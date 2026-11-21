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


def test_search_and_experiment_lifecycle_surface():
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    search = client.post("/v1/searches", json={"algorithm": "random", "dataset_id": "unit",
                                               "budget_evaluations": 2, "seed": 7})
    assert search.status_code == 200
    search_id = search.json()["search_id"]
    assert client.get(f"/v1/searches/{search_id}").json()["status"] == "created"
    assert client.post(f"/v1/searches/{search_id}/start").status_code == 503
    experiment = client.post("/v1/experiments", json={"architecture_id": identifier,
        "evidence_type": "predicted", "dataset_id": "unit", "dataset_version": "1", "seed": 7})
    assert experiment.status_code == 200
    assert client.get(f"/v1/experiments/{experiment.json()['experiment_id']}").status_code == 200
    assert client.get("/v1/models").status_code == 200
