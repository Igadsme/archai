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


def gaussian_calibration_error(targets: list[float], means: list[float], standard_deviations: list[float]) -> float:
    """Absolute coverage error averaged over several nominal Gaussian levels."""
    if not (len(targets) == len(means) == len(standard_deviations)) or not targets:
        raise ValueError("calibration inputs must be non-empty and equally sized")
    levels = ((0.50, 0.67449), (0.80, 1.28155), (0.90, 1.64485), (0.95, 1.95996))
    errors = []
    for nominal, z_score in levels:
        covered = sum(abs(target - mean) <= z_score * max(std, 1e-8)
                      for target, mean, std in zip(targets, means, standard_deviations)) / len(targets)
        errors.append(abs(covered - nominal))
    return sum(errors) / len(errors)


def embedding_ood_scores(reference_embeddings, query_embeddings):
    """Return standardized Euclidean distances from a reference embedding cloud."""
    try:
        import numpy as np
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra for OOD scoring") from exc
    reference = np.asarray(reference_embeddings, dtype=float)
    query = np.asarray(query_embeddings, dtype=float)
    if reference.ndim != 2 or query.ndim != 2 or reference.shape[1] != query.shape[1] or len(reference) < 2:
        raise ValueError("embeddings must be 2D with matching widths and at least two reference rows")
    center = reference.mean(axis=0)
    scale = reference.std(axis=0).clip(min=1e-6)
    return list(np.sqrt(((query - center) / scale) ** 2).mean(axis=1))
