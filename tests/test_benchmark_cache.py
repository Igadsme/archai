from archai_benchmark.adapter import BenchmarkRecord, NATSBenchAdapter
from archai_benchmark.cache import BenchmarkCache
from archai_benchmark.manifest import load_manifest
from archai_benchmark.search import BenchmarkEvaluator, QueryBudget


class FakeNATS:
    def arch(self, index):
        return f"|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|"

    def get_more_info(self, index, dataset, hp, is_random):
        return {"valid-accuracy": 80.0 + index, "test-accuracy": 79.0 + index, "train-all-time": 1.5}


def test_adapter_and_cache_preserve_architecture_string(tmp_path):
    adapter = NATSBenchAdapter("unused")
    adapter._api = FakeNATS()
    record = adapter.query(2, seed=1)
    assert record.architecture_string.startswith("|skip_connect")
    cache = BenchmarkCache(tmp_path / "cache.sqlite")
    cache.put(record)
    assert cache.get(2, "cifar10", 1) == record
    cache.close()


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
