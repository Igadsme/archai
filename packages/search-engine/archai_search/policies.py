from __future__ import annotations

import random
from collections import deque
from dataclasses import dataclass
from typing import Callable, Iterable

from archai_core.schema import Architecture
from archai_core.validation import validate_architecture


@dataclass(frozen=True)
class Evaluation:
    architecture_id: str
    score: float
    measured: bool = False


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
                 sample_size: int = 3, seed: int = 0):
        self.generator, self.population_size, self.sample_size = generator, population_size, sample_size
        self.rng = random.Random(seed)
        self.population: deque[Evaluation] = deque()
        self.architectures: dict[str, Architecture] = {}

    def ask(self) -> Architecture:
        if len(self.population) < self.population_size:
            candidate = validate_architecture(self.generator())
        else:
            sample = self.rng.sample(list(self.population), min(self.sample_size, len(self.population)))
            winner = max(sample, key=lambda x: x.score)
            candidate = validate_architecture(self.generator())
            self.architectures.setdefault(winner.architecture_id, self.architectures.get(winner.architecture_id))
        return candidate

    def tell(self, architecture: Architecture, score: float, measured: bool = False) -> None:
        architecture = validate_architecture(architecture)
        self.architectures[architecture.content_hash()] = architecture
        self.population.append(Evaluation(architecture.content_hash(), score, measured))
        while len(self.population) > self.population_size:
            self.population.popleft()


def pareto_frontier(rows: Iterable[dict[str, float]], maximize: tuple[str, ...], minimize: tuple[str, ...]) -> list[dict[str, float]]:
    rows = list(rows)
    def dominates(a, b):
        better_or_equal = all(a[k] >= b[k] for k in maximize) and all(a[k] <= b[k] for k in minimize)
        strictly_better = any(a[k] > b[k] for k in maximize) or any(a[k] < b[k] for k in minimize)
        return better_or_equal and strictly_better
    return [row for row in rows if not any(dominates(other, row) for other in rows if other is not row)]
