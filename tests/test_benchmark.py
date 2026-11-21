import hashlib
import json

import pytest

from archai_benchmark.nasbench201 import architecture_from_string, parse_architecture_string
from archai_benchmark.search import IndexRegularizedEvolution
from archai_benchmark.integrity import acquire_file, sha256_file
from scripts.acquire_dataset import main as acquire_dataset_main
from archai_core.schema import TensorSpec


def test_nasbench201_encoding_is_valid():
    value = "|nor_conv_3x3~0|+|none~0|nor_conv_1x1~1|+|avg_pool_3x3~0|skip_connect~1|none~2|"
    architecture = architecture_from_string(value, input_spec=TensorSpec(channels=3, height=8, width=8))
    assert architecture.architecture_id == architecture.content_hash()
    assert architecture.metadata["encoding"] == value
    assert len(parse_architecture_string(value).operations) == 6


def test_nasbench201_rejects_non_cell_encodings():
    with pytest.raises(ValueError, match="three destination groups"):
        parse_architecture_string("|skip_connect~0|")
    with pytest.raises(ValueError, match="exactly 3 edges"):
        parse_architecture_string("|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|")


def test_index_regularized_evolution_mutates_available_cell_and_is_reproducible():
    encodings = {
        0: "|skip_connect~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|",
        1: "|none~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|",
        2: "|nor_conv_3x3~0|+|skip_connect~0|skip_connect~1|+|skip_connect~0|skip_connect~1|skip_connect~2|",
    }
    left = IndexRegularizedEvolution(list(encodings), encodings, population_size=1, sample_size=1, seed=4)
    right = IndexRegularizedEvolution(list(encodings), encodings, population_size=1, sample_size=1, seed=4)
    first = left.ask()
    assert first == right.ask()
    left.tell(first, 0.8)
    right.tell(first, 0.8)
    second = left.ask()
    assert second == right.ask()
    assert second != first


def test_integrity_verification(tmp_path):
    source = tmp_path / "source.bin"
    source.write_bytes(b"archai")
    digest = hashlib.sha256(b"archai").hexdigest()
    assert sha256_file(source) == digest
    # file:// exercises the same streamed, checksum-gated acquisition path
    destination = tmp_path / "download.bin"
    acquired = acquire_file(source.as_uri(), destination, digest)
    assert acquired.read_bytes() == b"archai"
    with pytest.raises(ValueError):
        acquire_file(source.as_uri(), tmp_path / "bad.bin", "0" * 64)


def test_dataset_acquisition_cli_requires_and_reports_verified_manifest(tmp_path, monkeypatch, capsys):
    source = tmp_path / "source.bin"
    source.write_bytes(b"dataset")
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"dataset_id": "unit", "version": "1", "uri": source.as_uri(),
        "sha256": hashlib.sha256(b"dataset").hexdigest(), "license": "test",
        "search_space": "unit", "source": "local"}))
    destination = tmp_path / "downloaded.bin"
    monkeypatch.setattr("sys.argv", ["acquire_dataset", "--manifest", str(manifest),
                                      "--destination", str(destination)])
    assert acquire_dataset_main() == 0
    assert json.loads(capsys.readouterr().out)["verified"] is True
