import hashlib
import json

import pytest
from archai_api import main as api_main
from archai_api import settings
from archai_api.main import app
from fastapi.testclient import TestClient

_SAFE_PRODUCTION = {
    "ARCHAI_ENV": "production",
    "ARCHAI_API_KEY_SHA256": hashlib.sha256(b"a-production-key-that-is-long-enough").hexdigest(),
    "ARCHAI_CORS_ORIGINS": "https://studio.example.org",
    "DATABASE_URL": "postgresql+psycopg://archai:secret@db/archai",
    "ARCHAI_REDIS_URL": "rediss://cache:6380/0",
}


def architecture():
    return {"nodes": [{"id": "input", "op": "input", "channels": 3},
                      {"id": "conv", "op": "conv3x3", "channels": 8},
                      {"id": "output", "op": "output", "channels": 8}],
            "edges": [{"source": "input", "target": "conv"}, {"source": "conv", "target": "output"}],
            "input_spec": {"channels": 3, "height": 8, "width": 8}, "output_classes": 10}


@pytest.fixture
def production(monkeypatch):
    for name in ("ARCHAI_API_KEY", "ARCHAI_DB_AUTO_CREATE", "ARCHAI_REQUIRE_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    for name, value in _SAFE_PRODUCTION.items():
        monkeypatch.setenv(name, value)
    return monkeypatch


def test_safe_production_configuration_has_no_errors(production):
    assert settings.configuration_errors() == []
    assert settings.api_key_required()
    assert not settings.docs_enabled()


def test_production_requires_a_key(production):
    production.delenv("ARCHAI_API_KEY_SHA256")
    errors = settings.configuration_errors()
    assert any("ARCHAI_ENV=production" in error for error in errors)


@pytest.mark.parametrize("origins", ["*", "http://studio.example.org", "https://localhost:3000", ""])
def test_production_rejects_unsafe_cors_origins(production, origins):
    production.setenv("ARCHAI_CORS_ORIGINS", origins)
    assert any("CORS" in error for error in settings.configuration_errors())


def test_production_rejects_short_plaintext_keys_and_bad_digests(production):
    production.setenv("ARCHAI_API_KEY", "short")
    production.setenv("ARCHAI_API_KEY_SHA256", "not-a-digest")
    errors = " ".join(settings.configuration_errors())
    assert "at least 32 characters" in errors
    assert "64-character" in errors


def test_production_requires_durable_stores_and_migrations(production):
    production.delenv("DATABASE_URL")
    production.delenv("ARCHAI_REDIS_URL")
    production.setenv("ARCHAI_DB_AUTO_CREATE", "1")
    errors = " ".join(settings.configuration_errors())
    assert "DATABASE_URL" in errors and "ARCHAI_REDIS_URL" in errors and "ARCHAI_DB_AUTO_CREATE" in errors


def test_production_boot_is_refused_with_unsafe_settings(production):
    production.setenv("ARCHAI_CORS_ORIGINS", "*")
    with pytest.raises(RuntimeError, match="refusing to start"):
        with TestClient(app):
            pass


def test_development_defaults_stay_open(monkeypatch):
    for name in ("ARCHAI_ENV", "ARCHAI_REQUIRE_API_KEY", "ARCHAI_API_KEY", "ARCHAI_API_KEY_SHA256",
                 "ARCHAI_CORS_ORIGINS", "ARCHAI_DOCS_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    assert settings.configuration_errors() == []
    assert settings.docs_enabled()
    assert "http://localhost:3000" in settings.cors_origins()


def test_responses_carry_security_headers_and_request_ids():
    client = TestClient(app)
    response = client.get("/health")
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert "default-src 'none'" in response.headers["content-security-policy"]
    assert len(response.headers["x-request-id"]) == 32
    echoed = client.get("/health", headers={"x-request-id": "trace-123"})
    assert echoed.headers["x-request-id"] == "trace-123"
    replaced = client.get("/health", headers={"x-request-id": "bad id with spaces"})
    assert replaced.headers["x-request-id"] != "bad id with spaces"


def test_hsts_is_only_sent_in_production(monkeypatch):
    client = TestClient(app)
    monkeypatch.delenv("ARCHAI_ENV", raising=False)
    assert "strict-transport-security" not in client.get("/health").headers
    monkeypatch.setenv("ARCHAI_ENV", "production")
    assert "max-age" in client.get("/health").headers["strict-transport-security"]


def test_early_rejections_still_carry_request_id_and_headers(monkeypatch):
    monkeypatch.setenv("ARCHAI_MAX_REQUEST_BYTES", "10")
    response = TestClient(app).post("/v1/architectures/validate", json=architecture())
    assert response.status_code == 413
    assert response.headers["x-request-id"]
    assert response.headers["x-content-type-options"] == "nosniff"


def test_malformed_content_length_is_a_client_error():
    client = TestClient(app)
    request = client.build_request("POST", "/v1/architectures/validate", content=b"{}",
                                   headers={"content-type": "application/json"})
    request.headers["content-length"] = "abc"
    assert client.send(request).status_code == 400


def test_generate_requires_the_write_key(monkeypatch):
    monkeypatch.setenv("ARCHAI_API_KEY", "generate-secret")
    monkeypatch.delenv("ARCHAI_GENERATOR_CHECKPOINT", raising=False)
    client = TestClient(app)
    assert client.post("/v1/architectures/generate", json={}).status_code == 401
    authorized = client.post("/v1/architectures/generate", json={}, headers={"x-api-key": "generate-secret"})
    assert authorized.status_code == 503


def test_protect_reads_guards_everything_but_probes(monkeypatch):
    monkeypatch.setenv("ARCHAI_PROTECT_READS", "1")
    monkeypatch.setenv("ARCHAI_API_KEY", "read-secret")
    client = TestClient(app)
    assert client.get("/health").status_code == 200
    assert client.get("/readiness").status_code == 200
    denied = client.get("/v1/jobs")
    assert denied.status_code == 401
    assert denied.headers["www-authenticate"] == "Bearer"
    assert client.get("/v1/jobs", headers={"x-api-key": "read-secret"}).status_code == 200
    assert client.get("/v1/jobs", headers={"authorization": "Bearer read-secret"}).status_code == 200


def test_cors_exposes_download_and_trace_headers():
    response = TestClient(app).get("/health", headers={"Origin": "http://localhost:3000"})
    exposed = response.headers["access-control-expose-headers"].lower()
    assert "content-disposition" in exposed and "x-request-id" in exposed


def test_audit_log_is_readable_newest_first_with_the_key(monkeypatch, tmp_path):
    audit = tmp_path / "audit.jsonl"
    monkeypatch.setenv("ARCHAI_AUDIT_LOG", str(audit))
    monkeypatch.setenv("ARCHAI_API_KEY", "audit-reader-key")
    client = TestClient(app)
    headers = {"x-api-key": "audit-reader-key", "x-request-id": "audit-trace"}
    assert client.post("/v1/architectures", json=architecture()).status_code == 401
    assert client.post("/v1/architectures", json=architecture(), headers=headers).status_code == 200
    assert client.get("/v1/audit").status_code == 401
    body = client.get("/v1/audit", headers=headers).json()
    assert body["available"] is True
    assert [event["status"] for event in body["items"]] == [200, 401]
    assert body["items"][0]["request_id"] == "audit-trace"
    rejected = client.get("/v1/audit?outcome=rejected", headers=headers).json()["items"]
    assert [event["status"] for event in rejected] == [401]
    assert "audit-reader-key" not in json.dumps(body)


def test_audit_log_reports_when_no_file_is_configured(monkeypatch):
    monkeypatch.delenv("ARCHAI_AUDIT_LOG", raising=False)
    monkeypatch.delenv("ARCHAI_API_KEY", raising=False)
    monkeypatch.delenv("ARCHAI_API_KEY_SHA256", raising=False)
    body = TestClient(app).get("/v1/audit").json()
    assert body == {"available": False, "items": [], "detail": body["detail"]}


def test_tail_lines_reads_across_blocks(tmp_path):
    path = tmp_path / "log.jsonl"
    path.write_text("".join(f'{{"n": {index}}}\n' for index in range(500)))
    tail = api_main._tail_lines(path, 3, block_size=16)
    assert [json.loads(line)["n"] for line in tail] == [497, 498, 499]
