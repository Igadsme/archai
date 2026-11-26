from __future__ import annotations

from pathlib import Path

from .data import ArchitectureRecord, collate_records, make_loader
from .evaluation import gaussian_calibration_error, regression_metrics


def gaussian_nll(output, target):
    mean, log_variance = output[:, 0], output[:, 1].clamp(-8.0, 8.0)
    return 0.5 * (log_variance + (target - mean).pow(2) / log_variance.exp()).mean()


def fit_predictor(model, records: list[ArchitectureRecord], *, epochs: int = 20, lr: float = 1e-3,
                  seed: int = 0, batch_size: int = 32) -> list[float]:
    import torch
    if epochs <= 0:
        raise ValueError("epochs must be positive")
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    torch.manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    loader = make_loader(records, batch_size=batch_size, shuffle=True, seed=seed)
    history = []
    model.train()
    for _ in range(epochs):
        losses = []
        for features, mask, adjacency, tasks, targets in loader:
            output = model(features, tasks, adjacency, mask)
            loss = gaussian_nll(output, targets)
            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            losses.append(float(loss.detach()))
        history.append(sum(losses) / len(losses))
    return history


def evaluate_predictor(model, records: list[ArchitectureRecord], interval_z: float = 1.96) -> dict[str, float]:
    import torch
    model.eval()
    with torch.no_grad():
        features, mask, adjacency, tasks, targets = collate_records(records)
        output = model(features, tasks, adjacency, mask)
        means = output[:, 0]
        std = output[:, 1].clamp(-8.0, 8.0).exp().sqrt()
    values = [float(item) for item in targets]
    predictions = [float(item) for item in means]
    intervals = [(float(mean - interval_z * deviation), float(mean + interval_z * deviation))
                 for mean, deviation in zip(means, std)]
    result = regression_metrics(values, predictions, intervals)
    result["calibration_error"] = gaussian_calibration_error(values, predictions, [float(item) for item in std])
    return result


def save_checkpoint(model, path: str | Path, metadata: dict):
    import torch
    payload = {"state_dict": model.state_dict(), "metadata": metadata}
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    torch.save(payload, path)


def load_checkpoint(model, path: str | Path) -> dict:
    import torch
    payload = torch.load(path, map_location="cpu", weights_only=True)
    model.load_state_dict(payload["state_dict"])
    return payload["metadata"]
