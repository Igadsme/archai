import pytest
from fastapi.testclient import TestClient

from archai_api.main import app


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


def test_search_and_experiment_lifecycle_surface():
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
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


def test_readiness_and_queue_status_are_truthful():
    client = TestClient(app)
    readiness = client.get("/readiness")
    assert readiness.status_code == 200
    assert readiness.json()["durable_worker_configured"] is False
    queue = client.get("/v1/infrastructure/queue").json()
    assert queue["backend"] == "in_memory"


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
    torch = pytest.importorskip("torch")
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
