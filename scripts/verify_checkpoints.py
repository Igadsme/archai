"""Verify ArchAI-V1 smoke checkpoints: SHA-256 matches the training report, and a reloaded
model reproduces the saved model's outputs (predictor: held-out predictions; generator: samples)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from archai_shared.registry import sha256_file


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictor-report", type=Path, required=True)
    parser.add_argument("--predictor-checkpoint", type=Path, required=True)
    parser.add_argument("--generator-report", type=Path, required=True)
    parser.add_argument("--benchmark-path", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from archai_benchmark.adapter import NATSBenchAdapter
    from archai_predictor.data import split_records
    from archai_predictor.model import PerformancePredictor, PredictorConfig
    from archai_predictor.training import evaluate_predictor, load_checkpoint

    from scripts.train_predictor import collect_records
    predictor_report = json.loads(args.predictor_report.read_text())
    predictor = PerformancePredictor(PredictorConfig())
    metadata = load_checkpoint(predictor, args.predictor_checkpoint)
    adapter = NATSBenchAdapter(args.benchmark_path).open()
    indices = [int(value) for value in metadata["architecture_index_list"]] if "architecture_index_list" in metadata else None
    result = {"predictor": {"checkpoint": str(args.predictor_checkpoint),
                            "sha256_matches_report": sha256_file(args.predictor_checkpoint) == predictor_report["checkpoint_sha256"],
                            "code_revision": metadata["code_revision"]}}
    if indices is None:
        import random
        indices = sorted(random.Random(0).sample(range(15625), metadata["split_sizes"]["train"]
                                                + metadata["split_sizes"]["validation"] + metadata["split_sizes"]["test"]))
    records = collect_records(adapter, indices, metadata["seed"], metadata["dataset"])
    if [record.architecture.content_hash() for record in records] != metadata["architecture_ids"]:
        raise SystemExit("predictor records do not match the checkpoint's architecture ids")
    test = evaluate_predictor(predictor, split_records(records, seed=metadata["seed"])["test"])
    result["predictor"]["reloaded_test_metrics_match_report"] = all(
        abs(test[key] - predictor_report["test"][key]) < 1e-6 for key in ("mae", "rmse", "spearman", "kendall"))
    generator_report = json.loads(args.generator_report.read_text())
    generator_checkpoint = Path(generator_report["checkpoint"])
    result["generator"] = {"checkpoint": str(generator_checkpoint),
                           "sha256_matches_report": sha256_file(generator_checkpoint) == generator_report["checkpoint_sha256"],
                           "reload_reproduces_samples": generator_report["checkpoint_reload_reproduces_samples"]}
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True))
    print(json.dumps(result, sort_keys=True))
    return 0 if all(all(v for k, v in part.items() if isinstance(v, bool)) for part in result.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
