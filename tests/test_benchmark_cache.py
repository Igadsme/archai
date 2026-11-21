from archai_benchmark.adapter import BenchmarkRecord, NATSBenchAdapter
from archai_benchmark.cache import BenchmarkCache
from archai_benchmark.manifest import load_manifest
from archai_benchmark.search import BenchmarkEvaluator, IndexRandomSearch, QueryBudget


class FakeNATS:
    def arch(self, index):
        return f"|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|"

    def get_more_info(self, index, dataset, hp, is_random):
        return {"valid-accuracy": 80.0 + index, "test-accuracy": 79.0 + index, "train-all-time": 1.5}


class SeedAwareNATS(FakeNATS):
    def __init__(self):
        self.requested_trial_seeds = []

    def query_meta_info_by_index(self, index, hp):
        class Metadata:
            @staticmethod
            def get_dataset_seeds(_dataset):
                return [777, 888, 999]
        return Metadata()

    def get_more_info(self, index, dataset, hp, is_random):
        self.requested_trial_seeds.append(is_random)
        return super().get_more_info(index, dataset, hp, is_random)


def test_adapter_and_cache_preserve_architecture_string(tmp_path):
    adapter = NATSBenchAdapter("unused")
    adapter._api = FakeNATS()
    record = adapter.query(2, seed=1)
    assert record.architecture_string.startswith("|skip_connect")
    cache = BenchmarkCache(tmp_path / "cache.sqlite")
    cache.put(record)
    assert cache.get(2, "cifar10", 1) == record
    cache.close()


def test_adapter_maps_run_seed_to_available_benchmark_trial_seed():
    adapter = NATSBenchAdapter("unused")
    backend = SeedAwareNATS()
    adapter._api = backend
    record = adapter.query(2, seed=4)
    assert backend.requested_trial_seeds == [888]
    assert record.benchmark_trial_seed == 888
    assert record.seed == 4


def test_cached_query_does_not_consume_new_budget(tmp_path):
    adapter = NATSBenchAdapter("unused")
    adapter._api = FakeNATS()
    cache = BenchmarkCache(tmp_path / "cache.sqlite")
    evaluator = BenchmarkEvaluator(adapter, QueryBudget(1), cache)
    first = evaluator.evaluate_index(3, seed=0)
    second = evaluator.evaluate_index(3, seed=0)
    assert first == second
    assert evaluator.queries == 1


def test_unresolved_manifest_is_not_ready_for_download():
    manifest = load_manifest("datasets/manifests/natsbench201.json")
    assert manifest.sha256 is None


def test_index_random_search_is_seeded_and_budgetable():
    left = IndexRandomSearch(range(5), seed=12)
    right = IndexRandomSearch(range(5), seed=12)
    assert [left.ask() for _ in range(5)] == [right.ask() for _ in range(5)]
    assert left.ask() is None
