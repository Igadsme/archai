"""Condition encodings for parameter-budget-aware NAS-Bench-201 generation.

These helpers are used by `scripts/train_generator_nb201.py`. The scalar ceiling
is kept so nearby budgets stay close in the embedding, and a one-hot bin makes
the 0.8M evaluation budget a distinct code (sharper than a point estimate).
"""

from __future__ import annotations

MAX_PARAMS_M = 1.6
N_BUDGET_BINS = 6
CONDITION_DIM = 2 + N_BUDGET_BINS  # accuracy quantile, ceiling fraction, one-hot bin


def budget_bin(ceiling_frac: float, n_bins: int = N_BUDGET_BINS) -> int:
    frac = min(1.0, max(0.0, float(ceiling_frac)))
    if frac >= 1.0:
        return n_bins - 1
    return min(n_bins - 1, int(frac * n_bins))


def encode_condition(
    accuracy_quantile: float, ceiling_frac: float, n_bins: int = N_BUDGET_BINS
) -> tuple[float, ...]:
    """Return an 8-d condition: (acc quantile, ceiling/MAX, 6-bin one-hot)."""
    frac = min(1.0, max(0.0, float(ceiling_frac)))
    one_hot = [0.0] * n_bins
    one_hot[budget_bin(frac, n_bins)] = 1.0
    return (float(accuracy_quantile), frac, *one_hot)


def eval_condition(
    accuracy_quantile: float = 0.95, params_budget_m: float = 0.8
) -> tuple[float, ...]:
    return encode_condition(accuracy_quantile, params_budget_m / MAX_PARAMS_M)
