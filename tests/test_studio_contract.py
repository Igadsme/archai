"""The Studio forms and the API must agree on request shapes.

``apps/web/app/lib/fixtures/requests.json`` is produced by the Studio form builders (asserted by
``apps/web/tests/forms.test.ts``); here the API must accept every fixture unchanged.
"""
import json
from pathlib import Path

from archai_api.main import app
from fastapi.testclient import TestClient

FIXTURES = json.loads((Path(__file__).resolve().parents[1] / "apps/web/app/lib/fixtures/requests.json").read_text())


def test_api_accepts_studio_search_request():
    client = TestClient(app)
    created = client.post("/v1/searches", json=FIXTURES["search"])
    assert created.status_code == 200, created.text
    assert created.json()["indices"] == FIXTURES["search"]["indices"]
    assert client.post(f"/v1/searches/{created.json()['search_id']}/cancel").status_code == 200


def test_api_accepts_every_studio_training_request():
    client = TestClient(app)
    expected_kinds = {"candidate": "training", "generator": "generator_training",
                      "predictor": "predictor_training"}
    for name, kind in expected_kinds.items():
        created = client.post("/v1/training", json=FIXTURES[name])
        assert created.status_code == 200, (name, created.text)
        assert created.json()["kind"] == kind
        assert client.post(f"/v1/jobs/{created.json()['job_id']}/cancel").status_code == 200


def test_studio_policy_list_matches_the_backend_registry():
    from archai_benchmark.policy_registry import ALGORITHMS
    assert FIXTURES["algorithms"] == list(ALGORITHMS)


def test_studio_hypervolume_fixture_matches_python():
    from archai_benchmark.research_metrics import hypervolume_2d
    fixture = json.loads((Path(__file__).resolve().parents[1] / "apps/web/app/lib/fixtures/pareto.json").read_text())
    points = [(p["validation_accuracy"], p["params_m"]) for p in fixture["points"]]
    assert hypervolume_2d(points, tuple(fixture["reference"])) == fixture["hypervolume"]
