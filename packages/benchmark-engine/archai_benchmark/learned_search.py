"""Learned and multi-objective search policies over a finite NAS-Bench-201 index pool.

Every policy follows the ask/tell protocol of the baselines in `search.py`:
`ask()` returns an unobserved pool index (or None), and `tell()` receives only the
validation accuracy of that index (plus its static cost for the multi-objective
policy). None of them ever sees test accuracy. Learned models (ArchAI predictor,
ArchAI-V1 generator) are fitted online on in-budget observations only, so all
policies are compared at a matched query budget.
"""
from __future__ import annotations

import math
import random
from collections import deque
from collections.abc import Mapping, Sequence

from .nasbench201 import parse_architecture_string

NB201_OPS = ("none", "skip_connect", "nor_conv_1x1", "nor_conv_3x3", "avg_pool_3x3")


def cell_string(operations: Sequence[str]) -> str:
    """Inverse of `parse_architecture_string` for the six NAS-Bench-201 edges."""
    if len(operations) != 6:
        raise ValueError("NAS-Bench-201 cells have six edges")
    o = list(operations)
    return f"|{o[0]}~0|+|{o[1]}~0|{o[2]}~1|+|{o[3]}~0|{o[4]}~1|{o[5]}~2|"


class _PoolPolicy:
    def __init__(self, indices: Sequence[int], architecture_strings: Mapping[int, str], seed: int):
        if not indices:
            raise ValueError("at least one benchmark index is required")
        self._rng = random.Random(seed)
        self.seed = seed
        self._indices = list(dict.fromkeys(int(index) for index in indices))
        self._strings = {index: str(architecture_strings[index]) for index in self._indices}
        self._operations = {index: parse_architecture_string(encoding).operations
                            for index, encoding in self._strings.items()}
        self._by_operations = {operations: index for index, operations in self._operations.items()}
        self._observed: dict[int, float] = {}
        self._pending: set[int] = set()
        self.fallbacks = 0

    def _remaining(self) -> list[int]:
        return [index for index in self._indices if index not in self._observed and index not in self._pending]

    def _resolve(self, operations: Sequence[str]) -> int | None:
        index = self._by_operations.get(tuple(operations))
        if index is None or index in self._observed or index in self._pending:
            return None
        return index

    def _issue(self, index: int) -> int:
        self._pending.add(index)
        return index

    def _random_unobserved(self) -> int | None:
        remaining = self._remaining()
        if not remaining:
            return None
        self.fallbacks += 1
        return self._rng.choice(remaining)

    def _record(self, index: int, validation_accuracy: float) -> None:
        index = int(index)
        if index not in self._pending:
            raise ValueError("index must be returned by ask before tell")
        self._pending.discard(index)
        self._observed[index] = float(validation_accuracy)


class IndexREINFORCE(_PoolPolicy):
    """REINFORCE with an independent categorical per edge and an EMA reward baseline.

    This is the NAS-Bench-201 RL baseline design (per-edge softmax policy,
    exponential-moving-average baseline). The reward is validation accuracy in [0, 1].
    """

    def __init__(self, indices, architecture_strings, *, learning_rate: float = 0.5,
                 baseline_momentum: float = 0.9, max_resamples: int = 50, seed: int = 0):
        super().__init__(indices, architecture_strings, seed)
        if learning_rate <= 0 or not 0 <= baseline_momentum < 1 or max_resamples <= 0:
            raise ValueError("invalid REINFORCE parameters")
        self.learning_rate, self.baseline_momentum, self.max_resamples = learning_rate, baseline_momentum, max_resamples
        self.logits = [[0.0] * len(NB201_OPS) for _ in range(6)]
        self.baseline: float | None = None

    def probabilities(self) -> list[list[float]]:
        result = []
        for row in self.logits:
            peak = max(row)
            weights = [math.exp(value - peak) for value in row]
            total = sum(weights)
            result.append([weight / total for weight in weights])
        return result

    def ask(self) -> int | None:
        probabilities = self.probabilities()
        for _ in range(self.max_resamples):
            operations = [NB201_OPS[self._rng.choices(range(len(NB201_OPS)), weights=row)[0]] for row in probabilities]
            index = self._resolve(operations)
            if index is not None:
                return self._issue(index)
        index = self._random_unobserved()
        return None if index is None else self._issue(index)

    def tell(self, index: int, validation_accuracy: float) -> None:
        self._record(index, validation_accuracy)
        reward = float(validation_accuracy) / 100.0
        self.baseline = reward if self.baseline is None else (
            self.baseline_momentum * self.baseline + (1 - self.baseline_momentum) * reward)
        advantage = reward - self.baseline
        probabilities = self.probabilities()
        for edge, operation in enumerate(self._operations[int(index)]):
            chosen = NB201_OPS.index(operation)
            for token, probability in enumerate(probabilities[edge]):
                self.logits[edge][token] += self.learning_rate * advantage * ((token == chosen) - probability)


class IndexPredictorGuided(_PoolPolicy):
    """Greedy screening with the ArchAI graph performance predictor, refitted online.

    After `warmup` random queries, the predictor is retrained from scratch on all
    observations every `refit_every` new results; each step scores a random pool of
    `candidate_pool_size` unobserved cells and queries the highest predicted mean.
    """

    def __init__(self, indices, architecture_strings, *, warmup: int = 10, refit_every: int = 5,
                 epochs: int = 60, candidate_pool_size: int = 256, learning_rate: float = 3e-3, seed: int = 0):
        super().__init__(indices, architecture_strings, seed)
        if warmup <= 0 or refit_every <= 0 or epochs <= 0 or candidate_pool_size <= 0:
            raise ValueError("invalid predictor-guided parameters")
        self.warmup, self.refit_every, self.epochs = warmup, refit_every, epochs
        self.candidate_pool_size, self.learning_rate = candidate_pool_size, learning_rate
        self._model = None
        self._fitted_on = 0
        self._dags: dict[int, object] = {}
        self.refits = 0

    def _dag(self, index: int):
        if index not in self._dags:
            from archai_core.schema import TensorSpec

            from .nasbench201 import architecture_from_string
            self._dags[index] = architecture_from_string(self._strings[index],
                input_spec=TensorSpec(channels=3, height=32, width=32), output_classes=10)
        return self._dags[index]

    def _refit(self) -> None:
        import torch
        from archai_predictor.data import ArchitectureRecord
        from archai_predictor.model import PerformancePredictor, PredictorConfig
        from archai_predictor.training import fit_predictor
        torch.manual_seed(self.seed * 10_007 + len(self._observed))
        records = [ArchitectureRecord(self._dag(index), value / 100.0, (1.0,) + (0.0,) * 7, "in-budget")
                   for index, value in sorted(self._observed.items())]
        model = PerformancePredictor(PredictorConfig(dropout=0.0))
        fit_predictor(model, records, epochs=self.epochs, lr=self.learning_rate,
                      seed=self.seed + len(records), batch_size=32)
        model.eval()
        self._model, self._fitted_on = model, len(self._observed)
        self.refits += 1

    def predict(self, indices: Sequence[int]) -> list[float]:
        import torch
        from archai_predictor.data import ArchitectureRecord, collate_records
        records = [ArchitectureRecord(self._dag(index), 0.0, (1.0,) + (0.0,) * 7, "candidate") for index in indices]
        with torch.no_grad():
            features, mask, adjacency, tasks, _ = collate_records(records)
            return [float(value) for value in self._model(features, tasks, adjacency, mask)[:, 0]]

    def ask(self) -> int | None:
        remaining = self._remaining()
        if not remaining:
            return None
        if len(self._observed) < self.warmup:
            return self._issue(self._rng.choice(remaining))
        if self._model is None or len(self._observed) - self._fitted_on >= self.refit_every:
            self._refit()
        pool = remaining if len(remaining) <= self.candidate_pool_size else self._rng.sample(remaining, self.candidate_pool_size)
        scores = self.predict(pool)
        return self._issue(max(zip(pool, scores), key=lambda item: item[1])[0])

    def tell(self, index: int, validation_accuracy: float) -> None:
        self._record(index, validation_accuracy)


class IndexGeneratorGuided(_PoolPolicy):
    """Proposals from the ArchAI-V1 autoregressive generator, fine-tuned on in-budget elites.

    The generator (NAS-Bench-201 vocabulary) starts untrained. After `warmup` random
    queries it is fitted every `finetune_every` results on the top `elite_size`
    observed cells (likelihood weighted by rank), then sampled to propose unobserved
    cells. With `learn=False` the untrained generator is sampled throughout (ablation).
    """

    def __init__(self, indices, architecture_strings, *, warmup: int = 10, elite_size: int = 10,
                 finetune_every: int = 5, epochs: int = 40, samples_per_step: int = 64,
                 learning_rate: float = 1e-2, temperature: float = 1.0, learn: bool = True, seed: int = 0):
        super().__init__(indices, architecture_strings, seed)
        if min(warmup, elite_size, finetune_every, epochs, samples_per_step) <= 0 or temperature <= 0:
            raise ValueError("invalid generator-guided parameters")
        import torch
        from archai_generator.model import ArchitectureGenerator, GeneratorConfig
        torch.manual_seed(seed)
        self.model = ArchitectureGenerator(GeneratorConfig(latent_dim=8, hidden_dim=32, max_nodes=6,
                                                           condition_dim=1, vocabulary=NB201_OPS))
        self.optimizer = torch.optim.Adam(self.model.parameters(), lr=learning_rate)
        self.warmup, self.elite_size, self.finetune_every, self.epochs = warmup, elite_size, finetune_every, epochs
        self.samples_per_step, self.temperature, self.learn = samples_per_step, temperature, learn
        self._fitted_on = 0
        self._proposals: deque[int] = deque()
        self._draws = 0
        self.finetunes = 0

    def _finetune(self) -> None:
        from archai_generator.training import fit_sequences
        ranked = sorted(self._observed.items(), key=lambda item: item[1], reverse=True)[:self.elite_size]
        sequences = [list(self._operations[index]) for index, _ in ranked]
        weights = [float(self.elite_size - rank) for rank in range(len(ranked))]
        fit_sequences(self.model, sequences, conditions=[(1.0,)] * len(sequences), epochs=self.epochs,
                      seed=self.seed * 7919 + len(self._observed), optimizer=self.optimizer, weights=weights)
        self._fitted_on = len(self._observed)
        self.finetunes += 1
        self._proposals.clear()

    def _refill(self) -> None:
        self._draws += 1
        samples = self.model.sample_tokens(self.samples_per_step, steps=6, condition=(1.0,),
                                           seed=self.seed * 1_000_003 + self._draws, temperature=self.temperature)
        seen = set(self._proposals)
        for operations in samples:
            index = self._resolve(operations)
            if index is not None and index not in seen:
                self._proposals.append(index)
                seen.add(index)

    def ask(self) -> int | None:
        if not self._remaining():
            return None
        if len(self._observed) < self.warmup:
            return self._issue(self._rng.choice(self._remaining()))
        if self.learn and (self.finetunes == 0 or len(self._observed) - self._fitted_on >= self.finetune_every):
            self._finetune()
        while self._proposals:
            index = self._proposals.popleft()
            if index not in self._observed and index not in self._pending:
                return self._issue(index)
        self._refill()
        if self._proposals:
            return self._issue(self._proposals.popleft())
        index = self._random_unobserved()
        return None if index is None else self._issue(index)

    def tell(self, index: int, validation_accuracy: float) -> None:
        self._record(index, validation_accuracy)


def dominates(a: tuple[float, float], b: tuple[float, float]) -> bool:
    """(accuracy to maximize, cost to minimize)."""
    return a[0] >= b[0] and a[1] <= b[1] and (a[0] > b[0] or a[1] < b[1])


class IndexParetoEvolution(_PoolPolicy):
    """Multi-objective regularized evolution: maximize validation accuracy, minimize params.

    Parent selection takes a random non-dominated member of the tournament sample, so
    the population is pushed along the accuracy/cost Pareto front rather than toward
    accuracy alone. Costs are static cell properties revealed with each query.
    """

    uses_cost = True

    def __init__(self, indices, architecture_strings, *, population_size: int = 20, sample_size: int = 5,
                 cost_key: str = "params_m", seed: int = 0):
        super().__init__(indices, architecture_strings, seed)
        if population_size <= 0 or sample_size <= 0:
            raise ValueError("population_size and sample_size must be positive")
        self.population_size, self.sample_size, self.cost_key = population_size, sample_size, cost_key
        self._population: deque[tuple[int, float, float]] = deque()

    def _mutate(self, parent: int) -> int | None:
        operations = list(self._operations[parent])
        edge = self._rng.randrange(6)
        operations[edge] = self._rng.choice([op for op in NB201_OPS if op != operations[edge]])
        return self._resolve(operations)

    def ask(self) -> int | None:
        if not self._remaining():
            return None
        candidate = None
        if len(self._population) >= self.population_size:
            sample = self._rng.sample(list(self._population), min(self.sample_size, len(self._population)))
            front = [item for item in sample if not any(dominates((o[1], o[2]), (item[1], item[2])) for o in sample)]
            parent = self._rng.choice(front)[0]
            for _ in range(30):
                candidate = self._mutate(parent)
                if candidate is not None:
                    break
        if candidate is None:
            candidate = self._rng.choice(self._remaining())
        return self._issue(candidate)

    def tell(self, index: int, validation_accuracy: float, cost: Mapping[str, float] | None = None) -> None:
        if cost is None or self.cost_key not in cost:
            raise ValueError(f"multi-objective search needs the {self.cost_key!r} cost of every result")
        self._record(index, validation_accuracy)
        self._population.append((int(index), float(validation_accuracy), float(cost[self.cost_key])))
        while len(self._population) > self.population_size:
            self._population.popleft()
