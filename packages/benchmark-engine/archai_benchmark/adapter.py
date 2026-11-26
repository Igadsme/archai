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
    benchmark_trial_seed: int | None = None


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
        trial_seed = self._resolve_trial_seed(architecture_index, seed)
        is_random = trial_seed if trial_seed is not None else seed
        validation_dataset, test_dataset = self.metric_sources(self.dataset)
        validation_info = self._api.get_more_info(architecture_index, validation_dataset, hp=200,
                                                  is_random=is_random)
        test_info = (validation_info if test_dataset == validation_dataset else
                     self._api.get_more_info(architecture_index, test_dataset, hp=200,
                                             is_random=is_random))
        if "valid-accuracy" not in validation_info:
            raise BenchmarkUnavailable(
                f"benchmark split {validation_dataset!r} exposes no validation accuracy")
        architecture_string = self.architecture_string(architecture_index)
        return BenchmarkRecord(architecture_index, self.dataset, seed,
                               float(validation_info["valid-accuracy"]),
                               float(test_info["test-accuracy"]),
                               float(validation_info.get("train-all-time", 0.0)),
                               architecture_string=architecture_string,
                               benchmark_trial_seed=trial_seed)

    def cost(self, architecture_index: int) -> dict[str, float]:
        """Static cost of a cell (parameters and FLOPs in millions, benchmark latency in seconds).

        These are properties of the architecture, not training outcomes.
        """
        if self._api is None:
            raise BenchmarkUnavailable("adapter is not open")
        validation_dataset, _ = self.metric_sources(self.dataset)
        info = self._api.get_cost_info(architecture_index, validation_dataset, hp=200)
        return {"params_m": float(info["params"]), "flops_m": float(info["flops"]),
                "latency_s": float(info["latency"])}

    @staticmethod
    def metric_sources(dataset: str) -> tuple[str, str]:
        """(validation split, test split) following the NAS-Bench-201/NATS-Bench protocol.

        NATS-Bench `cifar10` records are trained on the full training set and expose no
        validation accuracy, so CIFAR-10 searches select on `cifar10-valid` validation
        accuracy and report the `cifar10` held-out test accuracy separately.
        """
        if dataset == "cifar10":
            return "cifar10-valid", "cifar10"
        return dataset, dataset

    def _resolve_trial_seed(self, architecture_index: int, seed: int) -> int | None:
        """Map a reproducibility seed to one of the archive's actual trial seeds."""
        query_meta = getattr(self._api, "query_meta_info_by_index", None)
        if query_meta is None:
            # Lightweight test doubles and compatible adapters may not expose
            # trial metadata; preserve their existing integer-seed contract.
            return None
        try:
            metadata = query_meta(architecture_index, hp=200)
            available = [int(value) for value in metadata.get_dataset_seeds(self.dataset)]
        except (AttributeError, KeyError, TypeError, ValueError) as exc:
            raise BenchmarkUnavailable(
                f"benchmark does not expose trial seeds for dataset {self.dataset!r}"
            ) from exc
        if not available:
            raise BenchmarkUnavailable(f"benchmark has no trial seeds for dataset {self.dataset!r}")
        return available[int(seed) % len(available)]

    def architecture_string(self, architecture_index: int) -> str:
        if self._api is None:
            raise BenchmarkUnavailable("adapter is not open")
        value = self._api.arch(architecture_index)
        if not isinstance(value, str):
            raise TypeError("NATS-Bench backend returned a non-string architecture encoding")
        return value
