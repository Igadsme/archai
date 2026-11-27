from archai_benchmark.constraint_filter import feasible_benchmark_indices
from archai_shared.constraints import ArchitectureConstraints, resolve_constraints


class FakeAdapter:
    def __init__(self, rows: dict[int, dict]):
        self._rows = rows

    def cost(self, architecture_index: int) -> dict[str, float]:
        row = self._rows[architecture_index]
        return {key: row[key] for key in ("params_m", "flops_m", "latency_s")}

    def architecture_string(self, architecture_index: int) -> str:
        return self._rows[architecture_index]["architecture_string"]


SMALL = "|none~0|+|none~0|none~1|+|skip_connect~0|none~1|none~2|"
CONV = "|nor_conv_3x3~0|+|none~0|nor_conv_1x1~1|+|avg_pool_3x3~0|skip_connect~1|none~2|"
ADAPTER = FakeAdapter({
    0: {"params_m": 0.3, "flops_m": 10.0, "latency_s": 0.01, "architecture_string": SMALL},
    1: {"params_m": 1.2, "flops_m": 80.0, "latency_s": 0.05, "architecture_string": CONV},
    2: {"params_m": 0.7, "flops_m": 20.0, "latency_s": 0.02, "architecture_string": SMALL},
})


def test_resolve_constraints_lets_request_fields_override_the_project():
    project = ArchitectureConstraints(max_parameters=1_000_000, allowed_ops=["skip_connect", "none"])
    request = ArchitectureConstraints(max_parameters=800_000, max_flops=50_000_000)
    resolved = resolve_constraints(request, project)
    assert resolved.max_parameters == 800_000
    assert resolved.max_flops == 50_000_000
    assert resolved.allowed_ops == ["skip_connect", "none"]


def test_filter_keeps_cells_within_param_and_op_budgets():
    constraints = ArchitectureConstraints(max_parameters=800_000, allowed_ops=["skip_connect", "none"])
    feasible, unevaluable = feasible_benchmark_indices(ADAPTER, [0, 1, 2], constraints)
    assert unevaluable == []
    assert feasible == [0, 2]


def test_filter_reports_unevaluable_latency_instead_of_ignoring_it():
    class NoLatency(FakeAdapter):
        def cost(self, architecture_index: int) -> dict[str, float]:
            row = self._rows[architecture_index]
            return {"params_m": row["params_m"], "flops_m": row["flops_m"]}

    adapter = NoLatency(ADAPTER._rows)
    constraints = ArchitectureConstraints(max_latency_s=0.02)
    feasible, unevaluable = feasible_benchmark_indices(adapter, [0, 1, 2], constraints)
    assert feasible == []
    assert unevaluable == ["max_latency_s"]
