# Local container deployment

Set `POSTGRES_PASSWORD` and optionally `ARCHAI_API_KEY`, then run:

```bash
docker compose -f infrastructure/docker/docker-compose.yml up --build api web postgres redis
```

The worker profile intentionally exits until a durable worker implementation is configured. This prevents a container from silently claiming to execute experiments while doing no work.
