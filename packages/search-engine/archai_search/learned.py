from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

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
                 evaluator: Callable[[Architecture], dict[str, float]], *, budget: int,
                 state_path: str | Path | None = None):
        if budget <= 0:
            raise ValueError("budget must be positive")
        self.proposer, self.predictor, self.evaluator, self.budget = proposer, predictor, evaluator, budget
        self.state_path = Path(state_path) if state_path is not None else None
        self.observations: list[SearchObservation] = []
        self.seen: set[str] = set()
        self.status = "created"
        self._cancel_requested = False
        self._load()

    def _persist(self) -> None:
        if self.state_path is None:
            return
        payload = {"status": self.status, "seen": sorted(self.seen),
                   "observations": [{"architecture_id": item.architecture_id,
                                     "predicted_mean": item.predicted_mean,
                                     "predicted_std": item.predicted_std,
                                     "measured_score": item.measured_score,
                                     "evidence_type": item.evidence_type,
                                     "metrics": item.metrics} for item in self.observations]}
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.state_path.with_suffix(self.state_path.suffix + ".partial")
        temporary.write_text(json.dumps(payload, sort_keys=True, indent=2))
        temporary.replace(self.state_path)

    def _load(self) -> None:
        if self.state_path is None or not self.state_path.exists():
            return
        payload = json.loads(self.state_path.read_text())
        self.observations = [SearchObservation(
            architecture_id=str(item["architecture_id"]),
            predicted_mean=float(item["predicted_mean"]),
            predicted_std=float(item["predicted_std"]),
            measured_score=float(item["measured_score"]),
            evidence_type=str(item["evidence_type"]),
            metrics={str(key): float(value) for key, value in item.get("metrics", {}).items()},
        ) for item in payload.get("observations", [])]
        self.seen = {str(identifier) for identifier in payload.get("seen", [])}
        self.status = str(payload.get("status", "created"))
        if self.status == "cancel_requested":
            self._cancel_requested = True

    def cancel(self) -> None:
        self._cancel_requested = True
        self.status = "cancel_requested"
        self._persist()

    def resume(self) -> None:
        if self.status in {"completed", "cancelled"} and len(self.observations) >= self.budget:
            return
        self._cancel_requested = False
        self.status = "created"
        self._persist()

    def step(self, pool_size: int = 8) -> SearchObservation | None:
        if self._cancel_requested:
            self.status = "cancelled"
            self._persist()
            return None
        if len(self.observations) >= self.budget:
            self.status = "completed"
            self._persist()
            return None
        candidates = []
        for candidate in self.proposer(pool_size):
            candidate = validate_architecture(candidate)
            if candidate.content_hash() not in self.seen:
                self.seen.add(candidate.content_hash())
                candidates.append(candidate)
        if not candidates:
            self.status = "completed"
            self._persist()
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
        self._persist()
        self.status = "completed" if len(self.observations) >= self.budget else "running"
        self._persist()
        return observation

    def run(self, pool_size: int = 8) -> list[SearchObservation]:
        if self._cancel_requested:
            self.status = "cancelled"
            self._persist()
            return list(self.observations)
        self.status = "running"
        self._persist()
        while len(self.observations) < self.budget and self.step(pool_size) is not None:
            pass
        if self._cancel_requested:
            self.status = "cancelled"
        elif len(self.observations) >= self.budget or self.status == "completed":
            self.status = "completed"
        self._persist()
        return list(self.observations)

    def pareto_frontier(self) -> list[dict[str, float]]:
        rows = []
        for item in self.observations:
            rows.append({"architecture_id": item.architecture_id, "accuracy": item.measured_score,
                         "parameters": float(item.metrics.get("parameters", 0.0))})
        return pareto_frontier(rows, maximize=("accuracy",), minimize=("parameters",))
