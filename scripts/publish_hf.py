#!/usr/bin/env python3
"""Publish ArchAI checkpoints to the Hugging Face Hub (private by default).

Dry-run mode is the default and never contacts the Hub API, even if HF_TOKEN
is set in the environment. A real upload requires an explicit --execute flag
and a fine-grained write token in HF_TOKEN; this script will not invent or
print that token. Do not run --execute until Imani provides a token and
asks for a publish.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def sha256_file(path: Path) -> str:
    from archai_shared.registry import sha256_file as digest

    return digest(path)


def collect_files(artifact_dir: Path, model_card: Path | None) -> list[dict]:
    if not artifact_dir.is_dir():
        raise SystemExit(f"artifact directory not found: {artifact_dir}")
    files: list[dict] = []
    for path in sorted(artifact_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("."):
            continue
        files.append(
            {
                "path": str(path.relative_to(artifact_dir)),
                "bytes": path.stat().st_size,
                "sha256": sha256_file(path),
            }
        )
    if model_card and model_card.is_file():
        already = {row["path"] for row in files}
        if "MODEL_CARD.md" not in already and "README.md" not in already:
            files.append(
                {
                    "path": "README.md",
                    "source": str(model_card),
                    "bytes": model_card.stat().st_size,
                    "sha256": sha256_file(model_card),
                    "note": "Hub model card is published as README.md",
                }
            )
    return files


def plan(args: argparse.Namespace) -> dict:
    files = collect_files(args.artifact_dir, args.model_card)
    total = sum(row["bytes"] for row in files)
    return {
        "repo_id": args.repo_id,
        "private": not args.public,
        "revision": args.revision,
        "artifact_dir": str(args.artifact_dir),
        "files": files,
        "file_count": len(files),
        "total_bytes": total,
        "total_bytes_note": "Stay under the free Hub private storage quota of 100 GB (verified 2026-11-26).",
        "dry_run": not args.execute,
        "token_present": bool(os.getenv("HF_TOKEN")),
        "token_used": False,
        "api_called": False,
    }


def execute_upload(payload: dict, args: argparse.Namespace) -> dict:
    token = os.getenv("HF_TOKEN")
    if not token:
        raise SystemExit("HF_TOKEN is required for --execute (fine-grained write token). Dry-run does not need it.")
    try:
        from huggingface_hub import HfApi
    except ImportError as exc:
        raise SystemExit("install huggingface_hub to run --execute (not required for --dry-run)") from exc
    api = HfApi(token=token)
    api.create_repo(repo_id=args.repo_id, private=not args.public, exist_ok=True, repo_type="model")
    api.upload_folder(
        repo_id=args.repo_id,
        folder_path=str(args.artifact_dir),
        repo_type="model",
        revision=args.revision,
        commit_message=args.commit_message,
    )
    if args.model_card and args.model_card.is_file():
        api.upload_file(
            path_or_fileobj=str(args.model_card),
            path_in_repo="README.md",
            repo_id=args.repo_id,
            repo_type="model",
            revision=args.revision,
            commit_message="Add model card",
        )
    payload["api_called"] = True
    payload["token_used"] = True
    payload["dry_run"] = False
    return payload


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-id", default="igadsme/archai-v1",
                        help="Hub repo id (owner/name). Created private unless --public is set.")
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--model-card", type=Path, default=ROOT / "MODEL_CARD.md")
    parser.add_argument("--revision", default="main")
    parser.add_argument("--commit-message", default="Add ArchAI-V1 artifacts")
    parser.add_argument("--public", action="store_true", help="Create or update a public repo. Default is private.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", dest="execute", action="store_false",
                      help="Print the upload plan and do not call the Hub API (default).")
    mode.add_argument("--execute", dest="execute", action="store_true",
                      help="Actually upload. Requires HF_TOKEN. Do not use until Imani asks.")
    parser.set_defaults(execute=False)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    payload = plan(args)
    if args.execute:
        payload = execute_upload(payload, args)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
