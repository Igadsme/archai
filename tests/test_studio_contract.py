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
