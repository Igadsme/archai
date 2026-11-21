import pytest

from archai_benchmark.adapter import BenchmarkRecord
from scripts.train_predictor import collect_records, main


class FakeAdapter:
    def query(self, index, seed):
        return BenchmarkRecord(index, "cifar10", seed, 80.0 + index, 79.0 + index, 1.0,
                               architecture_string="|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|")


def test_cli_record_collection_preserves_units_and_provenance():
    records = collect_records(FakeAdapter(), [1, 2], seed=3, dataset="cifar10")
    assert records[0].target == 0.81
    assert records[0].source == "NATS-Bench"
    assert records[0].task_features[0] == 1.0


def test_predictor_cli_rejects_archive_checksum_mismatch(tmp_path, monkeypatch):
    archive = tmp_path / "archive.bin"
    archive.write_bytes(b"archive")
    monkeypatch.setattr("sys.argv", ["train_predictor", "--benchmark-path", str(archive),
        "--benchmark-sha256", "0" * 64, "--indices", "1,2,3", "--checkpoint",
        str(tmp_path / "model.pt"), "--report", str(tmp_path / "report.json")])
    with pytest.raises(SystemExit):
        main()
