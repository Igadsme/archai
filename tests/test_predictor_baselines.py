import pytest
from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture
from archai_predictor.baselines import MeanBaseline, RidgeFeatureBaseline, evaluate_baseline
from archai_predictor.data import ArchitectureRecord


def record(channels: int, target: float):
    architecture = validate_architecture(Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10))
    return ArchitectureRecord(architecture, target, (0.0,) * 8, "unit")


def test_mean_baseline_is_fit_only_on_training_set():
    metrics = evaluate_baseline(MeanBaseline(), [record(4, 0.2), record(8, 0.4)], [record(16, 0.8)])
    assert metrics["mae"] == pytest.approx(0.5)


def test_ridge_feature_baseline_runs():
    pytest.importorskip("numpy")
    model = RidgeFeatureBaseline()
    metrics = evaluate_baseline(model, [record(4, 0.2), record(8, 0.4), record(16, 0.8)], [record(32, 1.6)])
    assert {"mae", "rmse", "spearman", "kendall"}.issubset(metrics)
