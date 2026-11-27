"""Architecture constraints shared by projects, the generator, and search.

A constraint that cannot be evaluated in a given context (for example latency on
an analytical graph with no latency model) is reported as such rather than ignored.
"""
from __future__ import annotations

from collections.abc import Iterable

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Union of the compiler DAG ops and the NATS-Bench TSS / NAS-Bench-201 cell ops.
KNOWN_OPS = frozenset({
    "input", "output", "conv3x3", "conv1x1", "skip", "avg_pool3x3", "none",
    "nor_conv_3x3", "nor_conv_1x1", "skip_connect", "avg_pool_3x3",
})


class ArchitectureConstraints(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_parameters: int | None = Field(default=None, gt=0, le=10**12)
    max_flops: int | None = Field(default=None, gt=0, le=10**15)
    max_latency_s: float | None = Field(default=None, gt=0, le=60)
    allowed_ops: list[str] | None = Field(default=None, max_length=32)

    @field_validator("allowed_ops")
    @classmethod
    def ops_are_known_and_unique(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return value
        if not value:
            raise ValueError("allowed_ops must contain at least one operation when set")
        unknown = sorted(set(value) - KNOWN_OPS)
        if unknown:
            raise ValueError(f"unsupported operations: {', '.join(unknown)}")
        # Preserve order, drop duplicates.
        seen: list[str] = []
        for op in value:
            if op not in seen:
                seen.append(op)
        return seen

    def is_empty(self) -> bool:
        return (self.max_parameters is None and self.max_flops is None
                and self.max_latency_s is None and not self.allowed_ops)


class ConstraintReport(BaseModel):
    """Outcome of checking one architecture or benchmark cell against constraints."""
    model_config = ConfigDict(extra="forbid")
    satisfied: bool
    violations: list[str] = Field(default_factory=list)
    unevaluable: list[str] = Field(default_factory=list)


def check_constraints(constraints: ArchitectureConstraints, *,
                      parameters: int | float | None = None,
                      flops: int | float | None = None,
                      latency_s: float | None = None,
                      operations: Iterable[str] | None = None,
                      require_evaluable: bool = True) -> ConstraintReport:
    """Compare costs and the op set to the constraints. Pass raw parameter and FLOP counts (for NATS-Bench, `params_m * 1e6`)."""
    violations: list[str] = []
    unevaluable: list[str] = []
    if constraints.max_parameters is not None:
        if parameters is None:
            unevaluable.append("max_parameters")
        elif parameters > constraints.max_parameters:
            violations.append(
                f"parameters {parameters:g} exceed max_parameters {constraints.max_parameters}")
    if constraints.max_flops is not None:
        if flops is None:
            unevaluable.append("max_flops")
        elif flops > constraints.max_flops:
            violations.append(f"flops {flops:g} exceed max_flops {constraints.max_flops}")
    if constraints.max_latency_s is not None:
        if latency_s is None:
            unevaluable.append("max_latency_s")
        elif latency_s > constraints.max_latency_s:
            violations.append(
                f"latency {latency_s:g}s exceeds max_latency_s {constraints.max_latency_s}")
    if constraints.allowed_ops:
        if operations is None:
            unevaluable.append("allowed_ops")
        else:
            allowed = set(constraints.allowed_ops)
            # Structural input/output nodes are never constrained away.
            structural = {"input", "output"}
            unexpected = sorted({op for op in operations if op not in allowed and op not in structural})
            if unexpected:
                violations.append(f"operations not in allowed_ops: {', '.join(unexpected)}")
    if require_evaluable and unevaluable:
        violations.extend(f"{name} cannot be evaluated in this context" for name in unevaluable)
        return ConstraintReport(satisfied=False, violations=violations, unevaluable=unevaluable)
    return ConstraintReport(satisfied=not violations, violations=violations, unevaluable=unevaluable)


def resolve_constraints(request: ArchitectureConstraints | None,
                        project: ArchitectureConstraints | None = None) -> ArchitectureConstraints:
    """Request fields override the project's constraints; unset request fields inherit."""
    base = (project or ArchitectureConstraints()).model_dump()
    if request is not None:
        for key, value in request.model_dump().items():
            if value is not None:
                base[key] = value
    return ArchitectureConstraints.model_validate(base)
