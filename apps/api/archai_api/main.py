from __future__ import annotations

import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Query

from archai_core.schema import Architecture
from archai_core.validation import ValidationError, validate_architecture
from archai_compiler.metrics import analytical_metrics

app = FastAPI(title="ArchAI API", version="v1")
_architectures: dict[str, Architecture] = {}


def require_write_access(api_key: Annotated[str | None, Header()] = None) -> None:
    """Local development is open; deployed writes require ARCHAI_API_KEY."""
    configured = os.getenv("ARCHAI_API_KEY")
    if configured and api_key != configured:
        raise HTTPException(status_code=401, detail="invalid API key")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "evidence_policy": "no fabricated metrics"}


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


@app.post("/v1/architectures/generate")
def generate_unavailable():
    raise HTTPException(status_code=503, detail="No trained generator checkpoint is configured")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
