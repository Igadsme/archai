# Local container deployment

Start everything with one command from the repository root:

```bash
scripts/local/archai.sh up
```

That runs `scripts/local/init_env.py` (creates `.env` from `.env.example`, a random Postgres password, and a bootstrap API key stored in `.archai/bootstrap-api-key`, with only its SHA-256 in `.env`) and then:

```bash
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml up -d --build --wait
```

Services:

- `postgres` and `redis` keep their data in named volumes. Redis uses append-only persistence so queued jobs survive restarts.
- `migrate` is a one-shot `alembic upgrade head`; the API and worker wait for it.
- `generator-init` is a one-shot that trains the small CPU generator checkpoint into the artifact volume if it is missing (`ARCHAI_TRAIN_GENERATOR=0` skips it; see `docs/GENERATOR.md`).
- `api` serves on `127.0.0.1:8000` and is healthy once `/readiness` reports Postgres and Redis reachable.
- `worker` runs benchmark search and training jobs. Candidate checkpoints go to `/var/lib/archai/checkpoints` in the shared volume, so the API can register and deploy them. Benchmark search defaults to the bundled 256-cell NATS-Bench fixture (fixture-only); mount the verified archive under `datasets/raw` (read-only at `/var/lib/archai/datasets`) and set `ARCHAI_NATS_BENCH_PATH` and `ARCHAI_NATS_BENCH_SHA256` for real searches.
- `web` (the Studio) serves on `127.0.0.1:3000`, with the API URL built in at image build time (`ARCHAI_PUBLIC_API_URL`).

For deployed environments, prefer `ARCHAI_API_KEY_SHA256` so the plaintext credential is not placed in the service environment. Clients send the original key with `x-api-key` or `Authorization: Bearer ...`.

The root `.dockerignore` excludes local dependency trees, raw datasets, checkpoints, caches, AppleDouble files and VCS metadata from build contexts.

macOS walkthrough, upgrades, backups and troubleshooting: `docs/deploy/LOCAL.md`.
