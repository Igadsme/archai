from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Provenance(BaseModel):
    model_config = ConfigDict(extra="forbid", protected_namespaces=())
    code_revision: str = "working-tree"
    dataset_id: str
    dataset_version: str
    dataset_checksum: str | None = None
    model_checkpoint: str | None = None
    hardware: str = "unknown"
    seed: int


class ExperimentRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    experiment_id: str
    architecture_id: str
    evidence_type: Literal["predicted", "benchmark_lookup", "measured_training"]
    status: Literal["created", "running", "completed", "failed", "cancelled"]
    metrics: dict[str, float] = Field(default_factory=dict)
    provenance: Provenance
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    failure_detail: str | None = None


class ArtifactStore:
    """Append-only JSONL store for auditable local experiments."""
    def __init__(self, path: str | Path):
        self.path = Path(path)

    def append(self, record: ExperimentRecord) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(record.model_dump_json() + "\n")

    def read_all(self) -> list[ExperimentRecord]:
        if not self.path.exists():
            return []
        return [ExperimentRecord.model_validate_json(line) for line in self.path.read_text().splitlines() if line.strip()]
