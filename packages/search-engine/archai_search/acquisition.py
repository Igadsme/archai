from __future__ import annotations

import math


def _normal_pdf(value: float) -> float:
    return math.exp(-0.5 * value * value) / math.sqrt(2.0 * math.pi)


def _normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def expected_improvement(mean: float, standard_deviation: float, incumbent: float, *, xi: float = 0.0) -> float:
    if standard_deviation < 0 or xi < 0:
        raise ValueError("standard deviation and xi must be non-negative")
    if standard_deviation == 0:
        return max(0.0, mean - incumbent - xi)
    improvement = mean - incumbent - xi
    z_score = improvement / standard_deviation
    return improvement * _normal_cdf(z_score) + standard_deviation * _normal_pdf(z_score)


def upper_confidence_bound(mean: float, standard_deviation: float, *, beta: float = 2.0) -> float:
    if standard_deviation < 0 or beta < 0:
        raise ValueError("standard deviation and beta must be non-negative")
    return mean + beta * standard_deviation


def rank_candidates(candidates: list[dict], *, incumbent: float, beta: float = 2.0) -> list[dict]:
    """Return candidates ranked by EI, retaining provenance fields."""
    ranked = []
    for candidate in candidates:
        item = dict(candidate)
        mean = float(item["predicted_mean"])
        deviation = max(0.0, float(item.get("predicted_std", 0.0)))
        item["acquisition"] = expected_improvement(mean, deviation, incumbent)
        item["ucb"] = upper_confidence_bound(mean, deviation, beta=beta)
        ranked.append(item)
    return sorted(ranked, key=lambda item: (item["acquisition"], item["ucb"]), reverse=True)
