# Production deployment checklist

Two supported shapes: a single host with Docker Compose, or the free hosted path
(Render API + Vercel Studio + Neon Postgres + Upstash Redis, see `HOSTING_RUNBOOK.md`).
Variable reference: `ENV.md`. Security model: `../../SECURITY.md`.

## 1. Secrets (never committed)

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"   # the write key: give it to Studio users
printf %s '<key>' | sha256sum | cut -d' ' -f1                    # ARCHAI_API_KEY_SHA256 for the API host
```

Also needed: a Postgres URL (`DATABASE_URL`, `postgresql+psycopg://…`), a Redis URL
(`ARCHAI_REDIS_URL`, `rediss://` for hosted Redis), and the public Studio origin for CORS.

## 2. Required API settings

| Variable | Value |
| --- | --- |
| `ARCHAI_ENV` | `production` (the API refuses to boot if any setting below is unsafe) |
| `ARCHAI_API_KEY_SHA256` | hash from step 1 |
| `ARCHAI_CORS_ORIGINS` | `https://<studio-host>` only |
| `DATABASE_URL` / `ARCHAI_REDIS_URL` | managed services; migrations run with `alembic upgrade head` before the app starts |
| `ARCHAI_ALLOWED_PATHS` | the data root mounted into the API and worker |
| `FORWARDED_ALLOW_IPS` | the reverse proxy's address(es) |
| Optional | `ARCHAI_PROTECT_READS=1` (private deployments), `ARCHAI_AUDIT_LOG=<path>` (enables the audit viewer), `ARCHAI_DOCS_ENABLED=1`, `WEB_CONCURRENCY` |

## 3. Docker Compose (single host)

```bash
cp .env.example .env    # set ARCHAI_ENV=production, POSTGRES_PASSWORD, ARCHAI_API_KEY_SHA256,
                        # ARCHAI_CORS_ORIGINS, ARCHAI_PUBLIC_API_URL (baked into the Studio build)
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml up -d --build --wait
```

Migrations (`migrate`) and the worker start automatically. Put a TLS-terminating reverse proxy (Caddy, nginx, a cloud
load balancer) in front of ports 3000 and 8000 and set `FORWARDED_ALLOW_IPS` to its address. The ports bind to
`127.0.0.1` unless `ARCHAI_BIND_ADDRESS` says otherwise, which suits a proxy on the same host. Postgres and Redis are not published.
Volumes: `archai-postgres`, `archai-redis` (append-only job queue), `archai-artifacts`
(checkpoints, audit log). Back up `archai-postgres` and `archai-artifacts`.

## 4. Verify after every deploy

```bash
curl -fsS https://<api>/health
curl -fsS https://<api>/readiness            # "status": "ready", rate_limit_backend "redis"
curl -s -o /dev/null -w '%{http_code}\n' -X POST https://<api>/v1/architectures -H 'content-type: application/json' -d '{}'   # 401
curl -fsSI https://<api>/health | grep -i strict-transport-security
curl -fsSI https://<studio>/ | grep -i content-security-policy
```

Then in the Studio: paste the key in the sidebar, queue a small candidate training job, watch its
live progress, cancel it, and confirm both requests appear in System Administration → Audit log.

## 5. Operations

- **Rotate the key**: generate a new key, update `ARCHAI_API_KEY_SHA256`, restart the API; the old key gets 401 immediately.
- **Worker recovery**: running jobs whose worker heartbeat lapses for 60 s are requeued automatically.
- **Logs**: `archai.*` loggers (including `archai.audit`) write to stderr at `ARCHAI_LOG_LEVEL` (default `INFO`). Every response carries `x-request-id`, which is also in the audit event.
- **Upgrades**: Dependabot opens weekly dependency PRs; CI must be green (tests, audits, image smoke test) before merging.
