from __future__ import annotations

import math


def _rank(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    for position, index in enumerate(order):
        ranks[index] = position
    return ranks


def regression_metrics(targets: list[float], predictions: list[float], intervals: list[tuple[float, float]] | None = None) -> dict[str, float]:
    if len(targets) != len(predictions) or not targets:
        raise ValueError("targets and predictions must be non-empty and equally sized")
    errors = [prediction - target for target, prediction in zip(targets, predictions)]
    mae = sum(abs(error) for error in errors) / len(errors)
    rmse = math.sqrt(sum(error * error for error in errors) / len(errors))
    target_ranks, prediction_ranks = _rank(targets), _rank(predictions)
    d_squared = sum((a - b) ** 2 for a, b in zip(target_ranks, prediction_ranks))
    spearman = 1.0 - 6.0 * d_squared / (len(targets) * (len(targets) ** 2 - 1)) if len(targets) > 1 else 1.0
    concordant = discordant = 0
    for i in range(len(targets)):
        for j in range(i + 1, len(targets)):
            product = (targets[i] - targets[j]) * (predictions[i] - predictions[j])
            concordant += product > 0
            discordant += product < 0
    denominator = concordant + discordant
    kendall = (concordant - discordant) / denominator if denominator else 1.0
    result = {"mae": mae, "rmse": rmse, "spearman": spearman, "kendall": kendall}
    if intervals is not None:
        if len(intervals) != len(targets):
            raise ValueError("intervals must match targets")
        result["interval_coverage"] = sum(low <= target <= high for target, (low, high) in zip(targets, intervals)) / len(targets)
    return result
