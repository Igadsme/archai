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


class ArchitectureDataset:
    """Torch-compatible dataset wrapper over provenance-bearing records."""
    def __init__(self, records: list[ArchitectureRecord]):
        if not records:
            raise ValueError("architecture dataset cannot be empty")
        self.records = list(records)

    def __len__(self) -> int:
        return len(self.records)

    def __getitem__(self, index: int) -> ArchitectureRecord:
        return self.records[index]


def make_loader(records: list[ArchitectureRecord], *, batch_size: int = 32, shuffle: bool = False,
                seed: int = 0):
    try:
        import torch
        from torch.utils.data import DataLoader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra to use predictor loaders") from exc
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    generator = torch.Generator().manual_seed(seed)
    return DataLoader(ArchitectureDataset(records), batch_size=batch_size, shuffle=shuffle,
                      generator=generator, collate_fn=collate_records)


def split_records(records: list[ArchitectureRecord], seed: int = 0,
                  fractions: tuple[float, float, float] = (0.8, 0.1, 0.1)) -> dict[str, list[ArchitectureRecord]]:
    """Split by architecture hash, making repeated benchmark observations inseparable."""
    if abs(sum(fractions) - 1.0) > 1e-9 or any(f <= 0 for f in fractions):
        raise ValueError("fractions must be positive and sum to one")
    groups: dict[str, list[ArchitectureRecord]] = {}
    for record in records:
        groups.setdefault(record.architecture.content_hash(), []).append(record)
    ordered = sorted(groups.values(), key=lambda group: group[0].architecture.content_hash())
    rng = random.Random(seed)
    rng.shuffle(ordered)
    n = len(ordered)
    first = int(n * fractions[0])
    second = first + int(n * fractions[1])
    result = {"train": [item for group in ordered[:first] for item in group],
              "validation": [item for group in ordered[first:second] for item in group],
              "test": [item for group in ordered[second:] for item in group]}
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
    adjacency = torch.zeros(len(features), max_nodes, max_nodes)
    for index, item in enumerate(features):
        batch[index, :item.shape[0]] = item
        mask[index, :item.shape[0]] = True
        by_id = {node.id: node_index for node_index, node in enumerate(records[index].architecture.nodes)}
        for edge in records[index].architecture.edges:
            adjacency[index, by_id[edge.target], by_id[edge.source]] = 1.0
    tasks = torch.tensor([record.task_features for record in records], dtype=torch.float32)
    targets = torch.tensor([record.target for record in records], dtype=torch.float32)
    return batch, mask, adjacency, tasks, targets
