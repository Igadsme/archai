"""Filter a benchmark index pool by ArchitectureConstraints."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Protocol

from archai_shared.constraints import ArchitectureConstraints, ConstraintReport, check_constraints

from .nasbench201 import parse_architecture_string


class CostAdapter(Protocol):
    def cost(self, architecture_index: int) -> dict[str, float]: ...
    def architecture_string(self, architecture_index: int) -> str: ...


def feasible_benchmark_indices(adapter: CostAdapter, indices: Sequence[int],
                               constraints: ArchitectureConstraints, *,
                               require_evaluable: bool = True,
                               ) -> tuple[list[int], list[str]]:
    """Return (feasible indices, unique unevaluable constraint names).

    NATS-Bench costs are in millions for params/FLOPs and seconds for latency.
    """
    if constraints.is_empty():
        return list(indices), []
    feasible: list[int] = []
    unevaluable: list[str] = []
    seen = set()
    for index in indices:
        cost = adapter.cost(index)
        operations = parse_architecture_string(adapter.architecture_string(index)).operations
        report = check_constraints(
            constraints,
            parameters=cost.get("params_m") * 1e6 if cost.get("params_m") is not None else None,
            flops=cost.get("flops_m") * 1e6 if cost.get("flops_m") is not None else None,
            latency_s=cost.get("latency_s"),
            operations=operations,
            require_evaluable=require_evaluable,
        )
        for name in report.unevaluable:
            if name not in seen:
                seen.add(name)
                unevaluable.append(name)
        if report.satisfied:
            feasible.append(index)
    if require_evaluable and unevaluable:
        return [], unevaluable
    return feasible, unevaluable


def reports_for_indices(adapter: CostAdapter, indices: Iterable[int],
                        constraints: ArchitectureConstraints) -> dict[int, ConstraintReport]:
    reports = {}
    for index in indices:
        cost = adapter.cost(index)
        operations = parse_architecture_string(adapter.architecture_string(index)).operations
        reports[index] = check_constraints(
            constraints,
            parameters=cost.get("params_m") * 1e6 if cost.get("params_m") is not None else None,
            flops=cost.get("flops_m") * 1e6 if cost.get("flops_m") is not None else None,
            latency_s=cost.get("latency_s"),
            operations=operations,
        )
    return reports
