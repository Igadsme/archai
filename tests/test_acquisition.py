import pytest
from archai_search.acquisition import expected_improvement, rank_candidates, upper_confidence_bound


def test_expected_improvement_handles_zero_uncertainty():
    assert expected_improvement(0.8, 0.0, 0.75) == pytest.approx(0.05)
    assert expected_improvement(0.7, 0.0, 0.75) == 0.0


def test_rank_candidates_prefers_useful_uncertainty():
    ranked = rank_candidates([{"id": "certain", "predicted_mean": 0.81, "predicted_std": 0.0},
                              {"id": "uncertain", "predicted_mean": 0.78, "predicted_std": 0.08}], incumbent=0.8)
    assert ranked[0]["id"] == "uncertain"
    assert upper_confidence_bound(0.8, 0.1, beta=2) == pytest.approx(1.0)
