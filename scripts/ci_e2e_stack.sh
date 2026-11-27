#!/usr/bin/env bash
# Start a fixture-only Studio stack and run the browser E2E. Not a research result.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

WORKDIR="${ARCHAI_CI_WORKDIR:-/tmp/archai-ci-e2e}"
mkdir -p "$WORKDIR"
KEY_FILE="$WORKDIR/api-key"
CKPT="$WORKDIR/generator-ci.pt"
LOG_DIR="$WORKDIR/logs"
mkdir -p "$LOG_DIR"

FIXTURE_CELLS="$ROOT/datasets/fixtures/natsbench-tss-cifar10-256/cells.jsonl"
FIXTURE_SHA="4a4b956ad6ae53b9d0b17fcf04b4935d17db030661afe23bbdb111c27ac5a148"

if [[ ! -f "$FIXTURE_CELLS" ]]; then
  echo "missing fixture: $FIXTURE_CELLS" >&2
  exit 1
fi

export KEY_FILE
if [[ ! -f "$KEY_FILE" ]]; then
  python - <<'PY'
import secrets
from pathlib import Path
import os
path = Path(os.environ["KEY_FILE"])
path.write_text(secrets.token_urlsafe(32) + "\n")
path.chmod(0o600)
PY
fi

export DATABASE_URL="${DATABASE_URL:?DATABASE_URL is required}"
export ARCHAI_REDIS_URL="${ARCHAI_REDIS_URL:?ARCHAI_REDIS_URL is required}"
export ARCHAI_REQUIRE_REDIS="${ARCHAI_REQUIRE_REDIS:-1}"
export ARCHAI_ALLOWED_PATHS="${ARCHAI_ALLOWED_PATHS:-$ROOT:$WORKDIR:/tmp}"
export ARCHAI_NATS_BENCH_PATH="$FIXTURE_CELLS"
export ARCHAI_NATS_BENCH_SHA256="$FIXTURE_SHA"
export ARCHAI_BENCHMARK_CACHE="$WORKDIR/benchmark-cache.sqlite"
export ARCHAI_AUDIT_LOG="$WORKDIR/audit.jsonl"
export ARCHAI_ARTIFACT_STORE="$WORKDIR/artifacts"
export ARCHAI_GENERATOR_CHECKPOINT="$CKPT"
export ARCHAI_API_KEY="$(tr -d '[:space:]' < "$KEY_FILE")"
export ARCHAI_RATE_LIMIT_PER_MINUTE="${ARCHAI_RATE_LIMIT_PER_MINUTE:-300}"
export ARCHAI_RATE_LIMIT_GET_PER_MINUTE="${ARCHAI_RATE_LIMIT_GET_PER_MINUTE:-2000}"
export ARCHAI_CORS_ORIGINS="${ARCHAI_CORS_ORIGINS:-http://127.0.0.1:3000,http://localhost:3000}"
export NEXT_PUBLIC_ARCHAI_API_URL="${NEXT_PUBLIC_ARCHAI_API_URL:-http://127.0.0.1:8000}"
export ARCHAI_E2E_API_KEY_FILE="$KEY_FILE"
export ARCHAI_E2E_CHECKPOINT="$CKPT"
export ARCHAI_E2E_BUDGET="${ARCHAI_E2E_BUDGET:-8}"
export ARCHAI_E2E_INDICES="${ARCHAI_E2E_INDICES:-0:256}"
export STUDIO_URL="${STUDIO_URL:-http://127.0.0.1:3000}"
export API_URL="${API_URL:-http://127.0.0.1:8000}"
export SCREENS="${SCREENS:-$WORKDIR/screens}"

python -m alembic upgrade head

# Save a tiny default-vocabulary generator. /v1/architectures/generate uses sample(),
# which only builds graphs from GENERATABLE_OPS (not NAS-Bench-201 tokens). This
# checkpoint is fixture-only and is not a research result.
python - <<'PY'
from pathlib import Path
import os
from archai_generator.model import ArchitectureGenerator, GeneratorConfig
from archai_generator.training import save_checkpoint

path = Path(os.environ["ARCHAI_GENERATOR_CHECKPOINT"])
model = ArchitectureGenerator(GeneratorConfig(latent_dim=8, hidden_dim=64, max_nodes=6, condition_dim=8))
save_checkpoint(model, path, {"model": "ArchAI-V1", "kind": "generator", "scale": "ci_fixture",
                              "label": "fixture-only", "not_a_research_result": True})
print(f"wrote CI generator checkpoint ({path.stat().st_size} bytes)")
PY

cleanup() {
  for pidfile in "$LOG_DIR"/api.pid "$LOG_DIR"/worker.pid "$LOG_DIR"/studio.pid; do
    if [[ -f "$pidfile" ]]; then
      pid="$(cat "$pidfile" || true)"
      if [[ -n "${pid:-}" ]] && kill -0 "$pid" 2>/dev/null; then
        kill "$pid" 2>/dev/null || true
        wait "$pid" 2>/dev/null || true
      fi
    fi
  done
}
trap cleanup EXIT

python -m uvicorn archai_api.main:app --host 127.0.0.1 --port 8000 >"$LOG_DIR/api.log" 2>&1 &
echo $! >"$LOG_DIR/api.pid"
python -m archai_api.worker >"$LOG_DIR/worker.log" 2>&1 &
echo $! >"$LOG_DIR/worker.pid"

# Studio must already be built (npm run build) with NEXT_PUBLIC_ARCHAI_API_URL.
(cd "$ROOT/apps/web" && exec ./node_modules/.bin/next start --hostname 127.0.0.1 --port 3000) >"$LOG_DIR/studio.log" 2>&1 &
echo $! >"$LOG_DIR/studio.pid"

wait_http() {
  local url="$1" name="$2"
  for _ in $(seq 1 60); do
    if curl -sf "$url" >/dev/null; then
      echo "$name is up"
      return 0
    fi
    sleep 1
  done
  echo "$name failed to become ready: $url" >&2
  tail -n 80 "$LOG_DIR"/*.log >&2 || true
  return 1
}

wait_http "http://127.0.0.1:8000/health" "API health"
wait_http "http://127.0.0.1:8000/readiness" "API readiness"
wait_http "http://127.0.0.1:3000" "Studio"

# Unset the process env key so child logs are less likely to echo it; E2E reads the file.
unset ARCHAI_API_KEY
if ! (cd "$ROOT/apps/web" && node e2e/studio.e2e.mjs); then
  echo "E2E failed; last worker/api log lines (fixture-only stack):" >&2
  tail -n 80 "$LOG_DIR/worker.log" "$LOG_DIR/api.log" >&2 || true
  exit 1
fi
