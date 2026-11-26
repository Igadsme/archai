from __future__ import annotations

import math
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


class IndexBayesianOptimization:
    """Gaussian-process UCB baseline over a finite NAS-Bench-201 index pool.

    Dependency-free: each cell is encoded by its six edge operations, the kernel is
    `exp(-hamming / lengthscale)` (positive definite on one-hot encodings), and
    validation accuracies are standardised before an exact GP posterior is computed
    with a pure-Python Cholesky factorisation. To stay CPU-small on 15,625 cells,
    every `ask` scores a seeded random subset of `candidate_pool_size` unobserved
    cells. Only validation accuracy is ever passed to `tell`.
    """

    _operation = re.compile(r"\|([^~|]+)~(\d+)")

    def __init__(self, indices: Sequence[int], architecture_strings: Mapping[int, str], *,
                 seed: int = 0, warmup: int = 5, beta: float = 2.0, lengthscale: float = 2.0,
                 noise: float = 1e-3, candidate_pool_size: int = 512):
        if not indices:
            raise ValueError("at least one benchmark index is required")
        if warmup <= 0 or candidate_pool_size <= 0 or lengthscale <= 0 or noise <= 0 or beta < 0:
            raise ValueError("warmup, candidate_pool_size, lengthscale and noise must be positive; beta >= 0")
        from .nasbench201 import parse_architecture_string

        self._rng = random.Random(seed)
        self._indices = list(dict.fromkeys(int(index) for index in indices))
        self._codes: dict[int, tuple[str, ...]] = {}
        for index in self._indices:
            encoding = str(architecture_strings[index])
            parse_architecture_string(encoding)
            self._codes[index] = tuple(match.group(1) for match in self._operation.finditer(encoding))
        self.warmup, self.beta, self.lengthscale, self.noise = warmup, beta, lengthscale, noise
        self.candidate_pool_size = candidate_pool_size
        self._pending: set[int] = set()
        self._observed: dict[int, float] = {}

    def _kernel(self, left: int, right: int) -> float:
        distance = sum(a != b for a, b in zip(self._codes[left], self._codes[right]))
        return math.exp(-distance / self.lengthscale)

    @staticmethod
    def _cholesky(matrix: list[list[float]]) -> list[list[float]]:
        size = len(matrix)
        lower = [[0.0] * size for _ in range(size)]
        for i in range(size):
            for j in range(i + 1):
                total = matrix[i][j] - sum(lower[i][k] * lower[j][k] for k in range(j))
                lower[i][j] = math.sqrt(max(total, 1e-12)) if i == j else total / lower[j][j]
        return lower

    @staticmethod
    def _solve_lower(lower: list[list[float]], vector: list[float]) -> list[float]:
        result: list[float] = []
        for i, value in enumerate(vector):
            result.append((value - sum(lower[i][k] * result[k] for k in range(i))) / lower[i][i])
        return result

    @staticmethod
    def _solve_upper_from_lower(lower: list[list[float]], vector: list[float]) -> list[float]:
        size = len(vector)
        result = [0.0] * size
        for i in reversed(range(size)):
            total = vector[i] - sum(lower[k][i] * result[k] for k in range(i + 1, size))
            result[i] = total / lower[i][i]
        return result

    def posterior(self, candidates: Sequence[int]) -> list[tuple[float, float]]:
        """(mean, std) of standardised validation accuracy for each candidate."""
        observed = list(self._observed)
        values = [self._observed[index] for index in observed]
        mean_value = sum(values) / len(values)
        spread = math.sqrt(sum((value - mean_value) ** 2 for value in values) / len(values)) or 1.0
        targets = [(value - mean_value) / spread for value in values]
        gram = [[self._kernel(a, b) + (self.noise if i == j else 0.0)
                 for j, b in enumerate(observed)] for i, a in enumerate(observed)]
        lower = self._cholesky(gram)
        alpha = self._solve_upper_from_lower(lower, self._solve_lower(lower, targets))
        result = []
        for candidate in candidates:
            cross = [self._kernel(candidate, index) for index in observed]
            mean = sum(weight * coefficient for weight, coefficient in zip(cross, alpha))
            projection = self._solve_lower(lower, cross)
            variance = max(1.0 - sum(value * value for value in projection), 1e-12)
            result.append((mean, math.sqrt(variance)))
        return result

    def ask(self) -> int | None:
        remaining = [index for index in self._indices
                     if index not in self._observed and index not in self._pending]
        if not remaining:
            return None
        if len(self._observed) < self.warmup:
            choice = self._rng.choice(remaining)
        else:
            pool = (remaining if len(remaining) <= self.candidate_pool_size
                    else self._rng.sample(remaining, self.candidate_pool_size))
            scores = self.posterior(pool)
            choice = max(zip(pool, scores), key=lambda item: item[1][0] + self.beta * item[1][1])[0]
        self._pending.add(choice)
        return choice

    def tell(self, index: int, validation_accuracy: float) -> None:
        index = int(index)
        if index not in self._pending:
            raise ValueError("index must be returned by ask before tell")
        self._pending.discard(index)
        self._observed[index] = float(validation_accuracy)
