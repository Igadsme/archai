"""Register a model artifact with a SHA-256 manifest."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from archai_shared.registry import ModelRegistry


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-id", required=True)
    parser.add_argument("--kind", choices=("generator", "predictor", "candidate"), required=True)
    parser.add_argument("--version", required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--metadata", type=Path, help="JSON object with provenance metadata")
    args = parser.parse_args()
    metadata = json.loads(args.metadata.read_text()) if args.metadata else {}
    if not isinstance(metadata, dict):
        parser.error("--metadata must contain a JSON object")
    if os.getenv("DATABASE_URL"):
        from archai_api.db import SqlAlchemyModelRegistry
        registry = SqlAlchemyModelRegistry.from_url(os.environ["DATABASE_URL"])
    else:
        registry = ModelRegistry(os.getenv("ARCHAI_MODEL_MANIFEST", "/tmp/archai-models.json"))
    artifact = registry.register(model_id=args.model_id, kind=args.kind, version=args.version,
                                 artifact_path=args.artifact, metadata=metadata)
    print(json.dumps(artifact.__dict__, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
