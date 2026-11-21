"""Train the conditional ArchAI generator from a JSONL architecture corpus."""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

from archai_core.schema import Architecture
from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import fit_generator, generation_metrics, save_checkpoint
from archai_shared.registry import sha256_file


def _revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except (OSError, subprocess.CalledProcessError):
        return "working-tree"


def load_examples(path: str | Path, condition_dim: int = 8):
    examples = []
    for line_number, line in enumerate(Path(path).read_text().splitlines(), start=1):
        if not line.strip():
            continue
        payload = json.loads(line)
        architecture_payload = payload.get("architecture", payload)
        condition = tuple(payload.get("condition", [0.0] * condition_dim))
        if len(condition) != condition_dim:
            raise ValueError(f"line {line_number}: condition length must be {condition_dim}")
        examples.append((Architecture.model_validate(architecture_payload), condition))
    if not examples:
        raise ValueError("architecture corpus is empty")
    return examples


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--corpus", type=Path, required=True, help="JSONL architecture corpus")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()
    examples = load_examples(args.corpus)
    model = ArchitectureGenerator(GeneratorConfig(condition_dim=8))
    history = fit_generator(model, examples, epochs=args.epochs, seed=args.seed)
    candidates = model.sample(seed=args.seed, condition=examples[0][1])
    metrics = generation_metrics(candidates)
    metadata = {"model": "ArchAI-V1", "kind": "generator", "seed": args.seed,
                "code_revision": _revision(), "corpus_examples": len(examples),
                "conditional": True, "test_selection": "not applicable"}
    save_checkpoint(model, args.checkpoint, metadata)
    checkpoint_sha256 = sha256_file(args.checkpoint)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps({"metadata": metadata, "checkpoint_sha256": checkpoint_sha256,
                                       "training_loss": history, "generation_metrics": metrics},
                                      indent=2, sort_keys=True))
    print(json.dumps({"checkpoint": str(args.checkpoint), "report": str(args.report), "generation_metrics": metrics}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
