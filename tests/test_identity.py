import hashlib

import pytest
from archai_api import main as api_main
from archai_api.identity import IdentityService, InMemoryIdentityStore, hash_key, scope_allows
from fastapi.testclient import TestClient

BOOTSTRAP = "bootstrap-key-for-identity-tests-0123456789"


@pytest.fixture
def client(monkeypatch):
    for name in ("ARCHAI_API_KEY", "ARCHAI_API_KEY_SHA256", "ARCHAI_PROTECT_READS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api_main, "_identity", IdentityService(InMemoryIdentityStore()))
    return TestClient(api_main.app)


def _admin(client, headers):
    user = client.post("/v1/users", json={"email": "Admin@Example.org", "role": "admin"}, headers=headers)
    assert user.status_code == 200, user.text
    key = client.post("/v1/api-keys", json={"user_id": user.json()["user_id"], "name": "admin",
                                            "scopes": ["admin"]}, headers=headers)
    assert key.status_code == 200, key.text
    return user.json(), key.json()


def test_scope_hierarchy():
    assert scope_allows(["admin"], "write") and scope_allows(["admin"], "read")
    assert scope_allows(["write"], "read") and not scope_allows(["write"], "admin")
    assert scope_allows(["read"], "read") and not scope_allows(["read"], "write")


def test_open_mode_until_the_first_managed_key(client):
    assert client.get("/v1/auth/whoami").json()["auth_enabled"] is False
    _user, key = _admin(client, {})
    assert key["secret"].startswith(key["key_prefix"] + "_")
    assert "key_hash" not in key
    whoami = client.get("/v1/auth/whoami").json()
    assert whoami["auth_enabled"] is True and whoami["authenticated"] is False
    assert client.post("/v1/projects", json={"name": "p", "task": "t"}).status_code == 401
    me = client.get("/v1/auth/whoami", headers={"x-api-key": key["secret"]}).json()
    assert me["principal"]["kind"] == "key" and me["principal"]["email"] == "admin@example.org"
    assert client.get("/v1/auth/whoami", headers={"x-api-key": "ak_00000000_" + "x" * 43}).status_code == 401


def test_first_managed_key_must_be_admin_without_bootstrap(client):
    user = client.post("/v1/users", json={"email": "m@example.org"}).json()
    response = client.post("/v1/api-keys", json={"user_id": user["user_id"], "name": "k", "scopes": ["write"]})
    assert response.status_code == 409


def test_scopes_are_enforced(client):
    _user, admin = _admin(client, {})
    headers = {"x-api-key": admin["secret"]}
    member = client.post("/v1/users", json={"email": "member@example.org"}, headers=headers).json()
    reader = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "ro", "scopes": ["read"]},
                         headers=headers).json()
    writer = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "rw",
                                               "scopes": ["read", "write"]}, headers=headers).json()
    denied = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "x", "scopes": ["admin"]},
                         headers=headers)
    assert denied.status_code == 409  # members cannot hold admin keys
    body = {"name": "p", "task": "t"}
    assert client.post("/v1/projects", json=body, headers={"x-api-key": reader["secret"]}).status_code == 403
    assert client.post("/v1/projects", json=body, headers={"x-api-key": writer["secret"]}).status_code == 200
    assert client.get("/v1/users", headers={"x-api-key": writer["secret"]}).status_code == 403
    assert client.get("/v1/audit", headers={"x-api-key": writer["secret"]}).status_code == 403
    listed = client.get("/v1/api-keys", headers=headers).json()["items"]
    assert {item["name"] for item in listed} == {"admin", "ro", "rw"}
    assert all("secret" not in item and "key_hash" not in item for item in listed)


def test_rotation_issues_a_new_secret_and_revokes_the_old_one(client):
    _user, admin = _admin(client, {})
    headers = {"x-api-key": admin["secret"]}
    member = client.post("/v1/users", json={"email": "r@example.org"}, headers=headers).json()
    old = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "ci", "scopes": ["write"]},
                      headers=headers).json()
    rotated = client.post(f"/v1/api-keys/{old['credential_id']}/rotate", json={"expires_in_days": 30},
                          headers=headers)
    assert rotated.status_code == 200, rotated.text
    new = rotated.json()
    assert new["secret"] != old["secret"] and new["rotated_from"] == old["credential_id"]
    assert new["scopes"] == ["write"] and new["expires_at"] is not None
    assert new["revoked"]["state"] == "revoked"
    body = {"name": "p", "task": "t"}
    assert client.post("/v1/projects", json=body, headers={"x-api-key": old["secret"]}).status_code == 401
    assert client.post("/v1/projects", json=body, headers={"x-api-key": new["secret"]}).status_code == 200
    again = client.post(f"/v1/api-keys/{old['credential_id']}/rotate", headers=headers)
    assert again.status_code == 422


def test_disabled_users_lose_access_and_the_last_admin_is_protected(client):
    admin_user, admin = _admin(client, {})
    headers = {"x-api-key": admin["secret"]}
    assert client.post(f"/v1/api-keys/{admin['credential_id']}/revoke", headers=headers).status_code == 409
    assert client.patch(f"/v1/users/{admin_user['user_id']}", json={"disabled": True},
                        headers=headers).status_code == 409
    member = client.post("/v1/users", json={"email": "d@example.org"}, headers=headers).json()
    key = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "k", "scopes": ["write"]},
                      headers=headers).json()
    assert client.patch(f"/v1/users/{member['user_id']}", json={"disabled": True},
                        headers=headers).json()["active"] is False
    assert client.post("/v1/projects", json={"name": "p", "task": "t"},
                       headers={"x-api-key": key["secret"]}).status_code == 401
    assert client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "k2", "scopes": ["read"]},
                       headers=headers).status_code == 409


def test_bootstrap_key_is_admin_and_allows_member_only_keys(client, monkeypatch):
    monkeypatch.setenv("ARCHAI_API_KEY_SHA256", hashlib.sha256(BOOTSTRAP.encode()).hexdigest())
    headers = {"authorization": f"Bearer {BOOTSTRAP}"}
    assert client.get("/v1/users").status_code == 401
    member = client.post("/v1/users", json={"email": "b@example.org"}, headers=headers).json()
    key = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "k", "scopes": ["read"]},
                      headers=headers)
    assert key.status_code == 200
    assert client.post(f"/v1/api-keys/{key.json()['credential_id']}/revoke", headers=headers).json()["state"] == "revoked"
    assert client.get("/v1/auth/whoami", headers=headers).json()["principal"]["kind"] == "bootstrap"


def test_protect_reads_accepts_read_scoped_keys(client, monkeypatch):
    _user, admin = _admin(client, {})
    monkeypatch.setenv("ARCHAI_PROTECT_READS", "1")
    assert client.get("/v1/jobs").status_code == 401
    assert client.get("/v1/auth/whoami").status_code == 200
    assert client.get("/v1/jobs", headers={"x-api-key": admin["secret"]}).status_code == 200


def test_expired_keys_are_rejected(client):
    from dataclasses import replace
    from datetime import UTC, datetime, timedelta
    _user, admin = _admin(client, {})
    headers = {"x-api-key": admin["secret"]}
    member = client.post("/v1/users", json={"email": "e@example.org"}, headers=headers).json()
    key = client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "k", "scopes": ["write"],
                                            "expires_in_days": 1}, headers=headers).json()
    store = api_main._identity.store
    credential = store.get_credential(key["credential_id"])
    store.update_credential(replace(credential, expires_at=datetime.now(UTC) - timedelta(seconds=1)))
    assert store.find_by_hash(hash_key(key["secret"])) is not None
    assert client.post("/v1/projects", json={"name": "p", "task": "t"},
                       headers={"x-api-key": key["secret"]}).status_code == 401


def test_audit_events_name_the_principal(client, monkeypatch, tmp_path):
    log = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ARCHAI_AUDIT_LOG", str(log))
    _user, admin = _admin(client, {})
    client.post("/v1/projects", json={"name": "p", "task": "t"}, headers={"x-api-key": admin["secret"]})
    events = client.get("/v1/audit", headers={"x-api-key": admin["secret"]}).json()["items"]
    assert events[0]["principal"] == admin["credential_id"]


def test_sqlalchemy_identity_store_round_trip(tmp_path):
    from alembic import command
    from alembic.config import Config
    from archai_api.db import SqlAlchemyIdentityStore
    url = f"sqlite:///{tmp_path / 'identity.sqlite'}"
    import os
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(Config("alembic.ini"), "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL")
        else:
            os.environ["DATABASE_URL"] = previous
    service = IdentityService(SqlAlchemyIdentityStore.from_url(url))
    user = service.create_user(email="db@example.org", role="admin")
    credential, secret = service.create_key(user_id=user.user_id, name="db", scopes=["admin"])
    principal = service.authenticate(secret)
    assert principal is not None and principal.credential_id == credential.credential_id
    assert principal.allows("admin")
    new, new_secret, old = service.rotate_key(credential.credential_id)
    assert service.authenticate(secret) is None
    assert service.authenticate(new_secret).credential_id == new.credential_id
    assert service.store.get_credential(old.credential_id).state() == "revoked"
    assert service.store.get_user(user.user_id).role == "admin"
    with pytest.raises(ValueError):
        service.create_user(email="db@example.org")
