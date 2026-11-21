from __future__ import annotations

import os
import hashlib
import hmac
import time
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from archai_core.schema import Architecture
from archai_core.validation import ValidationError, validate_architecture
from archai_compiler.metrics import analytical_metrics
from archai_api.db import (SqlAlchemyArchitectureStore, SqlAlchemyExperimentStore,
                           SqlAlchemyDatasetStore, SqlAlchemyModelRegistry, SqlAlchemySearchStore,
                           database_is_ready)
from archai_shared.jobs import InMemoryJobStore, RedisJobStore
from archai_shared.records import ArtifactStore, ExperimentRecord, Provenance
from archai_shared.registry import ModelRegistry
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="ArchAI API", version="v1")
_cors_origins = [origin.strip() for origin in os.getenv(
    "ARCHAI_CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(",") if origin.strip()]
app.add_middleware(CORSMiddleware, allow_origins=_cors_origins, allow_credentials=False,
                   allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
                   allow_headers=["Authorization", "Content-Type", "x-api-key"])
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
_model_registry = (SqlAlchemyModelRegistry.from_url(
    os.environ["DATABASE_URL"], initialize=os.getenv("ARCHAI_DB_AUTO_CREATE", "0") == "1")
    if os.getenv("DATABASE_URL") else ModelRegistry(os.getenv("ARCHAI_MODEL_MANIFEST", "/tmp/archai-models.json")))
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

    def list(self, limit: int = 50) -> list[dict]:
        return list(self._values.values())[:limit]


class _InMemoryExperimentStore:
    def __init__(self):
        self._values: dict[str, ExperimentRecord] = {}

    def put(self, record: ExperimentRecord) -> ExperimentRecord:
        self._values[record.experiment_id] = record
        return record

    def get(self, experiment_id: str) -> ExperimentRecord | None:
        return self._values.get(experiment_id)

    def list(self, limit: int = 50) -> list[ExperimentRecord]:
        return list(self._values.values())[:limit]


class _InMemoryDatasetStore:
    def __init__(self):
        self._values: dict[tuple[str, str], dict] = {}

    def put(self, *, dataset_id: str, version: str, checksum: str, uri: str, license: str | None = None) -> dict:
        import re
        if not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
            raise ValueError("dataset checksum must be a 64-character SHA-256 hex digest")
        key = (dataset_id, version)
        value = {"dataset_id": dataset_id, "version": version, "checksum": checksum.lower(),
                 "uri": uri, "license": license}
        if key in self._values and self._values[key] != value:
            raise ValueError("dataset version is immutable once registered")
        self._values[key] = value
        return value

    def get(self, dataset_id: str, version: str):
        return self._values.get((dataset_id, version))

    def list(self, limit: int = 50):
        return list(self._values.values())[:limit]


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
_dataset_store = (SqlAlchemyDatasetStore.from_url(
    os.environ["DATABASE_URL"], initialize=os.getenv("ARCHAI_DB_AUTO_CREATE", "0") == "1")
    if os.getenv("DATABASE_URL") else _InMemoryDatasetStore())


def _redis_is_ready() -> bool:
    if not isinstance(_jobs, RedisJobStore):
        return False
    try:
        return bool(_jobs.client.ping())
    except Exception:
        return False


@app.middleware("http")
async def request_limits(request: Request, call_next):
    max_bytes = int(os.getenv("ARCHAI_MAX_REQUEST_BYTES", str(1024 * 1024)))
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > max_bytes:
        return JSONResponse({"detail": "request body too large"}, status_code=413)
    if not content_length and request.method in {"POST", "PUT", "PATCH"}:
        body = await request.body()
        if len(body) > max_bytes:
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


class ExperimentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: str
    metrics: dict[str, float] | None = None
    failure_detail: str | None = Field(default=None, max_length=4096)


class GenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    count: int = Field(default=1, gt=0, le=64)
    seed: int = Field(default=0, ge=0)
    condition: list[float] = Field(default_factory=lambda: [0.0] * 8, min_length=8, max_length=8)
    input_spec: dict[str, int] = Field(default_factory=lambda: {"channels": 3, "height": 32, "width": 32})
    output_classes: int = Field(default=10, gt=1, le=10000)


class DatasetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=128)
    checksum: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    uri: str = Field(min_length=1, max_length=2048)
    license: str | None = Field(default=None, max_length=256)


def require_write_access(api_key: Annotated[str | None, Header(alias="x-api-key")] = None,
                         authorization: Annotated[str | None, Header()] = None) -> None:
    """Local development is open; deployed writes require a configured key.

    `ARCHAI_API_KEY_SHA256` avoids storing a plaintext key in the service
    environment. Bearer tokens and the legacy x-api-key header are accepted.
    """
    supplied = api_key
    if supplied is None and authorization and authorization.startswith("Bearer "):
        supplied = authorization.removeprefix("Bearer ")
    configured = os.getenv("ARCHAI_API_KEY")
    configured_hash = os.getenv("ARCHAI_API_KEY_SHA256")
    valid = False
    if supplied and configured:
        valid = hmac.compare_digest(supplied, configured)
    if supplied and configured_hash:
        valid = valid or hmac.compare_digest(hashlib.sha256(supplied.encode()).hexdigest(), configured_hash.lower())
    if (configured or configured_hash) and not valid:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "evidence_policy": "no fabricated metrics"}


@app.get("/readiness")
def readiness() -> dict[str, bool | str]:
    redis_ready = _redis_is_ready()
    database_configured = bool(os.getenv("DATABASE_URL"))
    database_ready = database_is_ready(os.environ["DATABASE_URL"]) if database_configured else True
    ready = database_ready and (redis_ready or not os.getenv("ARCHAI_REQUIRE_REDIS"))
    return {"status": "ready" if ready else "not_ready", "durable_worker_configured": redis_ready,
            "database_configured": database_configured, "database_ready": database_ready}


@app.get("/v1/infrastructure/workers")
def worker_status() -> dict[str, object]:
    configured = _redis_is_ready()
    return {"configured": configured, "status": "connected" if configured else "not_configured",
            "workers": []}


@app.get("/v1/infrastructure/queue")
def queue_status() -> dict[str, object]:
    backend = "redis" if isinstance(_jobs, RedisJobStore) else "in_memory"
    try:
        jobs = _jobs.list()
    except Exception as exc:
        return {"backend": backend, "available": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"backend": backend, "available": True,
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


@app.get("/v1/searches")
def list_searches(limit: int = Query(default=50, ge=1, le=500)):
    items = []
    for search in _search_store.list(limit):
        job = _jobs.get(search["search_id"])
        if job is not None:
            items.append({**search, "status": job.status, "job": job.as_dict()})
    return {"items": items}


@app.post("/v1/searches/{search_id}/start", dependencies=[Depends(require_write_access)])
def start_search(search_id: str):
    search = _search_store.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    job = _jobs.get(search_id)
    if job is None:
        raise HTTPException(status_code=404, detail="search job not found")
    if not _redis_is_ready():
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


@app.get("/v1/experiments")
def list_experiments(limit: int = Query(default=50, ge=1, le=500)):
    return {"items": [record.model_dump(mode="json") for record in _experiment_store.list(limit)]}


@app.patch("/v1/experiments/{experiment_id}", dependencies=[Depends(require_write_access)])
def update_experiment(experiment_id: str, request: ExperimentUpdate):
    record = _experiment_store.get(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    allowed = {"created": {"running", "failed", "cancelled"},
               "running": {"completed", "failed", "cancelled"},
               "completed": set(), "failed": set(), "cancelled": set()}
    if request.status not in {"created", "running", "completed", "failed", "cancelled"}:
        raise HTTPException(status_code=422, detail="invalid experiment status")
    if request.status not in allowed[record.status]:
        raise HTTPException(status_code=409, detail=f"invalid experiment transition {record.status}->{request.status}")
    now = datetime.now(timezone.utc)
    updated = record.model_copy(update={"status": request.status,
        "metrics": request.metrics if request.metrics is not None else record.metrics,
        "failure_detail": request.failure_detail,
        "completed_at": now if request.status in {"completed", "failed", "cancelled"} else record.completed_at})
    _experiment_store.put(updated)
    _artifact_store.append(updated)
    return updated.model_dump(mode="json")


@app.get("/v1/models")
def list_models():
    return {"items": [item.__dict__ for item in _model_registry.list()]}


@app.get("/v1/models/{model_id}")
def get_model(model_id: str, version: str | None = None):
    artifact = _model_registry.get(model_id, version)
    if artifact is None:
        raise HTTPException(status_code=404, detail="model not found")
    return artifact.__dict__


@app.post("/v1/datasets", dependencies=[Depends(require_write_access)])
def register_dataset(request: DatasetRequest):
    try:
        return _dataset_store.put(**request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/v1/datasets")
def list_datasets(limit: int = Query(default=50, ge=1, le=500)):
    return {"items": _dataset_store.list(limit)}


@app.get("/v1/datasets/{dataset_id}")
def get_dataset(dataset_id: str, version: str = Query(..., min_length=1, max_length=128)):
    dataset = _dataset_store.get(dataset_id, version)
    if dataset is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return dataset


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
