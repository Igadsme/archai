# Local container deployment

Set `POSTGRES_PASSWORD` and optionally `ARCHAI_API_KEY`, then run:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up --build api web postgres redis
```

Enable the durable queue worker with:

```bash
docker compose -f infrastructure/docker/docker-compose.yml --profile worker up --build
```

The generic worker claims Redis jobs and records unsupported job kinds as failures. Search/training handlers must be registered by the experiment service before production execution is enabled.
