from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.request import urlopen


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def acquire_file(url: str, destination: str | Path, expected_sha256: str) -> Path:
    """Download once, stream to a temporary file, and verify before promotion."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_suffix(destination.suffix + ".partial")
    with urlopen(url, timeout=60) as source, open(temporary, "wb") as target:
        while chunk := source.read(1024 * 1024):
            target.write(chunk)
    actual = sha256_file(temporary)
    if actual.lower() != expected_sha256.lower():
        temporary.unlink(missing_ok=True)
        raise ValueError(f"checksum mismatch for {url}: expected {expected_sha256}, got {actual}")
    os.replace(temporary, destination)
    return destination
