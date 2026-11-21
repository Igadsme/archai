import pytest


def test_training_engine_runs_and_writes_safe_checkpoint(tmp_path):
    torch = pytest.importorskip("torch")
    from torch.utils.data import DataLoader, TensorDataset
    from archai_training.engine import TrainingConfig, train_model

    torch.manual_seed(1)
    inputs = torch.randn(12, 3, 4, 4)
    targets = (inputs.mean(dim=(1, 2, 3)) > 0).long()
    loader = DataLoader(TensorDataset(inputs, targets), batch_size=4, shuffle=False)
    model = torch.nn.Sequential(torch.nn.Flatten(), torch.nn.Linear(48, 2))
    checkpoint = tmp_path / "training.pt"
    result = train_model(model, loader, loader, TrainingConfig(epochs=2, seed=5), checkpoint_path=checkpoint)
    assert result.status == "completed"
    assert result.epochs_completed == 2
    assert checkpoint.exists()
    payload = torch.load(checkpoint, map_location="cpu", weights_only=True)
    assert set(payload) >= {"model_state", "optimizer_state", "config", "history"}
