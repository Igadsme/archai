"""User accounts and managed API keys.

Keys are shown once at creation or rotation and only their SHA-256 digest is stored. Every key
belongs to a user and carries explicit scopes. The bootstrap key from `ARCHAI_API_KEY` /
`ARCHAI_API_KEY_SHA256` keeps working as an admin credential with no user attached, so a host can
always recover access to key management.

Authentication is enforced when a bootstrap key is configured or at least one managed key is
active. With neither, the API stays in open local-development mode, as before.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import re
import secrets
import threading
import time
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import uuid4

Scope = Literal["read", "write", "admin"]
SCOPES: tuple[Scope, ...] = ("read", "write", "admin")
Role = Literal["admin", "member"]
KEY_PREFIX = "ak_"
_KEY_SHAPE = re.compile(r"^ak_([0-9a-f]{8})_[A-Za-z0-9_-]{32,}$")
_EMAIL = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}$")


def utcnow() -> datetime:
    return datetime.now(UTC)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=UTC)


def hash_key(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


def generate_key(credential_id: str) -> str:
    """`ak_<first 8 hex of the credential id>_<43 url-safe random chars>` (256 bits of entropy)."""
    return f"{KEY_PREFIX}{credential_id[:8]}_{secrets.token_urlsafe(32)}"


def normalize_scopes(values) -> tuple[Scope, ...]:
    chosen = {str(value).strip().lower() for value in values}
    unknown = sorted(chosen - set(SCOPES))
    if unknown:
        raise ValueError(f"unknown scope(s): {', '.join(unknown)}; choose from {', '.join(SCOPES)}")
    if not chosen:
        raise ValueError("at least one scope is required")
    return tuple(scope for scope in SCOPES if scope in chosen)


def scope_allows(scopes, needed: Scope) -> bool:
    """`admin` implies `write`, and `write` implies `read`."""
    granted = set(scopes)
    if "admin" in granted:
        return True
    if needed == "read":
        return bool(granted & {"read", "write"})
    return needed in granted


@dataclass(frozen=True)
class User:
    user_id: str
    email: str
    display_name: str = ""
    role: Role = "member"
    created_at: datetime = field(default_factory=utcnow)
    disabled_at: datetime | None = None

    def as_dict(self) -> dict:
        return {"user_id": self.user_id, "email": self.email, "display_name": self.display_name,
                "role": self.role, "created_at": self.created_at.isoformat(),
                "disabled_at": self.disabled_at.isoformat() if self.disabled_at else None,
                "active": self.disabled_at is None}


@dataclass(frozen=True)
class Credential:
    credential_id: str
    user_id: str
    key_hash: str
    name: str
    key_prefix: str
    scopes: tuple[Scope, ...]
    created_at: datetime = field(default_factory=utcnow)
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    rotated_from: str | None = None

    def state(self, now: datetime | None = None) -> str:
        now = now or utcnow()
        if self.revoked_at is not None:
            return "revoked"
        if self.expires_at is not None and _aware(self.expires_at) <= now:
            return "expired"
        return "active"

    def as_dict(self) -> dict:
        """Public view: the key hash and secret are never returned."""
        iso = lambda value: _aware(value).isoformat() if value else None  # noqa: E731
        return {"credential_id": self.credential_id, "user_id": self.user_id, "name": self.name,
                "key_prefix": self.key_prefix, "scopes": list(self.scopes),
                "created_at": iso(self.created_at), "last_used_at": iso(self.last_used_at),
                "expires_at": iso(self.expires_at), "revoked_at": iso(self.revoked_at),
                "rotated_from": self.rotated_from, "state": self.state()}


@dataclass(frozen=True)
class Principal:
    kind: Literal["anonymous", "bootstrap", "key"]
    scopes: tuple[Scope, ...]
    user_id: str | None = None
    email: str | None = None
    credential_id: str | None = None
    key_prefix: str | None = None

    def allows(self, scope: Scope) -> bool:
        return scope_allows(self.scopes, scope)

    @property
    def audit_id(self) -> str:
        return self.credential_id or self.kind

    def as_dict(self) -> dict:
        return {"kind": self.kind, "scopes": list(self.scopes), "user_id": self.user_id,
                "email": self.email, "credential_id": self.credential_id, "key_prefix": self.key_prefix}


OPEN_PRINCIPAL = Principal(kind="anonymous", scopes=SCOPES)
ANONYMOUS = Principal(kind="anonymous", scopes=())
BOOTSTRAP = Principal(kind="bootstrap", scopes=SCOPES)


class InMemoryIdentityStore:
    """Process-local store used when DATABASE_URL is unset (tests and quick local runs)."""

    def __init__(self):
        self._users: dict[str, User] = {}
        self._credentials: dict[str, Credential] = {}
        self._lock = threading.Lock()

    def add_user(self, user: User) -> User:
        with self._lock:
            if any(existing.email == user.email for existing in self._users.values()):
                raise ValueError(f"a user with email {user.email} already exists")
            self._users[user.user_id] = user
            return user

    def update_user(self, user: User) -> User:
        with self._lock:
            self._users[user.user_id] = user
            return user

    def get_user(self, user_id: str) -> User | None:
        return self._users.get(user_id)

    def list_users(self) -> list[User]:
        return sorted(self._users.values(), key=lambda user: user.created_at)

    def add_credential(self, credential: Credential) -> Credential:
        with self._lock:
            self._credentials[credential.credential_id] = credential
            return credential

    def update_credential(self, credential: Credential) -> Credential:
        with self._lock:
            self._credentials[credential.credential_id] = credential
            return credential

    def get_credential(self, credential_id: str) -> Credential | None:
        return self._credentials.get(credential_id)

    def find_by_hash(self, key_hash: str) -> Credential | None:
        for credential in self._credentials.values():
            if hmac.compare_digest(credential.key_hash, key_hash):
                return credential
        return None

    def list_credentials(self, user_id: str | None = None) -> list[Credential]:
        values = [value for value in self._credentials.values() if user_id is None or value.user_id == user_id]
        return sorted(values, key=lambda value: value.created_at)

    def touch(self, credential_id: str, at: datetime) -> None:
        with self._lock:
            credential = self._credentials.get(credential_id)
            if credential is not None:
                self._credentials[credential_id] = replace(credential, last_used_at=at)


def bootstrap_key_configured() -> bool:
    return bool(os.getenv("ARCHAI_API_KEY") or os.getenv("ARCHAI_API_KEY_SHA256"))


def bootstrap_key_matches(supplied: str) -> bool:
    configured = os.getenv("ARCHAI_API_KEY")
    configured_hash = os.getenv("ARCHAI_API_KEY_SHA256")
    valid = bool(configured) and hmac.compare_digest(supplied.encode(), configured.encode())
    if configured_hash:
        valid = hmac.compare_digest(hash_key(supplied), configured_hash.lower()) or valid
    return valid


class IdentityService:
    """Authentication, user and key lifecycle on top of a store."""

    _ACTIVE_CACHE_SECONDS = 5.0
    _TOUCH_INTERVAL_SECONDS = 60.0

    def __init__(self, store):
        self.store = store
        self._active_cache: tuple[float, bool] | None = None
        self._touched: dict[str, float] = {}
        self._lock = threading.Lock()

    def _invalidate(self) -> None:
        self._active_cache = None

    def managed_keys_active(self) -> bool:
        cached = self._active_cache
        now = time.monotonic()
        if cached and now - cached[0] < self._ACTIVE_CACHE_SECONDS:
            return cached[1]
        active = any(self._usable(credential) for credential in self.store.list_credentials())
        self._active_cache = (now, active)
        return active

    def auth_enabled(self) -> bool:
        return bootstrap_key_configured() or self.managed_keys_active()

    def _usable(self, credential: Credential) -> bool:
        if credential.state() != "active":
            return False
        user = self.store.get_user(credential.user_id)
        return user is not None and user.disabled_at is None

    def authenticate(self, supplied: str | None) -> Principal | None:
        """Principal for the supplied secret; None when a secret was supplied but is not valid.

        With authentication disabled every caller is the open-mode principal.
        """
        if not self.auth_enabled():
            return OPEN_PRINCIPAL
        if not supplied:
            return ANONYMOUS
        if bootstrap_key_configured() and bootstrap_key_matches(supplied):
            return BOOTSTRAP
        if not _KEY_SHAPE.fullmatch(supplied):
            return None
        credential = self.store.find_by_hash(hash_key(supplied))
        if credential is None or not self._usable(credential):
            return None
        user = self.store.get_user(credential.user_id)
        self._maybe_touch(credential.credential_id)
        return Principal(kind="key", scopes=credential.scopes, user_id=credential.user_id,
                         email=user.email if user else None, credential_id=credential.credential_id,
                         key_prefix=credential.key_prefix)

    def _maybe_touch(self, credential_id: str) -> None:
        now = time.monotonic()
        with self._lock:
            last = self._touched.get(credential_id)
            if last is not None and now - last < self._TOUCH_INTERVAL_SECONDS:
                return
            self._touched[credential_id] = now
        try:
            self.store.touch(credential_id, utcnow())
        except Exception:  # last-used bookkeeping must never fail a request
            pass

    def create_user(self, *, email: str, display_name: str = "", role: Role = "member") -> User:
        email = email.strip().lower()
        if not _EMAIL.fullmatch(email):
            raise ValueError("email must look like name@host")
        if role not in ("admin", "member"):
            raise ValueError("role must be admin or member")
        return self.store.add_user(User(user_id=uuid4().hex, email=email,
                                        display_name=display_name.strip(), role=role))

    def update_user(self, user_id: str, *, display_name: str | None = None, role: Role | None = None,
                    disabled: bool | None = None) -> User:
        user = self._require_user(user_id)
        changes: dict = {}
        if display_name is not None:
            changes["display_name"] = display_name.strip()
        if role is not None:
            if role not in ("admin", "member"):
                raise ValueError("role must be admin or member")
            changes["role"] = role
        if disabled is not None:
            if disabled and user.disabled_at is None:
                self._guard_last_admin(excluding_user=user_id)
            changes["disabled_at"] = (user.disabled_at or utcnow()) if disabled else None
        updated = self.store.update_user(replace(user, **changes))
        self._invalidate()
        return updated

    def create_key(self, *, user_id: str, name: str, scopes, expires_in_days: int | None = None,
                   rotated_from: str | None = None) -> tuple[Credential, str]:
        user = self._require_user(user_id)
        if user.disabled_at is not None:
            raise PermissionError("cannot issue keys to a disabled user")
        chosen = normalize_scopes(scopes)
        if "admin" in chosen and user.role != "admin":
            raise PermissionError("only users with role=admin can hold admin-scoped keys")
        if ("admin" not in chosen and not bootstrap_key_configured()
                and not any("admin" in value.scopes and self._usable(value)
                            for value in self.store.list_credentials())):
            raise PermissionError("the first managed key must be admin-scoped when no bootstrap key "
                                  "(ARCHAI_API_KEY / ARCHAI_API_KEY_SHA256) is configured, or nobody "
                                  "could manage keys afterwards")
        credential_id = uuid4().hex
        secret = generate_key(credential_id)
        expires_at = utcnow() + timedelta(days=expires_in_days) if expires_in_days else None
        credential = Credential(credential_id=credential_id, user_id=user_id, key_hash=hash_key(secret),
                                name=name.strip() or "unnamed", key_prefix=f"{KEY_PREFIX}{credential_id[:8]}",
                                scopes=chosen, expires_at=expires_at, rotated_from=rotated_from)
        self.store.add_credential(credential)
        self._invalidate()
        return credential, secret

    def revoke_key(self, credential_id: str) -> Credential:
        credential = self._require_credential(credential_id)
        if credential.revoked_at is not None:
            return credential
        if "admin" in credential.scopes:
            self._guard_last_admin(excluding_credential=credential_id)
        updated = self.store.update_credential(replace(credential, revoked_at=utcnow()))
        self._invalidate()
        return updated

    def rotate_key(self, credential_id: str, *, expires_in_days: int | None = None) -> tuple[Credential, str, Credential]:
        """Issue a replacement with the same owner, name and scopes, then revoke the old key."""
        old = self._require_credential(credential_id)
        if old.state() == "revoked":
            raise ValueError("a revoked key cannot be rotated; create a new key instead")
        new, secret = self.create_key(user_id=old.user_id, name=old.name, scopes=old.scopes,
                                      expires_in_days=expires_in_days, rotated_from=old.credential_id)
        revoked = self.store.update_credential(replace(old, revoked_at=utcnow()))
        self._invalidate()
        return new, secret, revoked

    def _require_user(self, user_id: str) -> User:
        user = self.store.get_user(user_id)
        if user is None:
            raise LookupError(f"user {user_id} not found")
        return user

    def _require_credential(self, credential_id: str) -> Credential:
        credential = self.store.get_credential(credential_id)
        if credential is None:
            raise LookupError(f"API key {credential_id} not found")
        return credential

    def _guard_last_admin(self, *, excluding_user: str | None = None,
                          excluding_credential: str | None = None) -> None:
        """Refuse to remove the last admin credential when no bootstrap key can recover access."""
        if bootstrap_key_configured():
            return
        remaining = [credential for credential in self.store.list_credentials()
                     if "admin" in credential.scopes and self._usable(credential)
                     and credential.credential_id != excluding_credential
                     and credential.user_id != excluding_user]
        if not remaining:
            raise PermissionError("this would remove the last active admin key and no bootstrap key "
                                  "(ARCHAI_API_KEY / ARCHAI_API_KEY_SHA256) is configured")
