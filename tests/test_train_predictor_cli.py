from archai_benchmark.adapter import BenchmarkRecord
from scripts.train_predictor import collect_records


class FakeAdapter:
    def query(self, index, seed):
        return BenchmarkRecord(index, "cifar10", seed, 80.0 + index, 79.0 + index, 1.0,
                               architecture_string="|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|")


def test_cli_record_collection_preserves_units_and_provenance():
    records = collect_records(FakeAdapter(), [1, 2], seed=3, dataset="cifar10")
    assert records[0].target == 0.81
    assert records[0].source == "NATS-Bench"
    assert records[0].task_features[0] == 1.0
