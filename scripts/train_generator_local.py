"""Train a small FLOPs-budget-conditioned generator on CPU and write a checkpoint the API can serve.

    python scripts/train_generator_local.py --checkpoint artifacts/generator/local.pt \
        --report artifacts/generator/local-report.json

Takes well under a minute on a laptop CPU with the defaults. The corpus is random GENERATABLE_OPS chains labelled
with analytical FLOPs (see archai_generator.local_corpus); the model learns budget-aware op choice, not accuracy.
Set ARCHAI_GENERATOR_CHECKPOINT to the checkpoint path to enable POST /v1/architectures/generate.
"""
from __future__ import annotations

import argparse
import json
import random
import subprocess
import time
from pathlib import Path

from archai_core.schema import TensorSpec
from archai_generator.local_corpus import (
    CONDITION_DIM,
    ENCODING_NAME,
    N_BINS,
    budget_adherence,
    build_corpus,
    encode_bin,
    encode_budget,
    reference_flops,
)
from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import fit_sequences, generation_metrics, save_checkpoint
from archai_shared.registry import sha256_file

BUDGETS = (1 / 3, 1 / 2, 2 / 3, 5 / 6)


def _revision() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True, stderr=subprocess.DEVNULL).strip()
    except (OSError, subprocess.CalledProcessError):
        return "working-tree"


def train(*, corpus_size: int, epochs: int, seed: int, lr: float, hidden_dim: int, length: int = 8,
          unconditioned_share: float = 0.15, spec: TensorSpec | None = None, output_classes: int = 10):
    import torch

    spec = spec or TensorSpec(channels=3, height=32, width=32)
    torch.manual_seed(seed)
    corpus = build_corpus(corpus_size, length=length, seed=seed, spec=spec, output_classes=output_classes)
    rng = random.Random(seed + 1)
    conditions = [encode_bin(None) if rng.random() < unconditioned_share else encode_bin(row["bin"])
                  for row in corpus]
    model = ArchitectureGenerator(GeneratorConfig(hidden_dim=hidden_dim, max_nodes=length,
                                                  condition_dim=CONDITION_DIM))
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    started = time.monotonic()
    history = fit_sequences(model, [row["ops"] for row in corpus], conditions=conditions, epochs=epochs,
                            seed=seed, optimizer=optimizer)
    seconds = time.monotonic() - started
    model.train(False)
    return model, corpus, history, seconds, spec


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--corpus-size", type=int, default=4096)
    parser.add_argument("--epochs", type=int, default=400)
    parser.add_argument("--hidden-dim", type=int, default=64)
    parser.add_argument("--lr", type=float, default=3e-3)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--eval-samples", type=int, default=256)
    args = parser.parse_args()

    import torch
    model, corpus, history, seconds, spec = train(corpus_size=args.corpus_size, epochs=args.epochs, seed=args.seed,
                                                  lr=args.lr, hidden_dim=args.hidden_dim)
    length, output_classes = model.config.max_nodes, 10
    adherence = budget_adherence(model, budgets=BUDGETS, samples=args.eval_samples, length=length, spec=spec,
                                 output_classes=output_classes, seed=args.seed + 1000)
    candidates = [model.sample(seed=args.seed + offset, condition=encode_budget(0.5), input_spec=spec)[-1]
                  for offset in range(64)]
    metadata = {
        "model": "ArchAI-V1", "kind": "generator", "scale": "local_cpu",
        "label": "local CPU generator; budget-conditioned on analytical FLOPs, not trained for accuracy",
        "seed": args.seed, "code_revision": _revision(), "corpus": "random GENERATABLE_OPS chains (synthetic)",
        "corpus_examples": len(corpus), "epochs": args.epochs, "final_training_loss": history[-1],
        "training_seconds": round(seconds, 2), "torch_version": str(torch.__version__), "device": "cpu",
        "conditional": True,
        "condition_encoding": {"name": ENCODING_NAME, "dims": CONDITION_DIM, "bins": N_BINS,
                               "reference": "FLOPs of an all-conv3x3 chain of max_nodes ops at the request input_spec",
                               "trained_input_spec": spec.model_dump(), "trained_output_classes": output_classes,
                               "reference_flops_at_trained_spec": reference_flops(length, spec, output_classes)},
    }
    save_checkpoint(model, args.checkpoint, metadata)
    report = {"metadata": metadata, "checkpoint": str(args.checkpoint),
              "checkpoint_sha256": sha256_file(args.checkpoint), "training_loss": history,
              "budget_adherence": adherence, "generation_metrics": generation_metrics(candidates),
              "evaluation_note": ("within_budget_* is the share of sampled chains whose analytical FLOPs fraction is at "
                                  "or below the requested budget; unconditioned uses the all-zero condition.")}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2, sort_keys=True))
    print(json.dumps({"checkpoint": str(args.checkpoint), "sha256": report["checkpoint_sha256"],
                      "training_seconds": metadata["training_seconds"], "final_loss": round(history[-1], 4),
                      "budget_adherence": adherence}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
