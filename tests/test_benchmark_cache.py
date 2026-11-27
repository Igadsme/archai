from archai_benchmark.adapter import NATSBenchAdapter
from archai_benchmark.cache import BenchmarkCache
from archai_benchmark.manifest import load_manifest
from archai_benchmark.search import BenchmarkEvaluator, IndexRandomSearch, QueryBudget


class FakeNATS:
    def arch(self, index):
        return "|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|"

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
    assert backend.requested_trial_seeds == [888, 888]  # cifar10-valid validation + cifar10 test
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


def test_committed_manifest_pins_a_checksum_before_download():
    manifest = load_manifest("datasets/manifests/natsbench201.json")
    assert manifest.sha256 is not None and len(manifest.sha256) == 64
    assert manifest.search_space == "tss"


def test_index_random_search_is_seeded_and_budgetable():
    left = IndexRandomSearch(range(5), seed=12)
    right = IndexRandomSearch(range(5), seed=12)
    assert [left.ask() for _ in range(5)] == [right.ask() for _ in range(5)]
    assert left.ask() is None


class SplitAwareNATS:
    """Mirrors real NATS-Bench TSS keys: `cifar10` has no validation split."""
    def __init__(self):
        self.requests = []

    def arch(self, index):
        return FakeNATS().arch(index)

    def get_more_info(self, index, dataset, hp, is_random):
        self.requests.append(dataset)
        if dataset == "cifar10":
            return {"test-accuracy": 93.0, "train-all-time": 2.0}
        return {"valid-accuracy": 90.0, "test-accuracy": 89.0, "train-all-time": 1.0}


def test_cifar10_selects_on_cifar10_valid_and_reports_cifar10_test():
    adapter = NATSBenchAdapter("unused", dataset="cifar10")
    adapter._api = SplitAwareNATS()
    record = adapter.query(0)
    assert adapter._api.requests == ["cifar10-valid", "cifar10"]
    assert (record.validation_accuracy, record.test_accuracy) == (90.0, 93.0)
    assert NATSBenchAdapter.metric_sources("cifar100") == ("cifar100", "cifar100")


def test_adapter_refuses_split_without_validation_accuracy():
    import pytest
    from archai_benchmark.adapter import BenchmarkUnavailable

    class NoValidation(SplitAwareNATS):
        def get_more_info(self, index, dataset, hp, is_random):
            return {"test-accuracy": 1.0}
    adapter = NATSBenchAdapter("unused", dataset="cifar100")
    adapter._api = NoValidation()
    with pytest.raises(BenchmarkUnavailable, match="no validation accuracy"):
        adapter.query(0)


def test_tree_digest_is_deterministic_and_content_sensitive(tmp_path):
    from archai_benchmark.integrity import sha256_path, sha256_tree
    root = tmp_path / "archive"
    (root / "sub").mkdir(parents=True)
    (root / "a.bin").write_bytes(b"a")
    (root / "sub" / "b.bin").write_bytes(b"b")
    first = sha256_tree(root)
    assert sha256_path(root) == first and len(first) == 64
    (root / "sub" / "b.bin").write_bytes(b"changed")
    assert sha256_tree(root) != first
    assert sha256_path(root / "a.bin") == __import__("hashlib").sha256(b"a").hexdigest()
