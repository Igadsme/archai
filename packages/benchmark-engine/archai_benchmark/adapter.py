from __future__ import annotations

from dataclasses import dataclass


class BenchmarkUnavailable(RuntimeError):
    pass


@dataclass(frozen=True)
class BenchmarkRecord:
    architecture_index: int
    dataset: str
    seed: int
    validation_accuracy: float
    test_accuracy: float
    training_time_seconds: float | None
    source: str = "NATS-Bench"
    architecture_string: str | None = None


class NATSBenchAdapter:
    def __init__(self, path: str, search_space: str = "tss", dataset: str = "cifar10"):
        self.path, self.search_space, self.dataset = path, search_space, dataset
        self._api = None

    def open(self):
        try:
            from nats_bench import create
        except ImportError as exc:
            raise BenchmarkUnavailable("install the benchmark extra") from exc
        self._api = create(self.path, self.search_space, fast_mode=True, verbose=False)
        return self

    def query(self, architecture_index: int, seed: int = 0) -> BenchmarkRecord:
        if self._api is None:
            raise BenchmarkUnavailable("adapter is not open")
        info = self._api.get_more_info(architecture_index, self.dataset, hp=200, is_random=seed)
        architecture_string = self.architecture_string(architecture_index)
        return BenchmarkRecord(architecture_index, self.dataset, seed,
                               float(info["valid-accuracy"]), float(info["test-accuracy"]),
                               float(info.get("train-all-time", 0.0)), architecture_string=architecture_string)

    def architecture_string(self, architecture_index: int) -> str:
        if self._api is None:
            raise BenchmarkUnavailable("adapter is not open")
        value = self._api.arch(architecture_index)
        if not isinstance(value, str):
            raise TypeError("NATS-Bench backend returned a non-string architecture encoding")
        return value
