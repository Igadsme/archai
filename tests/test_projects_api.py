from archai_api.main import app
from fastapi.testclient import TestClient


def test_project_crud_and_archived_projects_cannot_accept_search():
    client = TestClient(app)
    created = client.post("/v1/projects", json={"name": "  CIFAR-10 search  ", "task": "cifar10",
                                                 "description": "budgeted lookup",
                                                 "constraints": {"max_parameters": 800000, "allowed_ops": ["nor_conv_3x3", "skip_connect", "none", "avg_pool_3x3", "nor_conv_1x1"]}})
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["name"] == "CIFAR-10 search" and body["status"] == "active"
    project_id = body["project_id"]
    assert client.get("/v1/projects").json()["items"][0]["project_id"] == project_id
    assert client.get(f"/v1/projects/{project_id}").json()["task"] == "cifar10"
    patched = client.patch(f"/v1/projects/{project_id}", json={"description": "updated"})
    assert patched.status_code == 200 and patched.json()["description"] == "updated"
    # unknown or empty id
    assert client.get("/v1/projects/missing123").status_code == 404
    assert client.post("/v1/searches", json={"algorithm": "random", "dataset_id": "cifar10",
                                              "budget_evaluations": 2, "seed": 0, "project_id": "missing123"}).status_code == 404
    # archive, then refuse new search
    assert client.patch(f"/v1/projects/{project_id}", json={"status": "archived"}).json()["status"] == "archived"
    refused = client.post("/v1/searches", json={"algorithm": "random", "dataset_id": "cifar10",
                                                 "budget_evaluations": 2, "seed": 0, "project_id": project_id})
    assert refused.status_code == 409


def test_project_constraints_are_validated():
    client = TestClient(app)
    bad = client.post("/v1/projects", json={"name": "x", "task": "cifar10", "constraints": {"allowed_ops": ["nope"]}})
    assert bad.status_code == 422
