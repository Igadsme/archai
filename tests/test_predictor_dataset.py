import pytest

from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_core.validation import validate_architecture
from archai_predictor.data import ArchitectureDataset, ArchitectureRecord, make_loader


def record(channels):
    architecture = validate_architecture(Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=channels), Node(id="output", op="output", channels=channels)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")], input_spec=TensorSpec(channels=3, height=8, width=8), output_classes=10))
    return ArchitectureRecord(architecture, channels / 100, (0.0,) * 8, "unit")


def test_dataset_and_loader_collate_graph_batch():
    pytest.importorskip("torch")
    values = [record(4), record(8)]
    assert len(ArchitectureDataset(values)) == 2
    batch = next(iter(make_loader(values, batch_size=2, seed=5)))
    features, mask, adjacency, tasks, targets = batch
    assert features.shape[0] == 2
    assert adjacency.shape[0] == 2
    assert targets.shape[0] == 2
