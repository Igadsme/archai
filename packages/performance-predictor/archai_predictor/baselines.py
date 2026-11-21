from __future__ import annotations

from .data import ArchitectureRecord
from .evaluation import regression_metrics


def _features(record: ArchitectureRecord) -> list[float]:
    from archai_core.schema import OP_TYPES
    architecture = record.architecture
    counts = [sum(node.op == operation for node in architecture.nodes) for operation in sorted(OP_TYPES)]
    return [1.0, float(len(architecture.nodes)), float(len(architecture.edges)), *map(float, counts),
            float(sum(node.channels for node in architecture.nodes))]


class MeanBaseline:
    """Leakage-safe statistical baseline fit only on the supplied training set."""
    def __init__(self):
        self.value: float | None = None

    def fit(self, records: list[ArchitectureRecord]) -> "MeanBaseline":
        if not records:
            raise ValueError("baseline requires training records")
        self.value = sum(record.target for record in records) / len(records)
        return self

    def predict(self, records: list[ArchitectureRecord]) -> list[float]:
        if self.value is None:
            raise RuntimeError("fit the baseline before prediction")
        return [self.value] * len(records)


class RidgeFeatureBaseline:
    """Closed-form graph-feature ridge baseline for predictor comparisons."""
    def __init__(self, alpha: float = 1e-3):
        if alpha <= 0:
            raise ValueError("alpha must be positive")
        self.alpha = alpha
        self.weights = None

    def fit(self, records: list[ArchitectureRecord]) -> "RidgeFeatureBaseline":
        if not records:
            raise ValueError("baseline requires training records")
        try:
            import numpy as np
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("install the 'ml' extra for the feature baseline") from exc
        matrix = np.asarray([_features(record) for record in records], dtype=float)
        targets = np.asarray([record.target for record in records], dtype=float)
        regularizer = self.alpha * np.eye(matrix.shape[1])
        regularizer[0, 0] = 0.0
        self.weights = np.linalg.solve(matrix.T @ matrix + regularizer, matrix.T @ targets)
        return self

    def predict(self, records: list[ArchitectureRecord]) -> list[float]:
        if self.weights is None:
            raise RuntimeError("fit the baseline before prediction")
        import numpy as np
        return list(np.asarray([_features(record) for record in records]) @ self.weights)


def evaluate_baseline(model, train_records: list[ArchitectureRecord], test_records: list[ArchitectureRecord]) -> dict[str, float]:
    model.fit(train_records)
    predictions = model.predict(test_records)
    return regression_metrics([record.target for record in test_records], predictions)
