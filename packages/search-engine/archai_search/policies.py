from __future__ import annotations

import random
import math
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable

from archai_core.schema import Architecture, OP_TYPES
from archai_core.validation import validate_architecture


@dataclass(frozen=True)
class Evaluation:
    architecture_id: str
    score: float
    measured: bool = False


def mutate_architecture(parent: Architecture, rng: random.Random) -> Architecture:
    """Apply one validity-preserving mutation to a supported graph."""
    mutable = [node for node in parent.nodes if node.op not in {"input", "output"}]
    if not mutable:
        return parent
    target = rng.choice(mutable)
    choices = sorted(OP_TYPES - {"input", "output"} - {target.op})
    replacement = rng.choice(choices)
    nodes = [node.model_copy(update={"op": replacement}) if node.id == target.id else node for node in parent.nodes]
    return parent.model_copy(update={"nodes": nodes, "generator_version": "regularized-evolution"})


class RandomSearch:
    def __init__(self, candidates: Iterable[Architecture], seed: int = 0):
        self._rng = random.Random(seed)
        self._pool = [validate_architecture(c) for c in candidates]
        self._seen: set[str] = set()

    def ask(self) -> Architecture | None:
        remaining = [c for c in self._pool if c.content_hash() not in self._seen]
        if not remaining:
            return None
        candidate = self._rng.choice(remaining)
        self._seen.add(candidate.content_hash())
        return candidate


class RegularizedEvolution:
    def __init__(self, generator: Callable[[], Architecture], population_size: int = 8,
                 sample_size: int = 3, seed: int = 0,
                 mutator: Callable[[Architecture, random.Random], Architecture] | None = mutate_architecture):
        self.generator, self.population_size, self.sample_size = generator, population_size, sample_size
        self.mutator = mutator
        self.rng = random.Random(seed)
        self.population: deque[Evaluation] = deque()
        self.architectures: dict[str, Architecture] = {}

    def ask(self) -> Architecture:
        if len(self.population) < self.population_size:
            candidate = validate_architecture(self.generator())
        else:
            sample = self.rng.sample(list(self.population), min(self.sample_size, len(self.population)))
            winner = max(sample, key=lambda x: x.score)
            parent = self.architectures[winner.architecture_id]
            candidate = validate_architecture(self.mutator(parent, self.rng) if self.mutator else self.generator())
        return candidate

    def tell(self, architecture: Architecture, score: float, measured: bool = False) -> None:
        architecture = validate_architecture(architecture)
        self.architectures[architecture.content_hash()] = architecture
        self.population.append(Evaluation(architecture.content_hash(), score, measured))
        while len(self.population) > self.population_size:
            self.population.popleft()


class BayesianOptimization:
    """Dependency-light kernel/UCB baseline over a finite candidate pool."""
    def __init__(self, candidates: Iterable[Architecture], *, feature_fn: Callable[[Architecture], list[float]] | None = None,
                 seed: int = 0, warmup: int = 3, beta: float = 2.0):
        self.rng = random.Random(seed)
        self.candidates = [validate_architecture(candidate) for candidate in candidates]
        self.feature_fn = feature_fn or (lambda candidate: [float(len(candidate.nodes)), float(len(candidate.edges)),
                                                            float(sum(node.channels for node in candidate.nodes))])
        self.features = {candidate.content_hash(): self.feature_fn(candidate) for candidate in self.candidates}
        self.observations: dict[str, float] = {}
        self.warmup, self.beta = warmup, beta

    @staticmethod
    def _kernel(left: list[float], right: list[float]) -> float:
        return math.exp(-sum((a - b) ** 2 for a, b in zip(left, right)) / 2.0)

    def ask(self) -> Architecture | None:
        remaining = [candidate for candidate in self.candidates if candidate.content_hash() not in self.observations]
        if not remaining:
            return None
        if len(self.observations) < self.warmup:
            return self.rng.choice(remaining)
        scored = []
        for candidate in remaining:
            feature = self.features[candidate.content_hash()]
            weights = [(self._kernel(feature, self.features[observed_id]), value)
                       for observed_id, value in self.observations.items()]
            total_weight = sum(weight for weight, _ in weights)
            mean_prediction = sum(weight * value for weight, value in weights) / total_weight if total_weight else 0.0
            uncertainty = 1.0 / math.sqrt(1.0 + total_weight)
            scored.append((mean_prediction + self.beta * uncertainty, candidate))
        return max(scored, key=lambda item: item[0])[1]

    def tell(self, candidate: Architecture, score: float) -> None:
        candidate = validate_architecture(candidate)
        identifier = candidate.content_hash()
        if identifier not in self.features:
            raise ValueError("candidate was not part of this finite search pool")
        if identifier in self.observations:
            raise ValueError("candidate has already been evaluated")
        self.observations[identifier] = float(score)


def pareto_frontier(rows: Iterable[dict[str, float]], maximize: tuple[str, ...], minimize: tuple[str, ...]) -> list[dict[str, float]]:
    rows = list(rows)
    def dominates(a, b):
        better_or_equal = all(a[k] >= b[k] for k in maximize) and all(a[k] <= b[k] for k in minimize)
        strictly_better = any(a[k] > b[k] for k in maximize) or any(a[k] < b[k] for k in minimize)
        return better_or_equal and strictly_better
    return [row for row in rows if not any(dominates(other, row) for other in rows if other is not row)]
