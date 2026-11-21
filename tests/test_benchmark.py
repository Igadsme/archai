import hashlib

import pytest

from archai_benchmark.nasbench201 import architecture_from_string
from archai_benchmark.integrity import acquire_file, sha256_file
from archai_core.schema import TensorSpec


def test_nasbench201_encoding_is_valid():
    value = "|nor_conv_3x3~0|+|none~0|nor_conv_1x1~1|+|avg_pool_3x3~0|skip_connect~1|none~2|"
    architecture = architecture_from_string(value, input_spec=TensorSpec(channels=3, height=8, width=8))
    assert architecture.architecture_id == architecture.content_hash()
    assert architecture.metadata["encoding"] == value


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
