from __future__ import annotations

import random
import re
from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .adapter import BenchmarkRecord, NATSBenchAdapter
from .cache import BenchmarkCache


@dataclass(frozen=True)
class QueryBudget:
    max_queries: int


class BenchmarkEvaluator:
    def __init__(self, adapter: NATSBenchAdapter, budget: QueryBudget, cache: BenchmarkCache | None = None):
        self.adapter, self.budget, self.cache = adapter, budget, cache
        self.queries = 0
        self.results: list[BenchmarkRecord] = []

    def evaluate_index(self, architecture_index: int, seed: int = 0) -> BenchmarkRecord:
        if self.cache:
            cached = self.cache.get(architecture_index, self.adapter.dataset, seed)
            if cached is not None:
                return cached
        if self.queries >= self.budget.max_queries:
            raise RuntimeError("benchmark query budget exhausted")
        record = self.adapter.query(architecture_index, seed)
        self.queries += 1
        self.results.append(record)
        if self.cache:
            self.cache.put(record)
        return record


class IndexRandomSearch:
    """Reproducible random search over benchmark indices under a fixed budget."""
    def __init__(self, indices, *, seed: int = 0):
        import random
        self._rng = random.Random(seed)
        self._indices = list(indices)
        self._rng.shuffle(self._indices)
        self._position = 0

    def ask(self) -> int | None:
        if self._position >= len(self._indices):
            return None
        index = self._indices[self._position]
        self._position += 1
        return index


class IndexRegularizedEvolution:
    """Regularized evolution over a finite NAS-Bench-201 index pool.

    The benchmark exposes architecture strings separately from metric queries.
    This policy uses those strings to mutate one operation in a sampled parent,
    then resolves the child back into the supplied finite pool.  If a mutation
    is not represented in the pool it falls back to an unobserved candidate,
    keeping the policy reproducible and budget-safe.
    """

    _operation = re.compile(r"\|([^~|]+)~(\d+)")
    _operations = ("nor_conv_1x1", "nor_conv_3x3", "avg_pool_3x3", "skip_connect", "none")

    def __init__(self, indices: Sequence[int], architecture_strings: Mapping[int, str], *,
                 population_size: int = 8, sample_size: int = 3, seed: int = 0):
        if not indices:
            raise ValueError("at least one benchmark index is required")
        if population_size <= 0 or sample_size <= 0:
            raise ValueError("population_size and sample_size must be positive")
        from .nasbench201 import parse_architecture_string

        self._rng = random.Random(seed)
        self._indices = list(dict.fromkeys(int(index) for index in indices))
        self._strings = {int(index): str(architecture_strings[index]) for index in self._indices}
        for encoding in self._strings.values():
            parse_architecture_string(encoding)
        self._by_encoding = {encoding: index for index, encoding in self._strings.items()}
        self.population_size = population_size
        self.sample_size = sample_size
        self._population: deque[tuple[int, float]] = deque()
        self._observed: set[int] = set()

    def _mutate(self, parent: int) -> int | None:
        encoding = self._strings[parent]
        matches = list(self._operation.finditer(encoding))
        if not matches:
            return None
        position = self._rng.randrange(len(matches))
        match = matches[position]
        choices = [operation for operation in self._operations if operation != match.group(1)]
        replacement = self._rng.choice(choices)
        child_encoding = encoding[:match.start(1)] + replacement + encoding[match.end(1):]
        child = self._by_encoding.get(child_encoding)
        return child if child not in self._observed else None

    def ask(self) -> int | None:
        remaining = [index for index in self._indices if index not in self._observed]
        if not remaining:
            return None
        candidate: int | None = None
        if len(self._population) >= self.population_size:
            sample = self._rng.sample(list(self._population), min(self.sample_size, len(self._population)))
            parent, _score = max(sample, key=lambda item: item[1])
            for _ in range(len(self._operations) * 6):
                candidate = self._mutate(parent)
                if candidate is not None:
                    break
        if candidate is None or candidate not in remaining:
            candidate = self._rng.choice(remaining)
        self._observed.add(candidate)
        return candidate

    def tell(self, index: int, validation_accuracy: float) -> None:
        index = int(index)
        if index not in self._observed:
            raise ValueError("index must be returned by ask before tell")
        self._population.append((index, float(validation_accuracy)))
        while len(self._population) > self.population_size:
            self._population.popleft()
