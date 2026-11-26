import json
from pathlib import Path

import pytest

from archai_benchmark.adapter import BenchmarkRecord
from scripts.run_experiment_matrix import load_matrix, main, planned_runs, run_matrix

ROOT = Path(__file__).parents[1]
OPS = ("none", "skip_connect", "nor_conv_1x1", "nor_conv_3x3", "avg_pool_3x3")


class FakeAdapter:
    """Deterministic test double: synthetic accuracies for exercising plumbing only."""
    dataset = "cifar10"

    def __init__(self):
        self.queries = 0

    def architecture_string(self, index):
        ops = [OPS[(index // 5 ** position) % 5] for position in range(6)]
        return (f"|{ops[0]}~0|+|{ops[1]}~0|{ops[2]}~1|+|{ops[3]}~0|{ops[4]}~1|{ops[5]}~2|")

    def query(self, index, seed=0):
        self.queries += 1
        validation = 50.0 + (index * 7 % 31)
        test = validation - 1.0 - (index % 3)
        return BenchmarkRecord(index, self.dataset, seed, validation, test, 1.0)


def _config(tmp_path, **overrides):
    config = {"name": "unit", "benchmark": {"search_space": "tss", "dataset": "cifar10"},
              "indices": {"start": 0, "stop": 25}, "budget": 6, "seeds": [0, 1],
              "algorithms": ["random", "evolution"], "evolution": {"population_size": 3, "sample_size": 2}}
    config.update(overrides)
    path = tmp_path / "matrix.json"
    path.write_text(json.dumps(config))
    return path


def test_committed_experiment_configs_are_valid():
    paths = sorted((ROOT / "research/experiments").glob("*.json"))
    assert paths
    for path in paths:
        config = load_matrix(path)
        assert len(planned_runs(config)) == len(config["seeds"]) * len(config["algorithms"])


def test_matrix_rejects_bad_configs(tmp_path):
    with pytest.raises(ValueError, match="seeds"):
        load_matrix(_config(tmp_path, seeds=[1, 1]))
    with pytest.raises(ValueError, match="algorithms"):
        load_matrix(_config(tmp_path, algorithms=["random", "magic"]))
    with pytest.raises(ValueError, match="budget"):
        load_matrix(_config(tmp_path, budget=0))


def test_matrix_runs_matched_budget_and_builds_validation_only_report(tmp_path):
    config = load_matrix(_config(tmp_path))
    adapter = FakeAdapter()
    report = run_matrix(config, adapter, tmp_path / "out", archive_sha256="a" * 64)
    runs = json.loads((tmp_path / "out/runs.json").read_text())
    assert len(runs) == 4
    assert {run["search_cost"] for run in runs} == {6}  # per-run caches keep the budget matched
    assert adapter.queries == 24
    assert all(run["test_used_for_selection"] is False for run in runs)
    assert report["matched_budget"] == 6.0
    assert report["test_selection_policy"] == "validation_only"
    assert set(report["algorithms"]) == {"random", "evolution"}
    assert report["minimum_seeds"] == 2
    assert json.loads((tmp_path / "out/report.json").read_text())["archive_sha256"] == "a" * 64


def test_matrix_dry_run_needs_no_archive(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("sys.argv", ["run_experiment_matrix", "--config", str(_config(tmp_path)), "--dry-run"])
    assert main() == 0
    planned = json.loads(capsys.readouterr().out)
    assert len(planned["runs"]) == 4 and planned["index_pool_size"] == 25


def test_matrix_cli_rejects_checksum_mismatch(tmp_path, monkeypatch):
    archive = tmp_path / "archive.bin"
    archive.write_bytes(b"archive")
    monkeypatch.setattr("sys.argv", ["run_experiment_matrix", "--config", str(_config(tmp_path)),
        "--benchmark-path", str(archive), "--benchmark-sha256", "0" * 64, "--output", str(tmp_path / "o")])
    with pytest.raises(SystemExit):
        main()
