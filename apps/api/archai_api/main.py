from __future__ import annotations

from fastapi import FastAPI, HTTPException

from archai_core.schema import Architecture
from archai_core.validation import ValidationError, validate_architecture
from archai_compiler.metrics import analytical_metrics

app = FastAPI(title="ArchAI API", version="v1")


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


@app.post("/v1/architectures/generate")
def generate_unavailable():
    raise HTTPException(status_code=503, detail="No trained generator checkpoint is configured")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)
