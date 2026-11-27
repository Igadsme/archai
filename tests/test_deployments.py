import importlib.util
from uuid import uuid4

import pytest
from archai_api import main as api_main
from archai_api.deployments import InMemoryDeploymentStore
from archai_api.identity import IdentityService, InMemoryIdentityStore
from fastapi.testclient import TestClient

HAS_TORCH = importlib.util.find_spec("torch") is not None
pytestmark = pytest.mark.skipif(not HAS_TORCH, reason="torch is not installed")


def architecture(channels=8):
    return {"nodes": [{"id": "input", "op": "input", "channels": 3},
                      {"id": "conv", "op": "conv3x3", "channels": channels},
                      {"id": "output", "op": "output", "channels": channels}],
            "edges": [{"source": "input", "target": "conv"}, {"source": "conv", "target": "output"}],
            "input_spec": {"channels": 3, "height": 8, "width": 8}, "output_classes": 4}


@pytest.fixture
def client(monkeypatch):
    for name in ("ARCHAI_API_KEY", "ARCHAI_API_KEY_SHA256", "ARCHAI_PROTECT_READS"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(api_main, "_identity", IdentityService(InMemoryIdentityStore()))
    monkeypatch.setattr(api_main, "_deployment_store", InMemoryDeploymentStore())
    monkeypatch.setattr(api_main, "_runtime", None)
    return TestClient(api_main.app)


def _register(client, channels=8):
    response = client.post("/v1/architectures", json=architecture(channels))
    assert response.status_code == 200, response.text
    return response.json()["hash"]


def _checkpoint(client, tmp_path, architecture_id, *, channels=8):
    import torch
    from archai_api.deployments import build_model
    from archai_core.schema import Architecture

    model = build_model(Architecture.model_validate(architecture(channels)), None)
    for parameter in model.parameters():
        torch.nn.init.constant_(parameter, 0.01)
    path = tmp_path / f"candidate-{channels}.pt"
    torch.save({"epoch": 1, "model_state": model.state_dict()}, path)
    model_id = f"candidate-{uuid4().hex[:8]}"
    response = client.post("/v1/models", json={"model_id": model_id, "kind": "candidate", "version": "1",
                                               "artifact_path": str(path)})
    assert response.status_code == 200, response.text
    return model_id, path


def test_untrained_deployment_serves_and_is_labelled(client):
    architecture_id = _register(client)
    created = client.post("/v1/deployments", json={"name": "untrained", "architecture_id": architecture_id})
    assert created.status_code == 200, created.text
    deployment = created.json()
    assert deployment["status"] == "active" and deployment["trained"] is False
    assert deployment["weights"].startswith("untrained")
    assert deployment["input_shape"] == [3, 8, 8]
    result = client.post(deployment["predict_path"], json={"input": "random", "batch_size": 2, "seed": 3}).json()
    assert result["output_shape"] == [2, 4] and len(result["predicted_class"]) == 2
    assert result["trained"] is False and result["input_source"] == "random normal (seed=3)"
    assert result["latency_ms"] > 0
    again = client.post(deployment["predict_path"], json={"input": "random", "batch_size": 2, "seed": 3}).json()
    assert again["logits"] == result["logits"]
    listed = client.get("/v1/deployments").json()["items"]
    assert listed[0]["stats"]["request_count"] == 2 and listed[0]["loaded"] is True


def test_checkpoint_deployment_loads_verified_weights(client, tmp_path):
    architecture_id = _register(client)
    model_id, _path = _checkpoint(client, tmp_path, architecture_id)
    deployment = client.post("/v1/deployments", json={"name": "trained", "architecture_id": architecture_id,
                                                      "model_id": model_id}).json()
    assert deployment["trained"] is True and deployment["model"]["model_id"] == model_id
    inputs = [[[[1.0] * 8 for _ in range(8)] for _ in range(3)]]
    result = client.post(deployment["predict_path"], json={"inputs": inputs})
    assert result.status_code == 200, result.text
    assert result.json()["input_source"] == "caller" and "verified on load" in result.json()["weights"]
    bad = client.post(deployment["predict_path"], json={"inputs": [[[0.0]]]})
    assert bad.status_code == 422
    assert client.post(deployment["predict_path"], json={}).status_code == 422


def test_mismatched_or_tampered_checkpoints_are_refused(client, tmp_path):
    architecture_id = _register(client)
    other = _register(client, channels=16)
    model_id, path = _checkpoint(client, tmp_path, other, channels=16)
    mismatch = client.post("/v1/deployments", json={"name": "x", "architecture_id": architecture_id,
                                                    "model_id": model_id})
    assert mismatch.status_code == 422 and "does not match" in mismatch.json()["detail"]
    deployment = client.post("/v1/deployments", json={"name": "y", "architecture_id": other,
                                                      "model_id": model_id}).json()
    client.post(f"/v1/deployments/{deployment['deployment_id']}/stop")
    path.write_bytes(path.read_bytes() + b"tampered")
    started = client.post(f"/v1/deployments/{deployment['deployment_id']}/start")
    assert started.status_code == 409
    assert client.post("/v1/deployments", json={"name": "z", "architecture_id": "missing"}).status_code == 404
    assert client.post("/v1/deployments", json={"name": "z", "architecture_id": architecture_id,
                                                "model_id": "missing"}).status_code == 404


def test_stop_start_delete_lifecycle(client):
    architecture_id = _register(client)
    deployment = client.post("/v1/deployments", json={"name": "life", "architecture_id": architecture_id}).json()
    deployment_id = deployment["deployment_id"]
    assert client.post(f"/v1/deployments/{deployment_id}/stop").json()["status"] == "stopped"
    assert client.post(deployment["predict_path"], json={"input": "zeros"}).status_code == 409
    assert client.post(f"/v1/deployments/{deployment_id}/start").json()["status"] == "active"
    assert client.post(deployment["predict_path"], json={"input": "zeros"}).status_code == 200
    assert client.delete(f"/v1/deployments/{deployment_id}").status_code == 200
    assert client.get(f"/v1/deployments/{deployment_id}").status_code == 404


def test_read_scoped_keys_can_predict_but_not_deploy(client):
    admin_user = client.post("/v1/users", json={"email": "admin@example.org", "role": "admin"}).json()
    admin = client.post("/v1/api-keys", json={"user_id": admin_user["user_id"], "name": "admin",
                                              "scopes": ["admin"]}).json()
    headers = {"x-api-key": admin["secret"]}
    member = client.post("/v1/users", json={"email": "m@example.org"}, headers=headers).json()
    reader = {"x-api-key": client.post("/v1/api-keys", json={"user_id": member["user_id"], "name": "ro",
                                                             "scopes": ["read"]}, headers=headers).json()["secret"]}
    architecture_id = client.post("/v1/architectures", json=architecture(), headers=headers).json()["hash"]
    body = {"name": "scoped", "architecture_id": architecture_id}
    assert client.post("/v1/deployments", json=body, headers=reader).status_code == 403
    deployment = client.post("/v1/deployments", json=body, headers=headers).json()
    assert deployment["created_by"]
    assert client.post(deployment["predict_path"], json={"input": "zeros"}).status_code == 401
    assert client.post(deployment["predict_path"], json={"input": "zeros"}, headers=reader).status_code == 200


def test_sqlalchemy_deployment_store_round_trip(tmp_path):
    from archai_api.db import SqlAlchemyArchitectureStore, SqlAlchemyDeploymentStore
    from archai_core.schema import Architecture

    url = f"sqlite:///{tmp_path / 'deploy.db'}"
    SqlAlchemyArchitectureStore.from_url(url, initialize=True).put(Architecture.model_validate(architecture()))
    architecture_id = Architecture.model_validate(architecture()).content_hash()
    store = SqlAlchemyDeploymentStore.from_url(url, initialize=True)
    record = {"deployment_id": "d1", "architecture_id": architecture_id, "status": "active",
              "created_at": "2026-01-01T00:00:00+00:00", "stats": {"request_count": 0}}
    store.put(record)
    store.put({**record, "status": "stopped"})
    assert store.get("d1")["status"] == "stopped"
    assert [item["deployment_id"] for item in store.list()] == ["d1"]
    assert store.delete("d1") and store.get("d1") is None
