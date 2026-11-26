import pytest
from archai_shared.constraints import ArchitectureConstraints, check_constraints


def test_empty_constraints_are_satisfied():
    report = check_constraints(ArchitectureConstraints(), parameters=1_000_000, flops=2, latency_s=0.1, operations=["conv3x3"])
    assert report.satisfied and not report.violations


def test_parameter_flop_latency_and_op_violations_are_listed():
    constraints = ArchitectureConstraints(max_parameters=1000, max_flops=50, max_latency_s=0.01, allowed_ops=["conv3x3", "skip"])
    report = check_constraints(constraints, parameters=2000, flops=80, latency_s=0.02, operations=["avg_pool3x3"])
    assert not report.satisfied
    assert len(report.violations) == 4


def test_unevaluable_latency_is_a_hard_failure_by_default():
    report = check_constraints(ArchitectureConstraints(max_latency_s=0.01), parameters=10, operations=["skip"])
    assert not report.satisfied and "max_latency_s" in report.unevaluable


def test_unknown_ops_are_rejected():
    with pytest.raises(ValueError, match="unsupported operations"):
        ArchitectureConstraints(allowed_ops=["quantum_gate"])
