from archai_benchmark.adapter import BenchmarkRecord
from scripts.run_benchmark_search import select_best_validation


def test_benchmark_baseline_selects_only_validation():
    records = [BenchmarkRecord(1, "cifar10", 0, 80.0, 99.0, 1.0),
               BenchmarkRecord(2, "cifar10", 0, 81.0, 70.0, 1.0)]
    assert select_best_validation(records).architecture_index == 2
