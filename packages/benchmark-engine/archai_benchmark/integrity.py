from __future__ import annotations

import hashlib
import os
import re
import tempfile
from pathlib import Path
from urllib.request import urlopen


def sha256_file(path: str | Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        for chunk in iter(lambda: stream.read(chunk_size), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_tree(path: str | Path) -> str:
    """Deterministic digest of a directory: SHA-256 over sorted `relative-path NUL file-sha256` lines."""
    root = Path(path)
    if not root.is_dir():
        raise NotADirectoryError(str(root))
    digest = hashlib.sha256()
    for item in sorted(p for p in root.rglob("*") if p.is_file()):
        digest.update(item.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(sha256_file(item).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def sha256_path(path: str | Path) -> str:
    """SHA-256 of a file, or the `sha256_tree` digest of an extracted archive directory."""
    return sha256_tree(path) if Path(path).is_dir() else sha256_file(path)


def acquire_file(url: str, destination: str | Path, expected_sha256: str) -> Path:
    """Download once, stream to a temporary file, and verify before promotion."""
    if not re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256 or ""):
        raise ValueError("expected_sha256 must be a 64-character SHA-256 hex digest")
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary_name = tempfile.mkstemp(prefix=f".{destination.name}.", suffix=".partial",
                                          dir=destination.parent)
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with urlopen(url, timeout=60) as source, temporary.open("wb") as target:
            while chunk := source.read(1024 * 1024):
                target.write(chunk)
        actual = sha256_file(temporary)
        if actual.lower() != expected_sha256.lower():
            raise ValueError(f"checksum mismatch for {url}: expected {expected_sha256}, got {actual}")
        os.replace(temporary, destination)
        return destination
    finally:
        temporary.unlink(missing_ok=True)
