from pathlib import Path

from archai_benchmark import NATSBenchAdapter
from archai_benchmark.fixture import is_fixture_path
from archai_benchmark.integrity import sha256_file

FIXTURE = Path(__file__).resolve().parents[1] / "datasets/fixtures/natsbench-tss-cifar10-256"
CELLS = FIXTURE / "cells.jsonl"


def test_committed_fixture_is_labeled_and_checksum_stable():
    import json

    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    assert manifest["kind"] == "archai_natsbench_fixture"
    assert manifest["label"] == "fixture-only"
    assert manifest["not_the_official_benchmark"] is True
    assert manifest["n_cells"] == 256
    assert sha256_file(CELLS) == manifest["cells_sha256"]
    assert is_fixture_path(FIXTURE) and is_fixture_path(CELLS)


def test_fixture_adapter_queries_costs_and_official_split_protocol():
    adapter = NATSBenchAdapter(str(CELLS), "tss", "cifar10").open()
    record = adapter.query(0, seed=0)
    assert record.architecture_string.startswith("|")
    assert record.validation_accuracy > 0 and record.test_accuracy > 0
    cost = adapter.cost(0)
    assert cost["params_m"] > 0 and cost["latency_s"] > 0
    # A seed that maps to a different trial should be allowed to differ.
    other = adapter.query(0, seed=1)
    assert (
        other.benchmark_trial_seed != record.benchmark_trial_seed
        or other.validation_accuracy == record.validation_accuracy
    )


def test_fixture_indices_cover_all_committed_cells():
    from archai_benchmark.fixture import FixtureAPI

    assert FixtureAPI.from_path(FIXTURE).indices() == list(range(256))


def test_worker_expands_fixture_index_token(monkeypatch):
    from archai_api.worker import _benchmark_indices

    monkeypatch.setenv("ARCHAI_NATS_BENCH_INDICES", "fixture")
    assert _benchmark_indices({}, CELLS) == list(range(256))
    assert _benchmark_indices({"indices": [3, 9]}, CELLS) == [3, 9]
