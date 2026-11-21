import pytest

from archai_benchmark.reporting import build_research_report


def test_report_groups_seeds_and_keeps_test_separate():
    report = build_research_report([
        {"run_id": "r1", "algorithm": "random", "seed": 1, "best_validation_accuracy": 0.8, "final_test_accuracy": 0.79, "search_cost": 10, "selected_on": "validation"},
        {"run_id": "r2", "algorithm": "random", "seed": 2, "best_validation_accuracy": 0.82, "final_test_accuracy": 0.81, "search_cost": 12, "selected_on": "validation"},
    ])
    assert report["test_selection_policy"] == "validation_only"
    assert report["algorithms"]["random"]["runs"] == 2


def test_report_rejects_test_selection():
    with pytest.raises(ValueError, match="test leakage"):
        build_research_report([{"run_id": "bad", "algorithm": "random", "seed": 1,
                               "best_validation_accuracy": 0.8, "selected_on": "test"}])
