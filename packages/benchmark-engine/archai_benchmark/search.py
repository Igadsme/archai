from __future__ import annotations

from dataclasses import dataclass

from archai_core.schema import Architecture
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
