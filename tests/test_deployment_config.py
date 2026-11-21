from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_api_image_contains_runtime_ml_dependencies():
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
    assert "'.[ml,platform,benchmark]'" in dockerfile
    assert "COPY pyproject.toml README.md alembic.ini ./" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile


def test_web_image_does_not_require_untracked_lockfile():
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
    assert "package-lock.json" not in dockerfile


def test_postgres_schema_has_no_duplicate_experiment_columns_and_named_model_uniqueness():
    schema = (ROOT / "infrastructure/postgres/0001_initial.sql").read_text()
    assert schema.count("started_at TIMESTAMPTZ") == 1
    assert schema.count("completed_at TIMESTAMPTZ") == 1
    assert "UNIQUE (model_id, version)" in schema


def test_worker_compose_mounts_benchmark_data_and_uses_container_path():
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert "../../datasets/raw:/var/lib/archai/datasets:ro" in compose
    assert "/var/lib/archai/datasets/natsbench.tfrecord" in compose


def test_api_compose_passes_hashed_auth_configuration():
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert "ARCHAI_API_KEY_SHA256: ${ARCHAI_API_KEY_SHA256:-}" in compose


def test_docker_context_excludes_local_dependencies_and_artifacts():
    dockerignore = (ROOT / ".dockerignore").read_text()
    assert "**/node_modules" in dockerignore
    assert "datasets/raw" in dockerignore
    assert "*.safetensors" in dockerignore
