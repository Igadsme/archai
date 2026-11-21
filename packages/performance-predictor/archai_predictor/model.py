from __future__ import annotations

from dataclasses import dataclass

from archai_core.schema import Architecture, OP_TYPES


@dataclass(frozen=True)
class PredictorConfig:
    hidden_dim: int = 64
    task_dim: int = 8
    dropout: float = 0.1


class PerformancePredictor:
    """Edge-aware graph encoder with lazy torch import; outputs mean and log variance."""
    def __new__(cls, config: PredictorConfig = PredictorConfig()):
        try:
            import torch
            from torch import nn
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("install the 'ml' extra to use the predictor") from exc
        op_count = len(OP_TYPES)
        class _Model(nn.Module):
            def __init__(self):
                super().__init__()
                self.config = config
                self.node = nn.Sequential(nn.Linear(op_count + 4, config.hidden_dim), nn.ReLU(),
                                          nn.Dropout(config.dropout))
                self.message = nn.Linear(config.hidden_dim, config.hidden_dim, bias=False)
                self.update = nn.Linear(config.hidden_dim, config.hidden_dim)
                self.head = nn.Sequential(nn.Linear(config.hidden_dim + config.task_dim, config.hidden_dim),
                                          nn.ReLU(), nn.Linear(config.hidden_dim, 2))

            def forward(self, node_features, task_features, adjacency=None, mask=None):
                hidden = self.node(node_features)
                if adjacency is not None:
                    degree = adjacency.sum(dim=-1, keepdim=True).clamp_min(1.0)
                    neighbor = torch.bmm(adjacency, hidden) / degree
                    hidden = torch.relu(self.update(hidden) + self.message(neighbor))
                if mask is None:
                    pooled = hidden.mean(dim=1)
                else:
                    pooled = (hidden * mask.unsqueeze(-1)).sum(dim=1) / mask.sum(dim=1, keepdim=True).clamp_min(1)
                return self.head(torch.cat([pooled, task_features], dim=-1))
        return _Model()


def featurize(architecture: Architecture):
    try:
        import torch
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("install the 'ml' extra to featurize tensors") from exc
    ops = list(OP_TYPES)
    rows = []
    for node in architecture.nodes:
        rows.append([float(node.op == op) for op in ops] + [node.channels / 4096, node.kernel_size / 7,
                     float(node.activation != "none"), float(node.normalization != "none")])
    return torch.tensor(rows, dtype=torch.float32).unsqueeze(0)
