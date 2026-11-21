from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_api_image_contains_runtime_ml_dependencies():
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
    assert "'.[ml,platform,benchmark]'" in dockerfile


def test_web_image_does_not_require_untracked_lockfile():
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
    assert "package-lock.json" not in dockerfile


def test_postgres_schema_has_no_duplicate_experiment_columns_and_named_model_uniqueness():
    schema = (ROOT / "infrastructure/postgres/0001_initial.sql").read_text()
    assert schema.count("started_at TIMESTAMPTZ") == 1
    assert schema.count("completed_at TIMESTAMPTZ") == 1
    assert "UNIQUE (model_id, version)" in schema
