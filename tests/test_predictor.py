import pytest

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture
from archai_predictor.data import ArchitectureRecord, collate_records, split_records
from archai_predictor.evaluation import embedding_ood_scores, gaussian_calibration_error, regression_metrics
from archai_predictor.model import PerformancePredictor, PredictorConfig
from archai_predictor.training import evaluate_predictor, fit_predictor, load_checkpoint, save_checkpoint


def make_architecture(channels: int) -> Architecture:
    return validate_architecture(Architecture(
        nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")],
        input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10,
    ))


def test_split_is_hash_disjoint():
    records = [ArchitectureRecord(make_architecture(channels), channels / 100, (0.0,) * 8, "unit") for channels in range(4, 14)]
    splits = split_records(records, seed=4)
    hashes = [{item.architecture.content_hash() for item in values} for values in splits.values()]
    assert not (hashes[0] & hashes[1] or hashes[0] & hashes[2] or hashes[1] & hashes[2])
    assert sum(map(len, hashes)) == len(records)


def test_regression_metrics():
    result = regression_metrics([1.0, 2.0, 3.0], [1.0, 2.5, 2.5])
    assert result["mae"] == pytest.approx(1 / 3)
    assert -1 <= result["kendall"] <= 1
    assert 0 <= gaussian_calibration_error([1, 2, 3], [1, 2, 3], [0.1, 0.1, 0.1]) <= 1


def test_embedding_ood_scores_separate_reference_and_query():
    pytest.importorskip("numpy")
    scores = embedding_ood_scores([[0, 0], [1, 1], [2, 2]], [[1, 1], [100, 100]])
    assert scores[1] > scores[0]


def test_predictor_training_checkpoint_roundtrip(tmp_path):
    torch = pytest.importorskip("torch")
    records = [ArchitectureRecord(make_architecture(channels), channels / 100, (0.0,) * 8, "unit") for channels in range(4, 12)]
    model = PerformancePredictor(PredictorConfig(hidden_dim=16, task_dim=8))
    history = fit_predictor(model, records, epochs=3, seed=3)
    assert len(history) == 3
    metrics = evaluate_predictor(model, records)
    assert set(("mae", "rmse", "spearman", "kendall", "interval_coverage")).issubset(metrics)
    path = tmp_path / "predictor.pt"
    save_checkpoint(model, path, {"kind": "unit", "seed": 3})
    restored = PerformancePredictor(PredictorConfig(hidden_dim=16, task_dim=8))
    metadata = load_checkpoint(restored, path)
    assert metadata["kind"] == "unit"
    with torch.no_grad():
        assert torch.isfinite(restored(torch.zeros(1, 3, 11), torch.zeros(1, 8))).all()


def test_predictor_consumes_graph_connectivity():
    torch = pytest.importorskip("torch")
    record = ArchitectureRecord(make_architecture(8), 0.8, (0.0,) * 8, "unit")
    features, mask, adjacency, tasks, _ = collate_records([record])
    model = PerformancePredictor(PredictorConfig(hidden_dim=16, task_dim=8))
    model.eval()
    with torch.no_grad():
        connected = model(features, tasks, adjacency, mask)
        disconnected = model(features, tasks, torch.zeros_like(adjacency), mask)
    assert adjacency.sum() > 0
    assert not torch.allclose(connected, disconnected)
