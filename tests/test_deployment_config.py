import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_api_image_contains_runtime_ml_dependencies():
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
    assert "'.[ml,platform,benchmark]'" in dockerfile
    assert "COPY pyproject.toml README.md alembic.ini ./" in dockerfile
    assert "COPY scripts ./scripts" in dockerfile


def test_web_image_installs_from_committed_lockfile():
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
    lockfile = ROOT / "apps/web/package-lock.json"
    assert lockfile.is_file()
    assert "COPY apps/web/package.json apps/web/package-lock.json ./" in dockerfile
    assert "RUN npm ci" in dockerfile
    package = json.loads((ROOT / "apps/web/package.json").read_text())
    locked = json.loads(lockfile.read_text())["packages"][""]["dependencies"]
    assert locked == package["dependencies"]


def test_web_ci_exposes_source_typecheck():
    package = (ROOT / "apps/web/package.json").read_text()
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert '"typecheck":"tsc --noEmit"' in package
    assert "npm run typecheck" in workflow


def test_postgres_schema_has_no_duplicate_experiment_columns_and_named_model_uniqueness():
    schema = (ROOT / "infrastructure/postgres/0001_initial.sql").read_text()
    assert schema.count("started_at TIMESTAMPTZ") == 1
    assert schema.count("completed_at TIMESTAMPTZ") == 1
    assert "UNIQUE (model_id, version)" in schema


def test_worker_compose_mounts_benchmark_data_and_uses_container_path():
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert "../../datasets/raw:/var/lib/archai/datasets:ro" in compose
    assert "${ARCHAI_NATS_BENCH_PATH:-/opt/archai/datasets/fixtures/natsbench-tss-cifar10-256/cells.jsonl}" in compose


def test_api_compose_passes_hashed_auth_configuration():
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert "ARCHAI_API_KEY_SHA256: ${ARCHAI_API_KEY_SHA256:-}" in compose


def test_docker_context_excludes_local_dependencies_and_artifacts():
    dockerignore = (ROOT / ".dockerignore").read_text()
    assert "**/node_modules" in dockerignore
    assert "datasets/raw" in dockerignore
    assert "*.safetensors" in dockerignore


def test_api_image_is_cpu_torch_non_root_with_healthcheck_and_proxy_headers():
    dockerfile = (ROOT / "apps/api/Dockerfile").read_text()
    assert "download.pytorch.org/whl/cpu" in dockerfile
    assert "USER 10001" in dockerfile
    assert "chown archai:archai /var/lib/archai" in dockerfile
    assert "HEALTHCHECK" in dockerfile
    assert "--proxy-headers" in dockerfile
    assert "COPY research ./research" in dockerfile


def test_web_image_bakes_api_url_at_build_time_and_runs_standalone_as_node():
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
    assert "FROM node:22-alpine" in dockerfile and "node:20" not in dockerfile
    assert "ARG NEXT_PUBLIC_ARCHAI_API_URL" in dockerfile
    assert "NEXT_OUTPUT=standalone" in dockerfile
    assert "USER node" in dockerfile
    assert 'CMD ["node", "server.js"]' in dockerfile
    config = (ROOT / "apps/web/next.config.mjs").read_text()
    assert 'process.env.NEXT_OUTPUT === "standalone"' in config
    assert "Content-Security-Policy" in config and "frame-ancestors 'none'" in config


def test_compose_wires_production_switches_and_durable_redis():
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert "ARCHAI_ENV: ${ARCHAI_ENV:-development}" in compose
    assert "ARCHAI_PROTECT_READS" in compose
    assert "NEXT_PUBLIC_ARCHAI_API_URL: ${ARCHAI_PUBLIC_API_URL:-http://localhost:8000}" in compose
    assert '"--appendonly", "yes"' in compose
    assert "archai-redis:/data" in compose
    assert "--proxy-headers" in compose
    assert "restart: unless-stopped" in compose


def test_env_example_lists_every_compose_variable_without_secrets():
    import re
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    example = (ROOT / ".env.example").read_text()
    variables = set(re.findall(r"\$\{([A-Z0-9_]+)", compose)) - {"ARCHAI_API_PORT", "ARCHAI_WEB_PORT"}
    documented = set(re.findall(r"^#?\s*([A-Z0-9_]+)=", example, flags=re.MULTILINE))
    assert variables <= documented, sorted(variables - documented)
    for line in example.splitlines():
        if line.startswith(("POSTGRES_PASSWORD=", "ARCHAI_API_KEY_SHA256=", "ARCHAI_NATS_BENCH_SHA256=")):
            assert line.endswith("="), line


def test_render_runs_in_production_mode_behind_the_proxy():
    render = (ROOT / "render.yaml").read_text()
    assert "key: ARCHAI_ENV\n        value: production" in render
    assert "--proxy-headers" in render


def test_ci_is_least_privilege_and_audits_dependencies_and_images():
    workflow = (ROOT / ".github/workflows/ci.yml").read_text()
    assert "permissions:\n  contents: read" in workflow
    assert "pip-audit" in workflow
    assert "npm audit --audit-level=high" in workflow
    assert "docker build -f apps/api/Dockerfile" in workflow
    assert "docker build -f apps/web/Dockerfile" in workflow
    assert (ROOT / ".github/dependabot.yml").is_file()


def test_compose_runs_migrations_and_generator_training_before_the_api():
    compose = (ROOT / "infrastructure/docker/docker-compose.yml").read_text()
    assert 'command: ["alembic", "upgrade", "head"]' in compose
    assert "migrate: {condition: service_completed_successfully}" in compose
    assert "generator-init: {condition: service_completed_successfully}" in compose
    assert "scripts/train_generator_local.py" in compose
    assert "ARCHAI_CHECKPOINT_DIR: /var/lib/archai/checkpoints" in compose


def test_init_env_creates_secrets_without_printing_them(tmp_path, capsys):
    import hashlib
    import importlib.util
    import stat

    spec = importlib.util.spec_from_file_location("init_env", ROOT / "scripts/local/init_env.py")
    init_env = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(init_env)
    (tmp_path / ".env.example").write_text((ROOT / ".env.example").read_text())
    assert init_env.main(["--root", str(tmp_path)]) == 0
    env = init_env.parse((tmp_path / ".env").read_text())
    key = (tmp_path / ".archai/bootstrap-api-key").read_text().strip()
    assert len(env["POSTGRES_PASSWORD"]) == 48 and env["ARCHAI_REQUIRE_API_KEY"] == "1"
    assert env["ARCHAI_API_KEY_SHA256"] == hashlib.sha256(key.encode()).hexdigest()
    assert stat.S_IMODE((tmp_path / ".env").stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / ".archai/bootstrap-api-key").stat().st_mode) == 0o600
    printed = capsys.readouterr().out
    assert key not in printed and env["POSTGRES_PASSWORD"] not in printed
    first = dict(env)
    assert init_env.main(["--root", str(tmp_path)]) == 0
    assert init_env.parse((tmp_path / ".env").read_text()) == first
    assert init_env.main(["--root", str(tmp_path), "--rotate-key"]) == 0
    rotated = init_env.parse((tmp_path / ".env").read_text())
    assert rotated["ARCHAI_API_KEY_SHA256"] != first["ARCHAI_API_KEY_SHA256"]
    assert rotated["POSTGRES_PASSWORD"] == first["POSTGRES_PASSWORD"]
