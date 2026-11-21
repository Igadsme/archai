from __future__ import annotations

import os
import tempfile
from pathlib import Path


def allowed_path(value: str, *, field: str = "path") -> Path:
    """Resolve a worker path and enforce configured filesystem roots.

    Local mode defaults to ``/tmp`` and Python's temporary directory. Durable containers set
    ``ARCHAI_ALLOWED_PATHS`` to the mounted artifact/data root.
    """
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty path")
    candidate = Path(value)
    if not candidate.is_absolute():
        raise ValueError(f"{field} must be an absolute path")
    resolved = candidate.resolve(strict=False)
    configured_roots = os.getenv("ARCHAI_ALLOWED_PATHS")
    if configured_roots is None:
        configured_roots = f"/tmp:{tempfile.gettempdir()}"
    roots = [Path(raw.strip()).expanduser().resolve(strict=False)
             for raw in configured_roots.split(":") if raw.strip()]
    if not roots or not any(resolved == root or root in resolved.parents for root in roots):
        allowed = ", ".join(str(root) for root in roots) or "none"
        raise ValueError(f"{field} is outside allowed worker paths: {allowed}")
    return resolved
