from __future__ import annotations

from dataclasses import dataclass
import random

from archai_core.schema import Architecture, OP_TYPES


@dataclass(frozen=True)
class ArchitectureRecord:
    architecture: Architecture
    target: float
    task_features: tuple[float, ...]
    source: str
    split: str | None = None


def split_records(records: list[ArchitectureRecord], seed: int = 0,
                  fractions: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> dict[str, list[ArchitectureRecord]]:
    """Split by architecture hash, making repeated benchmark observations inseparable."""
    if abs(sum(fractions) - 1.0) > 1e-9 or any(f <= 0 for f in fractions):
        raise ValueError("fractions must be positive and sum to one")
    ordered = sorted(records, key=lambda r: r.architecture.content_hash())
    rng = random.Random(seed)
    rng.shuffle(ordered)
    n = len(ordered)
    first = int(n * fractions[0])
    second = first + int(n * fractions[1])
    result = {"train": ordered[:first], "validation": ordered[first:second], "test": ordered[second:]}
    return {name: [record.__class__(record.architecture, record.target, record.task_features, record.source, name) for record in values]
            for name, values in result.items()}


def architecture_features(architecture: Architecture):
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra to use predictor features") from exc
    ops = sorted(OP_TYPES)
    rows = []
    for node in architecture.nodes:
        rows.append([float(node.op == op) for op in ops] + [node.channels / 4096.0, node.kernel_size / 7.0,
                     float(node.activation != "none"), float(node.normalization != "none")])
    return torch.tensor(rows, dtype=torch.float32)


def collate_records(records: list[ArchitectureRecord]):
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra to use predictor data") from exc
    features = [architecture_features(record.architecture) for record in records]
    max_nodes, width = max(item.shape[0] for item in features), features[0].shape[1]
    batch = torch.zeros(len(features), max_nodes, width)
    mask = torch.zeros(len(features), max_nodes, dtype=torch.bool)
    for index, item in enumerate(features):
        batch[index, :item.shape[0]] = item
        mask[index, :item.shape[0]] = True
    tasks = torch.tensor([record.task_features for record in records], dtype=torch.float32)
    targets = torch.tensor([record.target for record in records], dtype=torch.float32)
    return batch, mask, tasks, targets
