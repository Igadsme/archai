from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class DatasetManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: str
    version: str
    uri: str
    sha256: str | None = Field(default=None, pattern=r"^[0-9a-fA-F]{64}$")
    license: str
    search_space: str
    source: str


def load_manifest(path: str) -> DatasetManifest:
    return DatasetManifest.model_validate_json(Path(path).read_text(encoding="utf-8"))
