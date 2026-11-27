import pytest
from archai_api.main import app
from fastapi.testclient import TestClient


def _client_with_generator(monkeypatch, tmp_path):
    pytest.importorskip("torch")
    from archai_generator.model import ArchitectureGenerator, GeneratorConfig
    from archai_generator.training import save_checkpoint

    checkpoint = tmp_path / "generator.pt"
    model = ArchitectureGenerator(GeneratorConfig(max_nodes=2))
    save_checkpoint(model, checkpoint, {"kind": "generator", "seed": 3})
    monkeypatch.setenv("ARCHAI_GENERATOR_CHECKPOINT", str(checkpoint))
    return TestClient(app)


def test_generate_rejects_unevaluable_latency_constraints(monkeypatch, tmp_path):
    client = _client_with_generator(monkeypatch, tmp_path)
    response = client.post("/v1/architectures/generate", json={
        "count": 1, "seed": 0, "constraints": {"max_latency_s": 0.01}})
    assert response.status_code == 422
    detail = response.json()["detail"]
    assert "max_latency_s" in detail["unevaluable"]


def test_generate_filters_to_a_parameter_budget(monkeypatch, tmp_path):
    client = _client_with_generator(monkeypatch, tmp_path)
    loose = client.post("/v1/architectures/generate", json={"count": 1, "seed": 0, "constraints": {"max_parameters": 10**12}})
    assert loose.status_code == 200, loose.text
    assert loose.json()["count"] == 1 and loose.json()["rejected"] == 0
    tight = client.post("/v1/architectures/generate", json={"count": 1, "seed": 0, "constraints": {"max_parameters": 1}})
    assert tight.status_code == 200, tight.text
    assert tight.json()["rejected"] >= 1
    from archai_compiler.metrics import analytical_metrics
    from archai_core.schema import Architecture
    params = analytical_metrics(Architecture.model_validate(tight.json()["items"][0]["architecture"])).parameters
    assert params <= 1
    impossible = client.post("/v1/architectures/generate", json={
        "count": 1, "seed": 0, "constraints": {"max_parameters": 1, "allowed_ops": ["conv3x3", "conv1x1"]}})
    assert impossible.status_code == 422
    assert impossible.json()["detail"]["rejected"] >= 1


def test_search_payload_merges_project_constraints():
    client = TestClient(app)
    created = client.post("/v1/projects", json={"name": "budgeted", "task": "cifar10",
                                                 "constraints": {"max_parameters": 800000}})
    project_id = created.json()["project_id"]
    search = client.post("/v1/searches", json={"algorithm": "random", "dataset_id": "cifar10",
                                               "budget_evaluations": 2, "seed": 0, "project_id": project_id,
                                               "constraints": {"max_flops": 50000000}})
    assert search.status_code == 200, search.text
    body = search.json()
    assert body["constraints"]["max_parameters"] == 800000
    assert body["constraints"]["max_flops"] == 50000000
