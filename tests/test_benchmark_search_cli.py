import pytest

from archai_benchmark.adapter import BenchmarkRecord
from scripts.run_benchmark_search import main, select_best_validation


def test_benchmark_baseline_selects_only_validation():
    records = [BenchmarkRecord(1, "cifar10", 0, 80.0, 99.0, 1.0),
               BenchmarkRecord(2, "cifar10", 0, 81.0, 70.0, 1.0)]
    assert select_best_validation(records).architecture_index == 2


def test_benchmark_cli_rejects_archive_checksum_mismatch(tmp_path, monkeypatch):
    archive = tmp_path / "archive.bin"
    archive.write_bytes(b"archive")
    monkeypatch.setattr("sys.argv", ["run_benchmark_search", "--benchmark-path", str(archive),
        "--benchmark-sha256", "0" * 64, "--indices", "1,2,3", "--budget", "1",
        "--cache", str(tmp_path / "cache.sqlite"), "--report", str(tmp_path / "report.json")])
    with pytest.raises(SystemExit):
        main()
