from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from archai_core.schema import Architecture
from archai_core.validation import validate_architecture
from .acquisition import rank_candidates
from .policies import pareto_frontier


@dataclass(frozen=True)
class SearchObservation:
    architecture_id: str
    predicted_mean: float
    predicted_std: float
    measured_score: float
    evidence_type: str
    metrics: dict[str, float] = field(default_factory=dict)


class LearnedSearch:
    """Connect proposal, predictor, acquisition, evaluation, and Pareto trace."""
    def __init__(self, proposer: Callable[[int], list[Architecture]],
                 predictor: Callable[[list[Architecture]], list[tuple[float, float]]],
                 evaluator: Callable[[Architecture], dict[str, float]], *, budget: int):
        if budget <= 0:
            raise ValueError("budget must be positive")
        self.proposer, self.predictor, self.evaluator, self.budget = proposer, predictor, evaluator, budget
        self.observations: list[SearchObservation] = []
        self.seen: set[str] = set()
        self.status = "created"

    def step(self, pool_size: int = 8) -> SearchObservation | None:
        if len(self.observations) >= self.budget:
            self.status = "completed"
            return None
        candidates = []
        for candidate in self.proposer(pool_size):
            candidate = validate_architecture(candidate)
            if candidate.content_hash() not in self.seen:
                self.seen.add(candidate.content_hash())
                candidates.append(candidate)
        if not candidates:
            self.status = "completed"
            return None
        incumbent = max((item.measured_score for item in self.observations), default=float("-inf"))
        predictions = self.predictor(candidates)
        if len(predictions) != len(candidates):
            raise ValueError("predictor must return one (mean, std) pair per candidate")
        ranked = rank_candidates([{"architecture": candidate, "predicted_mean": mean, "predicted_std": std}
                                  for candidate, (mean, std) in zip(candidates, predictions)], incumbent=incumbent if incumbent != float("-inf") else 0.0)
        selected = ranked[0]
        result = dict(self.evaluator(selected["architecture"]))
        score = float(result.get("score", result.get("validation_accuracy", 0.0)))
        observation = SearchObservation(selected["architecture"].content_hash(), float(selected["predicted_mean"]),
                                        float(selected["predicted_std"]), score,
                                        str(result.get("evidence_type", "measured")),
                                        {key: float(value) for key, value in result.items() if isinstance(value, (int, float))})
        self.observations.append(observation)
        self.status = "completed" if len(self.observations) >= self.budget else "running"
        return observation

    def run(self, pool_size: int = 8) -> list[SearchObservation]:
        self.status = "running"
        while len(self.observations) < self.budget and self.step(pool_size) is not None:
            pass
        if len(self.observations) >= self.budget or self.status == "completed":
            self.status = "completed"
        return list(self.observations)

    def pareto_frontier(self) -> list[dict[str, float]]:
        rows = []
        for item in self.observations:
            rows.append({"architecture_id": item.architecture_id, "accuracy": item.measured_score,
                         "parameters": float(item.metrics.get("parameters", 0.0))})
        return pareto_frontier(rows, maximize=("accuracy",), minimize=("parameters",))
