import hashlib
import io
import json
from uuid import uuid4

import pytest
from archai_api.main import app
from fastapi.testclient import TestClient

from tests.test_api import payload


def _has_torch() -> bool:
    try:
        import torch  # noqa: F401
    except ImportError:
        return False
    return True


def test_search_algorithm_listing_covers_the_full_suite():
    items = {item["name"]: item for item in TestClient(app).get("/v1/search/algorithms").json()["items"]}
    assert set(items) == {"random", "evolution", "reinforce", "bayesian", "predictor_guided",
                          "generator_guided", "multi_objective"}
    assert items["random"]["available"] is True
    assert items["predictor_guided"]["available"] is _has_torch()
    if not _has_torch():
        assert "torch" in items["predictor_guided"]["unavailable_reason"]


def test_search_creation_validates_algorithm_and_params():
    client = TestClient(app)
    base = {"dataset_id": "cifar10", "budget_evaluations": 3}
    assert client.post("/v1/searches", json={**base, "algorithm": "reinforcement"}).status_code == 422
    assert client.post("/v1/searches", json={**base, "algorithm": "random", "params": {"beta": 1}}).status_code == 422
    created = client.post("/v1/searches", json={**base, "algorithm": "bayesian", "params": {"beta": 0.0}})
    assert created.status_code == 200 and created.json()["params"] == {"beta": 0.0}
    client.post(f"/v1/searches/{created.json()['search_id']}/cancel")


def test_architecture_json_export_is_canonical_and_checksummed():
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    response = client.get(f"/v1/architectures/{identifier}/export?format=json")
    assert response.status_code == 200
    assert response.headers["x-archai-sha256"] == hashlib.sha256(response.content).hexdigest()
    assert json.loads(response.content)["nodes"][0]["id"] == "input"
    assert client.get("/v1/architectures/missing/export").status_code == 404
    assert client.get(f"/v1/architectures/{identifier}/export?format=onnx").status_code == 422


@pytest.mark.skipif(not _has_torch(), reason="PyTorch export needs torch")
def test_pytorch_export_loads_without_archai_and_runs():
    import torch
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    response = client.get(f"/v1/architectures/{identifier}/export?format=pytorch")
    assert response.status_code == 200
    module = torch.jit.load(io.BytesIO(response.content))
    output = module(torch.randn(2, 3, 8, 8))
    assert list(output.shape)[0] == 2
    assert json.loads(response.headers["x-archai-output-shape"])[0] == 1


def test_pytorch_export_reports_unavailable_without_torch(monkeypatch):
    if _has_torch():
        import builtins
        real_import = builtins.__import__

        def blocked(name, *args, **kwargs):
            if name == "torch":
                raise ImportError("blocked for test")
            return real_import(name, *args, **kwargs)
        monkeypatch.setattr(builtins, "__import__", blocked)
    client = TestClient(app)
    identifier = client.post("/v1/architectures", json=payload()).json()["hash"]
    response = client.get(f"/v1/architectures/{identifier}/export?format=pytorch")
    assert response.status_code == 503
    assert "unavailable" in response.json()["detail"]


@pytest.mark.skipif(not _has_torch(), reason="checkpoint inspection needs torch")
def test_checkpoint_inspection_reports_tensors_and_refuses_tampered_files(tmp_path):
    import torch
    artifact = tmp_path / "model.pt"
    torch.save({"state_dict": {"layer": {"weight": torch.zeros(3, 4), "bias": torch.zeros(3)}},
                "metadata": {"kind": "predictor", "scale": "cpu_smoke"}}, artifact)
    client = TestClient(app)
    model_id = f"inspect-{uuid4().hex}"
    assert client.post("/v1/models", json={"model_id": model_id, "kind": "predictor", "version": "v1",
                                           "artifact_path": str(artifact)}).status_code == 200
    body = client.get(f"/v1/models/{model_id}/inspect").json()
    assert body["tensor_count"] == 2 and body["parameter_count"] == 15
    assert body["checkpoint_metadata"] == {"kind": "predictor", "scale": "cpu_smoke"}
    artifact.write_bytes(b"tampered")
    assert client.get(f"/v1/models/{model_id}/inspect").status_code == 409
    assert client.get("/v1/models/unknown/inspect").status_code == 404


def test_research_results_are_listed_and_names_are_restricted(monkeypatch, tmp_path):
    result = tmp_path / "unit_suite"
    result.mkdir()
    (result / "report.json").write_text(json.dumps({"algorithms": {}}))
    (result / "README.md").write_text("# measured")
    (tmp_path / "Bad Name").mkdir()
    monkeypatch.setenv("ARCHAI_RESULTS_DIR", str(tmp_path))
    client = TestClient(app)
    listing = client.get("/v1/research/results").json()
    assert [item["name"] for item in listing["items"]] == ["unit_suite"]
    detail = client.get("/v1/research/results/unit_suite").json()
    assert detail["report"] == {"algorithms": {}} and detail["readme"] == "# measured"
    assert client.get("/v1/research/results/..%2Fetc").status_code == 404
    assert client.get("/v1/research/results/missing").status_code == 404


def test_committed_research_results_are_served():
    names = [item["name"] for item in TestClient(app).get("/v1/research/results").json()["items"]]
    assert "archai_v1_smoke" in names and "nasbench201_cifar10_cpu_small" in names
