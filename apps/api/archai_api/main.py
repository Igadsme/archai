from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from archai_core.schema import Architecture
from archai_core.validation import ValidationError, validate_architecture
from archai_compiler.metrics import analytical_metrics
from archai_shared.jobs import InMemoryJobStore, RedisJobStore
from archai_shared.records import ArtifactStore, ExperimentRecord, Provenance
from archai_shared.registry import ModelRegistry
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="ArchAI API", version="v1")
_architectures: dict[str, Architecture] = {}
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


class SearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    algorithm: str = Field(min_length=1, max_length=64)
    dataset_id: str = Field(min_length=1, max_length=128)
    budget_evaluations: int = Field(gt=0, le=1_000_000)
    seed: int = 0


class ExperimentRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    architecture_id: str
    evidence_type: str
    dataset_id: str
    dataset_version: str
    seed: int
    metrics: dict[str, float] = Field(default_factory=dict)


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
    _architectures[identifier] = architecture
    return {"architecture": architecture.model_dump(), "hash": identifier,
            "analytical_metrics": analytical_metrics(architecture).__dict__}


@app.get("/v1/architectures/{architecture_id}")
def get_architecture(architecture_id: str):
    architecture = _architectures.get(architecture_id)
    if architecture is None:
        raise HTTPException(status_code=404, detail="architecture not found")
    return {"architecture": architecture.model_dump(), "hash": architecture_id,
            "analytical_metrics": analytical_metrics(architecture).__dict__}


@app.get("/v1/architectures")
def list_architectures(limit: int = Query(default=50, ge=1, le=500)):
    values = list(_architectures.values())[:limit]
    return {"items": [{"architecture_id": value.content_hash(), "search_space": value.search_space,
                       "metrics": analytical_metrics(value).__dict__} for value in values]}


@app.post("/v1/searches", dependencies=[Depends(require_write_access)])
def create_search(request: SearchRequest):
    job = _jobs.create("search", request.model_dump())
    _searches[job.job_id] = {"search_id": job.job_id, "status": "created", **request.model_dump()}
    return _searches[job.job_id]


@app.get("/v1/searches/{search_id}")
def get_search(search_id: str):
    search = _searches.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    return search


@app.post("/v1/searches/{search_id}/start", dependencies=[Depends(require_write_access)])
def start_search(search_id: str):
    search = _searches.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    raise HTTPException(status_code=503, detail="no durable experiment worker is configured")


@app.post("/v1/searches/{search_id}/cancel", dependencies=[Depends(require_write_access)])
def cancel_search(search_id: str):
    search = _searches.get(search_id)
    if search is None:
        raise HTTPException(status_code=404, detail="search not found")
    search["status"] = "cancelled"
    return search


@app.post("/v1/experiments", dependencies=[Depends(require_write_access)])
def create_experiment(request: ExperimentRequest):
    if request.architecture_id not in _architectures:
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
    _experiments[record.experiment_id] = record
    _artifact_store.append(record)
    return record.model_dump(mode="json")


@app.get("/v1/experiments/{experiment_id}")
def get_experiment(experiment_id: str):
    record = _experiments.get(experiment_id)
    if record is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return record.model_dump(mode="json")


@app.get("/v1/models")
def list_models():
    return {"items": [item.__dict__ for item in _model_registry.list()]}


@app.post("/v1/architectures/generate")
def generate_unavailable():
    raise HTTPException(status_code=503, detail="No trained generator checkpoint is configured")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
