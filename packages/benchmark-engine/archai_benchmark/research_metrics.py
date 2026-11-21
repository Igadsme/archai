from __future__ import annotations

import random
from statistics import mean, stdev


def bootstrap_interval(values: list[float], *, seed: int = 0, samples: int = 2000,
                      confidence: float = 0.95) -> tuple[float, float]:
    if not values or not 0 < confidence < 1 or samples <= 0:
        raise ValueError("values, confidence, and samples must be valid")
    rng = random.Random(seed)
    estimates = [mean(rng.choices(values, k=len(values))) for _ in range(samples)]
    estimates.sort()
    alpha = (1.0 - confidence) / 2.0
    return estimates[int(alpha * samples)], estimates[min(samples - 1, int((1.0 - alpha) * samples))]


def summarize_seeds(values: list[float], *, seed: int = 0) -> dict[str, float]:
    if not values:
        raise ValueError("at least one seed result is required")
    interval = bootstrap_interval(values, seed=seed)
    return {"mean": mean(values), "std": stdev(values) if len(values) > 1 else 0.0,
            "min": min(values), "max": max(values), "ci_low": interval[0], "ci_high": interval[1],
            "n_seeds": float(len(values))}


def search_regret(best_found: float, oracle_best: float) -> float:
    """Positive regret means the search missed the best available result."""
    return max(0.0, oracle_best - best_found)


def hypervolume_2d(points: list[tuple[float, float]], reference: tuple[float, float]) -> float:
    """Compute exact 2D hypervolume for (maximize, minimize) points."""
    if not points:
        return 0.0
    ref_accuracy, ref_cost = reference
    valid = sorted({(accuracy, cost) for accuracy, cost in points
                    if accuracy >= ref_accuracy and cost <= ref_cost})
    if not valid:
        return 0.0
    suffix_best_cost = [0.0] * len(valid)
    best_cost = ref_cost
    for index in range(len(valid) - 1, -1, -1):
        best_cost = min(best_cost, valid[index][1])
        suffix_best_cost[index] = best_cost
    area = 0.0
    previous_accuracy = ref_accuracy
    for index, (accuracy, _) in enumerate(valid):
        height = max(0.0, ref_cost - suffix_best_cost[index])
        area += max(0.0, accuracy - previous_accuracy) * height
        previous_accuracy = accuracy
    return area
