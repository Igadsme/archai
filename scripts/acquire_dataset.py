"""Acquire a declared dataset only after checksum verification."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_benchmark.integrity import acquire_file, sha256_file
from archai_benchmark.manifest import load_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--destination", type=Path, required=True)
    args = parser.parse_args()
    manifest = load_manifest(args.manifest)
    if not manifest.sha256:
        parser.error("manifest must provide a verified sha256 before acquisition")
    acquired = acquire_file(manifest.uri, args.destination, manifest.sha256)
    report = {"dataset_id": manifest.dataset_id, "version": manifest.version,
              "path": str(acquired), "sha256": sha256_file(acquired),
              "verified": True, "source": manifest.uri}
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
