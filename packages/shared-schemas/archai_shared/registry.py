from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class ModelArtifact:
    model_id: str
    kind: str
    version: str
    path: str
    sha256: str
    metadata: dict


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


class ModelRegistry:
    def __init__(self, manifest_path: str | Path):
        self.path = Path(manifest_path)

    def register(self, *, model_id: str, kind: str, version: str, artifact_path: str | Path,
                 metadata: dict | None = None) -> ModelArtifact:
        artifact_path = Path(artifact_path).resolve()
        if not artifact_path.is_file():
            raise FileNotFoundError(artifact_path)
        artifact = ModelArtifact(model_id, kind, version, str(artifact_path), sha256_file(artifact_path), metadata or {})
        records = self.list()
        if any(item.model_id == model_id and item.version == version for item in records):
            raise ValueError("model version already registered")
        records.append(artifact)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".partial")
        temporary.write_text(json.dumps([asdict(item) for item in records], sort_keys=True, indent=2))
        temporary.replace(self.path)
        return artifact

    def list(self) -> list[ModelArtifact]:
        if not self.path.exists():
            return []
        return [ModelArtifact(**item) for item in json.loads(self.path.read_text())]

    def get(self, model_id: str, version: str | None = None) -> ModelArtifact | None:
        values = [item for item in self.list() if item.model_id == model_id]
        if version is not None:
            values = [item for item in values if item.version == version]
        return values[-1] if values else None
