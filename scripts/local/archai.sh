#!/usr/bin/env bash
# One-command local ArchAI stack (Postgres, Redis, migrations, API, worker, Studio) on Docker.
#
#   scripts/local/archai.sh up       build if needed, start everything, wait until healthy
#   scripts/local/archai.sh status   container state plus API readiness
#   scripts/local/archai.sh logs [service]
#   scripts/local/archai.sh key      print the bootstrap API key file path (not the key)
#   scripts/local/archai.sh smoke    check health, readiness, auth, generator and Studio over HTTP
#   scripts/local/archai.sh down     stop containers, keep data
#   scripts/local/archai.sh reset    stop and delete all local data volumes (asks first)
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT/infrastructure/docker/docker-compose.yml"
ENV_FILE="$ROOT/.env"
KEY_FILE="$ROOT/.archai/bootstrap-api-key"
export COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-archai}"

compose() { docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"; }
env_value() { sed -n "s/^$1=//p" "$ENV_FILE" | tail -n 1; }

require_docker() {
  if ! command -v docker >/dev/null 2>&1; then
    echo "docker is not installed. On macOS install Docker Desktop: https://www.docker.com/products/docker-desktop/" >&2
    exit 1
  fi
  if ! docker info >/dev/null 2>&1; then
    echo "Docker is installed but not running. Start Docker Desktop and retry." >&2
    exit 1
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "docker compose v2 is required (bundled with Docker Desktop)." >&2
    exit 1
  fi
}

urls() {
  local api_port web_port
  api_port="$(env_value ARCHAI_API_PORT)"; web_port="$(env_value ARCHAI_WEB_PORT)"
  echo "Studio:   http://localhost:${web_port:-3000}"
  echo "API:      http://localhost:${api_port:-8000}   (docs: http://localhost:${api_port:-8000}/docs)"
  echo "API key:  ${KEY_FILE#"$ROOT"/}  (paste its contents into Studio > API KEY; it is an admin key)"
}

smoke() {
  local api="http://localhost:$(env_value ARCHAI_API_PORT | grep . || echo 8000)"
  local web="http://localhost:$(env_value ARCHAI_WEB_PORT | grep . || echo 3000)"
  local key; key="$(tr -d '[:space:]' <"$KEY_FILE")"
  local failed=0
  check() { if eval "$2" >/dev/null 2>&1; then echo "ok    $1"; else echo "FAIL  $1"; failed=1; fi; }
  check "API /health" "curl -fsS $api/health"
  check "API /readiness (Postgres + Redis)" "curl -fsS $api/readiness"
  check "auth on: write without a key is refused" "test \"\$(curl -s -o /dev/null -w '%{http_code}' -X POST $api/v1/projects -H 'content-type: application/json' -d '{\"name\":\"x\",\"task\":\"y\"}')\" = 401"
  check "bootstrap key authenticates as admin" "curl -fsS $api/v1/auth/whoami -H 'x-api-key: $key' | grep -q '\"admin\"'"
  check "worker heartbeat" "curl -fsS $api/v1/infrastructure/workers -H 'x-api-key: $key' | grep -q worker_id"
  check "generator checkpoint serves candidates" "curl -fsS -X POST $api/v1/architectures/generate -H 'x-api-key: $key' -H 'content-type: application/json' -d '{\"count\":1}' | grep -q architecture_id"
  check "Studio responds" "curl -fsS -o /dev/null $web/"
  return "$failed"
}

command="${1:-up}"
case "$command" in
  up)
    require_docker
    python3 "$ROOT/scripts/local/init_env.py"
    echo "Building and starting the stack (first build downloads ~1.5 GB and takes several minutes)…"
    compose up -d --build --wait --wait-timeout "${ARCHAI_WAIT_TIMEOUT:-900}"
    compose ps
    echo
    urls
    ;;
  status) require_docker; compose ps; curl -fsS "http://localhost:$(env_value ARCHAI_API_PORT | grep . || echo 8000)/readiness" && echo ;;
  logs) require_docker; shift; compose logs -f --tail 200 "$@" ;;
  key) echo "${KEY_FILE#"$ROOT"/}"; [[ -f "$KEY_FILE" ]] || { echo "not created yet; run: scripts/local/archai.sh up" >&2; exit 1; } ;;
  smoke) smoke ;;
  urls) urls ;;
  down) require_docker; compose down ;;
  reset)
    require_docker
    read -r -p "Delete the local Postgres, Redis and artifact volumes (all ArchAI data)? [y/N] " answer
    [[ "$answer" == [yY] ]] || { echo "cancelled"; exit 1; }
    compose down -v
    ;;
  *) sed -n '2,11p' "$0"; exit 2 ;;
esac
