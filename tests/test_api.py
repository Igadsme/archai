import hashlib
import os
from uuid import uuid4

import pytest
from archai_api.main import app
from fastapi.testclient import TestClient


def payload():
    return {"nodes": [{"id": "input", "op": "input", "channels": 3},
                       {"id": "conv", "op": "conv3x3", "channels": 8},
                       {"id": "output", "op": "output", "channels": 8}],
            "edges": [{"source": "input", "target": "conv"}, {"source": "conv", "target": "output"}],
            "input_spec": {"channels": 3, "height": 8, "width": 8}, "output_classes": 10}


def test_architecture_registry_api():
    client = TestClient(app)
    created = client.post("/v1/architectures", json=payload())
    assert created.status_code == 200
    identifier = created.json()["hash"]
    assert client.get(f"/v1/architectures/{identifier}").status_code == 200
    assert client.get("/v1/architectures").json()["items"]
    assert client.get(f"/v1/architectures/compare?ids={identifier}").status_code == 200
    assert client.get("/v1/architectures/compare?ids=missing").status_code == 404


def test_dataset_registry_requires_checksum_and_is_immutable():
    client = TestClient(app)
    dataset = {"dataset_id": "unit", "version": "1", "checksum": "a" * 64,
               "uri": "file:///tmp/unit.bin", "license": "test"}
    assert client.post("/v1/datasets", json={**dataset, "checksum": "bad"}).status_code == 422
    assert client.post("/v1/datasets", json=dataset).status_code == 200
    assert client.get("/v1/datasets").json()["items"]
    assert client.get("/v1/datasets/unit?version=1").json()["checksum"] == "a" * 64
    assert client.post("/v1/datasets", json={**dataset, "uri": "file:///tmp/other.bin"}).status_code == 409


def test_search_and_experiment_lifecycle_surface():
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    dataset = {"dataset_id": "unit", "version": "1", "checksum": "a" * 64,
               "uri": "file:///tmp/unit.bin", "license": "test"}
    assert client.post("/v1/datasets", json=dataset).status_code == 200
    search = client.post("/v1/searches", json={"algorithm": "random", "dataset_id": "unit",
                                               "budget_evaluations": 2, "seed": 7})
    assert search.status_code == 200
    search_id = search.json()["search_id"]
    assert client.get(f"/v1/searches/{search_id}").json()["status"] == "queued"
    assert client.get("/v1/searches").json()["items"]
    assert client.post(f"/v1/searches/{search_id}/start").status_code == 503
    cancelled = client.post(f"/v1/searches/{search_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/v1/searches/{search_id}").json()["job"]["status"] == "cancelled"
    assert client.get(f"/v1/searches/{search_id}").json()["status"] == "cancelled"
    experiment = client.post("/v1/experiments", json={"architecture_id": identifier,
        "evidence_type": "predicted", "dataset_id": "unit", "dataset_version": "1", "seed": 7})
    assert experiment.status_code == 200
    experiment_id = experiment.json()["experiment_id"]
    assert client.get(f"/v1/experiments/{experiment_id}").status_code == 200
    assert client.get("/v1/experiments").json()["items"]
    updated = client.patch(f"/v1/experiments/{experiment_id}",
                            json={"status": "running", "metrics": {"loss": 0.4}})
    assert updated.status_code == 200
    assert updated.json()["status"] == "running"
    completed = client.patch(f"/v1/experiments/{experiment_id}",
                             json={"status": "completed", "metrics": {"accuracy": 0.8}})
    assert completed.status_code == 200
    assert client.patch(f"/v1/experiments/{experiment_id}", json={"status": "running"}).status_code == 409
    assert client.get("/v1/models").status_code == 200
    assert client.get("/v1/models/unknown").status_code == 404


def test_training_job_api_validates_and_exposes_job_lifecycle():
    client = TestClient(app)
    missing = client.post("/v1/training", json={"kind": "generator", "payload": {}})
    assert missing.status_code == 422
    request = {"kind": "generator", "payload": {"corpus_path": "/tmp/corpus.jsonl",
        "checkpoint_path": "/tmp/generator.pt", "epochs": 1}}
    created = client.post("/v1/training", json=request)
    assert created.status_code == 200
    job_id = created.json()["job_id"]
    assert created.json()["kind"] == "generator_training"
    assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "queued"
    assert client.get("/v1/jobs").json()["items"]
    cancelled = client.post(f"/v1/jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"/v1/jobs/{job_id}").json()["status"] == "cancelled"
    candidate = client.post("/v1/training", json={"kind": "candidate", "payload": {
        "architecture": payload(), "dataset": "cifar10"}})
    assert candidate.status_code == 422


def test_training_job_api_enforces_schema_and_resource_limits():
    client = TestClient(app)
    invalid_architecture = client.post("/v1/training", json={"kind": "candidate", "payload": {
        "architecture": {"nodes": [], "edges": []}, "epochs": 1}})
    assert invalid_architecture.status_code == 422
    excessive = client.post("/v1/training", json={"kind": "generator", "payload": {
        "corpus_path": "/tmp/corpus.jsonl", "checkpoint_path": "/tmp/model.pt", "epochs": 1001}})
    assert excessive.status_code == 422
    invalid_checksum = client.post("/v1/training", json={"kind": "predictor", "payload": {
        "benchmark_path": "/tmp/nats.tar", "benchmark_sha256": "bad", "indices": [1, 2, 3],
        "checkpoint_path": "/tmp/model.pt"}})
    assert invalid_checksum.status_code == 422


def test_training_job_api_enforces_allowed_worker_paths(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("ARCHAI_ALLOWED_PATHS", "/var/lib/archai")
    request = {"kind": "generator", "payload": {"corpus_path": "/tmp/corpus.jsonl",
        "checkpoint_path": "/var/lib/archai/model.pt", "epochs": 1}}
    response = client.post("/v1/training", json=request)
    assert response.status_code == 422
    assert "outside allowed worker paths" in response.json()["detail"]


def test_model_registry_api_registers_checksum_manifest(tmp_path):
    client = TestClient(app)
    artifact = tmp_path / "predictor.pt"
    artifact.write_bytes(b"api-model-artifact")
    model_id = f"api-test-predictor-{uuid4().hex}"
    request = {"model_id": model_id, "kind": "predictor", "version": "v1",
               "artifact_path": str(artifact), "metadata": {"seed": 4}}
    registered = client.post("/v1/models", json=request)
    assert registered.status_code == 200
    body = registered.json()
    assert body["sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()
    assert body["artifact_exists"] is True
    assert body["integrity_verified"] is True
    assert client.get(f"/v1/models/{model_id}?version=v1").json()["sha256"] == body["sha256"]
    artifact.write_bytes(b"tampered")
    assert client.get(f"/v1/models/{model_id}?version=v1").json()["integrity_verified"] is False


def test_model_registration_rejects_artifacts_outside_allowed_root(monkeypatch, tmp_path):
    client = TestClient(app)
    artifact = tmp_path / "outside.pt"
    artifact.write_bytes(b"model")
    monkeypatch.setenv("ARCHAI_ALLOWED_PATHS", "/var/lib/archai")
    response = client.post("/v1/models", json={"model_id": "outside", "kind": "predictor",
        "version": "v1", "artifact_path": str(artifact)})
    assert response.status_code == 422
    assert "outside allowed worker paths" in response.json()["detail"]


def test_experiment_api_enforces_evidence_provenance():
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    dataset = {"dataset_id": "experiment-unit", "version": "1", "checksum": "c" * 64,
               "uri": "file:///tmp/experiment-unit.bin", "license": "test"}
    assert client.post("/v1/datasets", json=dataset).status_code == 200
    base = {"architecture_id": identifier, "dataset_id": "experiment-unit", "dataset_version": "1", "seed": 3}
    assert client.post("/v1/experiments", json={**base, "evidence_type": "benchmark_lookup"}).status_code == 422
    assert client.post("/v1/experiments", json={**base, "evidence_type": "measured_training",
        "dataset_checksum": "a" * 64}).status_code == 422
    valid = client.post("/v1/experiments", json={**base, "evidence_type": "measured_training",
        "dataset_checksum": "c" * 64, "model_checkpoint": "b" * 64, "hardware": "cpu"})
    assert valid.status_code == 200


def test_experiment_api_requires_registered_matching_dataset_checksum():
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    base = {"architecture_id": identifier, "evidence_type": "benchmark_lookup",
            "dataset_id": "missing-experiment-dataset", "dataset_version": "1", "seed": 1,
            "dataset_checksum": "d" * 64}
    assert client.post("/v1/experiments", json=base).status_code == 404
    dataset = {"dataset_id": "checksum-experiment-dataset", "version": "1", "checksum": "e" * 64,
               "uri": "file:///tmp/checksum.bin", "license": "test"}
    assert client.post("/v1/datasets", json=dataset).status_code == 200
    request = {**base, "dataset_id": dataset["dataset_id"], "dataset_checksum": "d" * 64}
    assert client.post("/v1/experiments", json=request).status_code == 409


def test_readiness_and_queue_status_are_truthful():
    client = TestClient(app)
    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["durable_worker_configured"] is False
    queue = client.get("/v1/infrastructure/queue").json()
    assert queue["backend"] == "in_memory"
    assert queue["available"] is True


def test_worker_status_is_empty_for_local_backend():
    client = TestClient(app)
    response = client.get("/v1/infrastructure/workers")
    assert response.status_code == 200
    assert response.json()["workers"] == []


def test_database_readiness_probe_is_truthful(monkeypatch, tmp_path):
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path / 'ready.sqlite'}")
    from archai_api import main as api_main
    assert api_main.database_is_ready(os.environ["DATABASE_URL"]) is True
    monkeypatch.setenv("DATABASE_URL", "sqlite:////path/that/does/not/exist/archai.sqlite")
    assert api_main.database_is_ready(os.environ["DATABASE_URL"]) is False
    monkeypatch.delenv("DATABASE_URL")


def test_cors_allows_configured_studio_origin(monkeypatch):
    client = TestClient(app)
    response = client.options("/v1/architectures", headers={
        "Origin": "http://localhost:3000", "Access-Control-Request-Method": "GET"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"


def test_write_operations_honor_x_api_key(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("ARCHAI_API_KEY", "secret")
    assert client.post("/v1/searches", json={"algorithm": "random", "dataset_id": "unit", "budget_evaluations": 1}).status_code == 401
    assert client.post("/v1/searches", headers={"x-api-key": "secret"}, json={"algorithm": "random", "dataset_id": "unit", "budget_evaluations": 1}).status_code == 200
    monkeypatch.delenv("ARCHAI_API_KEY")


def test_write_operations_accept_bearer_and_hashed_keys(monkeypatch):
    import hashlib

    client = TestClient(app)
    monkeypatch.setenv("ARCHAI_API_KEY_SHA256", hashlib.sha256(b"hashed-secret").hexdigest())
    request = {"algorithm": "random", "dataset_id": "unit", "budget_evaluations": 1}
    assert client.post("/v1/searches", json=request).status_code == 401
    response = client.post("/v1/searches", headers={"Authorization": "Bearer hashed-secret"}, json=request)
    assert response.status_code == 200
    monkeypatch.delenv("ARCHAI_API_KEY_SHA256")


def test_request_size_limit_is_configurable(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("ARCHAI_MAX_REQUEST_BYTES", "10")
    assert client.post("/v1/architectures/validate", json=payload()).status_code == 413
    monkeypatch.delenv("ARCHAI_MAX_REQUEST_BYTES")


def test_request_size_limit_checks_body_without_content_length(monkeypatch):
    client = TestClient(app)
    monkeypatch.setenv("ARCHAI_MAX_REQUEST_BYTES", "10")
    request = client.build_request("POST", "/v1/architectures/validate", json=payload())
    request.headers.pop("content-length", None)
    response = client.send(request)
    assert response.status_code == 413
    monkeypatch.delenv("ARCHAI_MAX_REQUEST_BYTES")


def test_generator_endpoint_is_explicitly_unavailable_without_checkpoint(monkeypatch):
    client = TestClient(app)
    monkeypatch.delenv("ARCHAI_GENERATOR_CHECKPOINT", raising=False)
    response = client.post("/v1/architectures/generate", json={})
    assert response.status_code == 503
    assert "checkpoint" in response.json()["detail"]


def test_generator_endpoint_loads_checkpoint_and_returns_valid_architectures(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    from archai_generator.model import ArchitectureGenerator, GeneratorConfig
    from archai_generator.training import save_checkpoint

    checkpoint = tmp_path / "generator.pt"
    model = ArchitectureGenerator(GeneratorConfig(max_nodes=2))
    save_checkpoint(model, checkpoint, {"kind": "generator", "seed": 3})
    monkeypatch.setenv("ARCHAI_GENERATOR_CHECKPOINT", str(checkpoint))
    response = TestClient(app).post("/v1/architectures/generate", json={"count": 2, "seed": 7})
    assert response.status_code == 200
    body = response.json()
    assert body["count"] == 2
    assert len(body["items"]) == 2
    assert all(item["architecture_id"] for item in body["items"])


def test_write_requests_are_audited_without_leaking_credentials(monkeypatch, tmp_path):
    import json
    audit = tmp_path / "audit" / "events.jsonl"
    monkeypatch.setenv("ARCHAI_AUDIT_LOG", str(audit))
    monkeypatch.setenv("ARCHAI_API_KEY", "audit-secret-key")
    client = TestClient(app)
    assert client.post("/v1/architectures", json=payload()).status_code == 401
    assert client.post("/v1/architectures", json=payload(),
                       headers={"x-api-key": "audit-secret-key"}).status_code == 200
    client.get("/health")
    text = audit.read_text()
    assert "audit-secret-key" not in text
    events = [json.loads(line) for line in text.splitlines()]
    assert [(event["method"], event["path"], event["status"], event["outcome"]) for event in events] == [
        ("POST", "/v1/architectures", 401, "rejected"),
        ("POST", "/v1/architectures", 200, "allowed"),
    ]
    assert events[0]["credential_fingerprint"] is None
    assert events[1]["credential_fingerprint"] == hashlib.sha256(b"audit-secret-key").hexdigest()[:12]


def test_rate_limited_writes_are_audited(monkeypatch, tmp_path):
    import json

    from archai_api import main as api_main
    audit = tmp_path / "events.jsonl"
    monkeypatch.setenv("ARCHAI_AUDIT_LOG", str(audit))
    monkeypatch.setenv("ARCHAI_RATE_LIMIT_PER_MINUTE", "1")
    monkeypatch.setattr(api_main, "_rate_limiter", api_main.make_rate_limiter(""))
    client = TestClient(app)
    client.post("/v1/architectures/validate", json=payload())
    assert client.post("/v1/architectures/validate", json=payload()).status_code == 429
    statuses = [json.loads(line)["status"] for line in audit.read_text().splitlines()]
    assert statuses[-1] == 429


def test_rate_limit_response_includes_cors_headers(monkeypatch):
    from archai_api import main as api_main
    monkeypatch.setenv("ARCHAI_RATE_LIMIT_GET_PER_MINUTE", "1")
    monkeypatch.setattr(api_main, "_rate_limiter", api_main.make_rate_limiter(""))
    client = TestClient(app)
    headers = {"Origin": "http://127.0.0.1:3000"}
    assert client.get("/health", headers=headers).status_code == 200
    blocked = client.get("/health", headers=headers)
    assert blocked.status_code == 429
    assert blocked.headers.get("access-control-allow-origin") == "http://127.0.0.1:3000"
