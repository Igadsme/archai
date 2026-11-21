from __future__ import annotations

from pathlib import Path

from .data import ArchitectureRecord, collate_records
from .evaluation import regression_metrics


def gaussian_nll(output, target):
    import torch
    mean, log_variance = output[:, 0], output[:, 1].clamp(-8.0, 8.0)
    return 0.5 * (log_variance + (target - mean).pow(2) / log_variance.exp()).mean()


def fit_predictor(model, records: list[ArchitectureRecord], *, epochs: int = 20, lr: float = 1e-3,
                  seed: int = 0) -> list[float]:
    import torch
    torch.manual_seed(seed)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    history = []
    model.train()
    for _ in range(epochs):
        features, mask, adjacency, tasks, targets = collate_records(records)
        output = model(features, tasks, adjacency, mask)
        loss = gaussian_nll(output, targets)
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        history.append(float(loss.detach()))
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
    return regression_metrics(values, predictions, intervals)


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
