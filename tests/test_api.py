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
