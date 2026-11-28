#!/usr/bin/env python3
"""Create or complete `.env` for the local docker compose stack. Standard library only.

    python3 scripts/local/init_env.py              # first run: .env from .env.example, new secrets
    python3 scripts/local/init_env.py --rotate-key # new bootstrap API key (restart the API afterwards)

Existing non-empty values in `.env` are kept. Secrets are never printed: the bootstrap API key is written
to `.archai/bootstrap-api-key` (mode 0600) and only its SHA-256 goes into `.env`.
"""
from __future__ import annotations

import argparse
import hashlib
import os
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LINE = re.compile(r"^\s*(#\s*)?([A-Z][A-Z0-9_]*)=(.*)$")
LOCAL_DEFAULTS = {
    "ARCHAI_ENV": "development",
    "ARCHAI_REQUIRE_API_KEY": "1",
    "ARCHAI_CORS_ORIGINS": "http://localhost:3000,http://127.0.0.1:3000",
    "ARCHAI_PUBLIC_API_URL": "http://localhost:8000",
}


def parse(text: str) -> dict[str, str]:
    values = {}
    for line in text.splitlines():
        match = LINE.match(line)
        if match and not match.group(1):
            values[match.group(2)] = match.group(3).strip()
    return values


def render(template: str, values: dict[str, str]) -> str:
    """Fill the template's assignments in place, uncommenting keys that now have values."""
    seen, lines = set(), []
    for line in template.splitlines():
        match = LINE.match(line)
        if match and match.group(2) in values and match.group(2) not in seen:
            key = match.group(2)
            seen.add(key)
            if match.group(1) and not values[key]:
                lines.append(line)
                continue
            lines.append(f"{key}={values[key]}")
        else:
            lines.append(line)
    extra = [f"{key}={value}" for key, value in values.items() if key not in seen]
    if extra:
        lines += ["", "# Added by scripts/local/init_env.py", *extra]
    return "\n".join(lines) + "\n"


def write_private(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        stream.write(content)
    path.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--rotate-key", action="store_true", help="issue a new bootstrap API key")
    args = parser.parse_args(argv)
    root = args.root.resolve()
    example, target = root / ".env.example", root / ".env"
    key_file = root / ".archai" / "bootstrap-api-key"
    if not example.is_file():
        print(f"missing {example}", file=sys.stderr)
        return 1
    template = example.read_text()
    values = {**parse(template), **(parse(target.read_text()) if target.exists() else {})}
    changed = []
    for key, value in LOCAL_DEFAULTS.items():
        if not values.get(key) or (key == "ARCHAI_REQUIRE_API_KEY" and not target.exists()):
            values[key] = value
    if not values.get("POSTGRES_PASSWORD"):
        values["POSTGRES_PASSWORD"] = secrets.token_hex(24)
        changed.append("POSTGRES_PASSWORD")
    if args.rotate_key or not values.get("ARCHAI_API_KEY_SHA256") or not key_file.is_file():
        if values.get("ARCHAI_API_KEY"):
            print("ARCHAI_API_KEY (plaintext) is set in .env; remove it to use the hashed bootstrap key.",
                  file=sys.stderr)
            return 1
        key = secrets.token_urlsafe(32)
        write_private(key_file, key + "\n")
        values["ARCHAI_API_KEY_SHA256"] = hashlib.sha256(key.encode()).hexdigest()
        changed.append("ARCHAI_API_KEY_SHA256")
    write_private(target, render(template, values))
    print(f"{target.relative_to(root)}: {'updated ' + ', '.join(changed) if changed else 'already complete'}")
    print(f"bootstrap API key file: {key_file.relative_to(root)} (paste its contents into Studio > API KEY)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
