"""Runtime configuration read from the environment at call time.

`ARCHAI_ENV=production` turns on every deployment safeguard at once; each check
is also reachable on its own so local development stays open by default.
"""
from __future__ import annotations

import os
from urllib.parse import urlparse

DEFAULT_CORS_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
PUBLIC_PATHS = frozenset({"/health", "/readiness"})
DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})
_LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1", "[::1]"}  # noqa: S104 - a denylist, not a bind


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def environment() -> str:
    return os.getenv("ARCHAI_ENV", "development").strip().lower() or "development"


def is_production() -> bool:
    return environment() == "production"


def api_key_is_configured() -> bool:
    return bool(os.getenv("ARCHAI_API_KEY") or os.getenv("ARCHAI_API_KEY_SHA256"))


def api_key_required() -> bool:
    return is_production() or _flag("ARCHAI_REQUIRE_API_KEY")


def protect_reads() -> bool:
    """Require the API key on every read except health/readiness probes."""
    return _flag("ARCHAI_PROTECT_READS")


def docs_enabled() -> bool:
    return _flag("ARCHAI_DOCS_ENABLED", "0" if is_production() else "1")


def cors_origins() -> list[str]:
    raw = os.getenv("ARCHAI_CORS_ORIGINS", "" if is_production() else DEFAULT_CORS_ORIGINS)
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]


def configuration_errors() -> list[str]:
    """Problems that must stop the API from booting; empty when the configuration is safe."""
    errors: list[str] = []
    if api_key_required() and not api_key_is_configured():
        reason = "ARCHAI_ENV=production" if is_production() else "ARCHAI_REQUIRE_API_KEY=1"
        errors.append(f"{reason} but neither ARCHAI_API_KEY nor ARCHAI_API_KEY_SHA256 is set")
    digest = os.getenv("ARCHAI_API_KEY_SHA256")
    if digest and (len(digest) != 64 or any(char not in "0123456789abcdefABCDEF" for char in digest)):
        errors.append("ARCHAI_API_KEY_SHA256 must be a 64-character SHA-256 hex digest")
    if not is_production():
        return errors
    key = os.getenv("ARCHAI_API_KEY")
    if key and len(key) < 32:
        errors.append("ARCHAI_API_KEY must be at least 32 characters in production")
    origins = cors_origins()
    if not origins:
        errors.append("ARCHAI_CORS_ORIGINS must list the Studio origin(s) in production")
    for origin in origins:
        parsed = urlparse(origin)
        if origin == "*" or parsed.scheme != "https" or not parsed.hostname:
            errors.append(f"CORS origin {origin!r} must be an explicit https:// origin in production")
        elif parsed.hostname in _LOCAL_HOSTS:
            errors.append(f"CORS origin {origin!r} is a local address; remove it in production")
    for name in ("DATABASE_URL", "ARCHAI_REDIS_URL"):
        if not os.getenv(name):
            errors.append(f"{name} is required in production (in-memory stores lose data on restart)")
    if _flag("ARCHAI_DB_AUTO_CREATE"):
        errors.append("ARCHAI_DB_AUTO_CREATE must be 0 in production; run `alembic upgrade head`")
    return errors


def validate_configuration() -> None:
    errors = configuration_errors()
    if errors:
        raise RuntimeError("refusing to start: " + "; ".join(errors))
