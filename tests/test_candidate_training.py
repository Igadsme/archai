import pytest
from archai_core.schema import Architecture, Edge, Node, TensorSpec
from archai_training.candidate import train_candidate
from archai_training.engine import TrainingConfig


def test_compiled_candidate_runs_through_training_engine(tmp_path):
    torch = pytest.importorskip("torch")
    from torch.utils.data import DataLoader, TensorDataset
    architecture = Architecture(nodes=[Node(id="input", op="input", channels=3), Node(id="conv", op="conv3x3", channels=4), Node(id="output", op="output", channels=4)],
        edges=[Edge(source="input", target="conv"), Edge(source="conv", target="output")], input_spec=TensorSpec(channels=3, height=4, width=4), output_classes=2)
    inputs = torch.randn(8, 3, 4, 4)
    targets = torch.randint(0, 2, (8,))
    loader = DataLoader(TensorDataset(inputs, targets), batch_size=4)
    result = train_candidate(architecture, loader, loader, TrainingConfig(epochs=1), checkpoint_path=tmp_path / "candidate.pt")
    assert result.status == "completed"
