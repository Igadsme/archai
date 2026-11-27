from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import kaggle_train_archai_v1 as kaggle

torch = pytest.importorskip("torch")


def test_kaggle_smoke_args_stay_tiny():
    args = kaggle.parse_args(["--smoke", "--output", "/tmp/unused-smoke"])
    assert args.smoke is True
    assert args.generator_cells <= 8
    assert args.generator_epochs <= 2
    assert args.cifar_epochs <= 1
    assert args.cifar_architectures <= 1
    assert args.time_budget_hours <= 0.25


def test_kaggle_train_smoke_on_cpu(tmp_path):
    output = tmp_path / "archai_v1_smoke"
    code = kaggle.main(["--smoke", "--output", str(output), "--device", "cpu", "--seed", "0"])
    assert code == 0
    metrics = json.loads((output / "metrics.json").read_text())
    assert metrics["smoke"] is True
    assert metrics["device"] == "cpu"
    assert metrics["generator"]["scale"] == "cpu_smoke"
    assert metrics["generator"]["epochs_completed"] >= 1
    assert metrics["generator"]["checkpoint_sha256"]
    assert Path(metrics["generator"]["checkpoint"]).is_file()
    assert metrics["predictor"]["scale"] == "cpu_smoke"
    assert metrics["predictor"]["checkpoint_sha256"]
    assert metrics["cifar10_eval"]["scale"] == "cpu_smoke"
    assert metrics["cifar10_eval"]["candidates"]
    assert metrics["cifar10_eval"]["candidates"][0]["evidence_type"] == "synthetic_training"
    assert "held_out_test_accuracy" not in metrics["cifar10_eval"]["candidates"][0]
