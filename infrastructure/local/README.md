# Local live stack (no Docker, no hosted services)

Verified on the box 2026-11-25 with Debian packages `postgresql` (17.12) and `redis-server`. Every
service listens on 127.0.0.1 only and is memory-capped.

```bash
# Redis: 128 MB cap, no persistence
redis-server --port 6379 --bind 127.0.0.1 --maxmemory 128mb --maxmemory-policy noeviction \
  --save "" --appendonly no --daemonize yes
# PostgreSQL: user-owned cluster, small buffers
PG=/usr/lib/postgresql/17/bin; D=/path/to/pgdata
$PG/initdb -D $D -U archai --auth=trust -E UTF8
$PG/pg_ctl -D $D -l pg.log -o "-p 5433 -c listen_addresses=127.0.0.1 -c unix_socket_directories=/tmp \
  -c shared_buffers=64MB -c max_connections=20 -c work_mem=4MB" start
psql -h 127.0.0.1 -p 5433 -U archai -d postgres -c "create database archai"

export DATABASE_URL=postgresql+psycopg://archai@127.0.0.1:5433/archai
export ARCHAI_REDIS_URL=redis://127.0.0.1:6379/0 ARCHAI_REQUIRE_REDIS=1
export ARCHAI_ALLOWED_PATHS=/tmp:/path/to/data
export ARCHAI_NATS_BENCH_PATH=/path/to/NATS-tss-v1_0-3ffb9-simple
export ARCHAI_NATS_BENCH_SHA256=<sha256_tree of that directory>
export ARCHAI_API_KEY_SHA256=<sha256 of your API key>
alembic upgrade head
uvicorn archai_api.main:app --host 127.0.0.1 --port 8000 &
python -m archai_api.worker &
python scripts/live_service_check.py --api-key <key> --dataset-checksum $ARCHAI_NATS_BENCH_SHA256 \
  --dataset-uri file://$ARCHAI_NATS_BENCH_PATH --algorithm bayesian --budget 10 --indices 0:256
ARCHAI_LIVE_REDIS_URL=redis://127.0.0.1:6379/15 ARCHAI_LIVE_DATABASE_URL=$DATABASE_URL \
  pytest tests/test_live_services.py
```

`trust` authentication is acceptable only because the cluster is bound to loopback on a single-user
box. Use password or SCRAM authentication anywhere else.
