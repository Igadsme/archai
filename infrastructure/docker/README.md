# Local container deployment

Set `POSTGRES_PASSWORD` and optionally `ARCHAI_API_KEY`, then run:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up --build api web postgres redis
```

The API image installs the ML, platform, and benchmark extras, runs Alembic against PostgreSQL on startup, and connects to Redis for durable jobs. The benchmark worker mounts `datasets/raw` read-only at `/var/lib/archai/datasets`; place the verified archive there or set `ARCHAI_NATS_BENCH_PATH` to an in-container path, and provide its `ARCHAI_NATS_BENCH_SHA256`.

Enable the durable queue worker with:

```bash
docker compose -f infrastructure/docker/docker-compose.yml --profile worker up --build
```

The worker claims Redis jobs and records unsupported job kinds as failures. The current entry point registers benchmark search, candidate training, generator training, and predictor training handlers. Candidate training is explicitly limited to synthetic smoke data; predictor training requires a checksum-verified NATS-Bench archive.
