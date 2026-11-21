import pytest

from archai_benchmark.research_metrics import hypervolume_2d, search_regret, summarize_seeds


def test_seed_summary_and_regret():
    summary = summarize_seeds([0.8, 0.82, 0.81], seed=2)
    assert summary["n_seeds"] == 3
    assert summary["ci_low"] <= summary["mean"] <= summary["ci_high"]
    assert search_regret(0.8, 0.85) == pytest.approx(0.05)


def test_two_dimensional_hypervolume():
    assert hypervolume_2d([(0.8, 10), (0.9, 20)], (0.7, 30)) == pytest.approx(3.0)
