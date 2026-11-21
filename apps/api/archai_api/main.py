from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from archai_core.schema import Architecture
from archai_core.validation import ValidationError, validate_architecture
from archai_compiler.metrics import analytical_metrics
from archai_api.db import SqlAlchemyArchitectureStore, SqlAlchemyExperimentStore, SqlAlchemySearchStore
from archai_shared.jobs import InMemoryJobStore, RedisJobStore
from archai_shared.records import ArtifactStore, ExperimentRecord, Provenance
from archai_shared.registry import ModelRegistry
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="ArchAI API", version="v1")
_searches: dict[str, dict] = {}
_experiments: dict[str, ExperimentRecord] = {}
def _make_job_store():
    url = os.getenv("ARCHAI_REDIS_URL")
    if url:
        try:
            return RedisJobStore.from_url(url)
        except RuntimeError:
            pass
    return InMemoryJobStore()


_jobs = _make_job_store()
_artifact_store = ArtifactStore(os.getenv("ARCHAI_ARTIFACT_STORE", "/tmp/archai-experiments.jsonl"))
_model_registry = ModelRegistry(os.getenv("ARCHAI_MODEL_MANIFEST", "/tmp/archai-models.json"))
_rate_windows: dict[str, deque[float]] = defaultdict(deque)


class _InMemoryArchitectureStore:
    def __init__(self):
        self._values: dict[str, Architecture] = {}

    def put(self, architecture: Architecture) -> Architecture:
        canonical = architecture.with_id()
        self._values[canonical.content_hash()] = canonical
        return canonical

    def get(self, architecture_id: str) -> Architecture | None:
        return self._values.get(architecture_id)

    def list(self, limit: int = 50) -> list[Architecture]:
        return list(self._values.values())[:limit]


class _InMemorySearchStore:
    def __init__(self):
        self._values: dict[str, dict] = {}

    def put(self, search_id: str, config: dict, *, status: str = "queued") -> dict:
        value = {"search_id": search_id, **config}
        self._values[search_id] = value
        return value

    def get(self, search_id: str) -> dict | None:
        return self._values.get(search_id)

    def set_status(self, search_id: str, status: str, consumed_evaluations: int | None = None) -> None:
        if search_id not in self._values:
            raise KeyError(search_id)


class _InMemoryExperimentStore:
    def __init__(self):
        self._values: dict[str, ExperimentRecord] = {}

    def put(self, record: ExperimentRecord) -> ExperimentRecord:
        self._values[record.experiment_id] = record
        return record

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        return self._values.get(experiment_id)


def _make_architecture_store():
    url = os.getenv("DATABASE_URL")
    if not url:
        return _InMemoryArchitectureStore()
    return SqlAlchemyArchitectureStore.from_url(
        url, initialize=os.getenv("ARCHAI_DB_AUTO_CREATE", "0") == "1")


_architecture_store = _make_architecture_store()


def _make_search_store():
    url = os.getenv("DATABASE_URL")
    if not url:
        return _InMemorySearchStore()
    return SqlAlchemySearchStore.from_url(url, initialize=os.getenv("ARCHAI_DB_AUTO_CREATE", "0") == "1")


def _make_experiment_store():
    url = os.getenv("DATABASE_URL")
    if not url:
        return _InMemoryExperimentStore()
    return SqlAlchemyExperimentStore.from_url(url, initialize=os.getenv("ARCHAI_DB_AUTO_CREATE", "0") == "1")


_search_store = _make_search_store()
_experiment_store = _make_experiment_store()


@app.middleware("http")
async def request_limits(request: Request, call_next):
    max_bytes = int(os.getenv("ARCHAI_MAX_REQUEST_BYTES", str(1024 * 1024)))
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        return JSONResponse({"detail": "request body too large"}, status_code=413)
    limit = int(os.getenv("ARCHAI_RATE_LIMIT_PER_MINUTE", "120"))
    key = request.client.host if request.client else "unknown"
    now = time.monotonic()
    window = _rate_windows[key]
    while window and now - window[0] >= 60:
        window.popleft()
    if len(window) >= limit:
        return JSONResponse({"detail": "rate limit exceeded"}, status_code=429)
    window.append(now)
    return await call_next(request)


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    algorithm: str = Field(min_length=1, max_length=64)
    dataset_id: str = Field(min_length=1, max_length=128)
    budget_evaluations: int = Field(gt=0, le=1_000_000)
    seed: int = 0
    indices: list[int] = Field(default_factory=list, max_length=100_000)


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    architecture_id: str
    evidence_type: str
    dataset_id: str
    dataset_version: str
    seed: int
    metrics: dict[str, float] = Field(default_factory=dict)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(default=1, gt=0, le=64)
    seed: int = Field(default=0, ge=0)
    condition: list[float] = Field(default_factory=lambda: [0.0] * 8, min_length=8, max_length=8)
    input_spec: dict[str, int] = Field(default_factory=lambda: {"channels": 3, "height": 32, "width": 32})
    output_classes: int = Field(default=10, gt=1, le=10000)


def require_write_access(api_key: Annotated[str | None, Header(alias="x-api-key")] = None) -> None:
    """Local development is open; deployed writes require ARCHAI_API_KEY."""
    configured = os.getenv("ARCHAI_API_KEY")
    if configured and api_key != configured:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "evidence_policy": "no fabricated metrics"}


@app.get("/readiness")
def readiness() -> dict[str, bool | str]:
    redis_ready = isinstance(_jobs, RedisJobStore)
    if redis_ready:
        try:
            _jobs.client.ping()
        except Exception:
            redis_ready = False
    return {"status": "ready", "durable_worker_configured": redis_ready,
            "database_configured": bool(os.getenv("DATABASE_URL"))}


@app.get("/v1/infrastructure/workers")
def worker_status() -> dict[str, object]:
    configured = isinstance(_jobs, RedisJobStore)
    return {"configured": configured, "status": "connected" if configured else "not_configured",
            "workers": []}


@app.get("/v1/infrastructure/queue")
def queue_status() -> dict[str, object]:
    jobs = _jobs.list()
    return {"backend": "redis" if isinstance(_jobs, RedisJobStore) else "in_memory",
            "queued": sum(job.status == "queued" for job in jobs),
            "running": sum(job.status == "running" for job in jobs),
            "terminal": sum(job.status in {"succeeded", "failed", "cancelled"} for job in jobs)}


@app.post("/v1/architectures/validate")
def validate(payload: Architecture):
    try:
        architecture = validate_architecture(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"architecture": architecture.model_dump(), "hash": architecture.content_hash(),
            "analytical_metrics": analytical_metrics(architecture).__dict__}


@app.post("/v1/architectures", dependencies=[Depends(require_write_access)])
def create_architecture(payload: Architecture):
    try:
        architecture = validate_architecture(payload)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    identifier = architecture.content_hash()
    architecture = _architecture_store.put(architecture)
    return {"architecture": architecture.model_dump(), "hash": identifier,
            "analytical_metrics": analytical_metrics(architecture).__dict__}


@app.get("/v1/architectures")
def list_architectures(limit: int = Query(default=50, ge=1, le=500)):
    values = _architecture_store.list(limit)
    return {"items": [{"architecture_id": value.content_hash(), "search_space": value.search_space,
                       "metrics": analytical_metrics(value).__dict__} for value in values]}


@app.get("/v1/architectures/compare")
def compare_architectures(ids: Annotated[list[str], Query(min_length=1, max_length=20)]):
    values = {identifier: _architecture_store.get(identifier) for identifier in ids}
    missing = [identifier for identifier, architecture in values.items() if architecture is None]
    if missing:
        raise HTTPException(status_code=404, detail={"missing_architectures": missing})
    return {"items": [{"architecture_id": identifier, "architecture": values[identifier].model_dump(),
                       "analytical_metrics": analytical_metrics(values[identifier]).__dict__} for identifier in ids]}


@app.get("/v1/architectures/{architecture_id}")
def get_architecture(architecture_id: str):
    architecture = _architecture_store.get(architecture_id)
    if architecture is None:
        raise HTTPException(status_code=404, detail="architecture not found")
    return {"architecture": architecture.model_dump(), "hash": architecture_id,
            "analytical_metrics": analytical_metrics(architecture).__dict__}


@app.post("/v1/searches", dependencies=[Depends(require_write_access)])
def create_search(request: SearchRequest):
    job = _jobs.create("search", request.model_dump())
    return _search_store.put(job.job_id, request.model_dump())


@app.get("/v1/searches/{search_id}")
def get_search(search_id: str):
    search = _search_store.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    job = _jobs.get(search_id)
    if job is None:
        raise HTTPException(status_code=404, detail="search job not found")
    return {**search, "status": job.status, "job": job.as_dict()}


@app.post("/v1/searches/{search_id}/start", dependencies=[Depends(require_write_access)])
def start_search(search_id: str):
    search = _search_store.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    job = _jobs.get(search_id)
    if job is None:
        raise HTTPException(status_code=404, detail="search job not found")
    if not isinstance(_jobs, RedisJobStore):
        raise HTTPException(status_code=503, detail="no durable experiment worker is configured")
    return {**search, "status": job.status, "job": job.as_dict()}


@app.post("/v1/searches/{search_id}/cancel", dependencies=[Depends(require_write_access)])
def cancel_search(search_id: str):
    search = _search_store.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    job = _jobs.get(search_id)
    if job is None:
        raise HTTPException(status_code=404, detail="search job not found")
    if job.status in {"queued", "running"}:
        job = _jobs.transition(search_id, "cancelled")
        _search_store.set_status(search_id, job.status)
    return {**search, "status": job.status, "job": job.as_dict()}


@app.post("/v1/experiments", dependencies=[Depends(require_write_access)])
def create_experiment(request: ExperimentRequest):
    if _architecture_store.get(request.architecture_id) is None:
        raise HTTPException(status_code=404, detail="architecture not found")
    try:
        record = ExperimentRecord(experiment_id=_jobs.create("experiment").job_id,
                                  architecture_id=request.architecture_id,
                                  evidence_type=request.evidence_type,
                                  status="created", metrics=request.metrics,
                                  provenance=Provenance(dataset_id=request.dataset_id,
                                      dataset_version=request.dataset_version, seed=request.seed))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    _experiment_store.put(record)
    _artifact_store.append(record)
    return record.model_dump(mode="json")


@app.get("/v1/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    record = _experiment_store.get(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return record.model_dump(mode="json")


@app.get("/v1/models")
def list_models():
    return {"items": [item.__dict__ for item in _model_registry.list()]}


@app.get("/v1/models/{model_id}")
def get_model(model_id: str, version: str | None = None):
    artifact = _model_registry.get(model_id, version)
    if artifact is None:
        raise HTTPException(status_code=404, detail="model not found")
    return artifact.__dict__


@app.post("/v1/architectures/generate")
def generate_architectures(request: GenerateRequest):
    checkpoint = os.getenv("ARCHAI_GENERATOR_CHECKPOINT")
    if not checkpoint:
        raise HTTPException(status_code=503, detail="No trained generator checkpoint is configured")
    try:
        import torch
        from archai_generator.model import ArchitectureGenerator, GeneratorConfig
        from archai_generator.training import load_checkpoint
        from archai_core.schema import TensorSpec

        payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
        saved_config = payload.get("state_dict", {}).get("config", {})
        config = GeneratorConfig(**saved_config) if saved_config else GeneratorConfig()
        model = ArchitectureGenerator(config)
        metadata = load_checkpoint(model, checkpoint)
        generated = []
        for offset in range(request.count):
            candidates = model.sample(seed=request.seed + offset, condition=tuple(request.condition),
                                      input_spec=TensorSpec.model_validate(request.input_spec),
                                      output_classes=request.output_classes)
            if not candidates:
                raise RuntimeError("generator returned no candidates")
            generated.append(candidates[-1])
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail="configured generator checkpoint is unavailable") from exc
    except (ImportError, ValueError, KeyError, RuntimeError, OSError) as exc:
        raise HTTPException(status_code=503, detail=f"generator checkpoint could not be loaded: {exc}") from exc
    return {"items": [{"architecture": candidate.model_dump(),
                       "architecture_id": candidate.content_hash()} for candidate in generated],
            "count": len(generated), "checkpoint": checkpoint, "metadata": metadata}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
