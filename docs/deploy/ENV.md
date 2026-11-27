# Environment variables

Local development, CI, and the free hosted stack share these names. Never commit
secret values. The live box API key lives in `/workspace/archai-data/live/api-key`
and must not be pasted into a file in this repository.

Production (Render + Vercel + Neon + Upstash) **requires** a key and a restricted
CORS origin. Local development stays open if no key is configured, unless you set
`ARCHAI_REQUIRE_API_KEY=1`.

## API / worker (Render free web service)

| Name | Required in production | Notes |
| --- | --- | --- |
| `DATABASE_URL` | yes | Neon PostgreSQL URI (use the pooled / `-pooler` host). Alembic runs on deploy via `preDeployCommand`. |
| `ARCHAI_REDIS_URL` | yes | Upstash Redis URI (`rediss://`). Also used as the rate-limit backend. |
| `ARCHAI_REQUIRE_REDIS` | yes (`1`) | Readiness fails if Redis is down. |
| `ARCHAI_ENV` | yes (`production`) | Turns on every safeguard: refuses to boot without a key, with `*`/http/localhost CORS origins, without `DATABASE_URL`/`ARCHAI_REDIS_URL`, or with `ARCHAI_DB_AUTO_CREATE=1`; disables `/docs`; sends HSTS. Default `development`. |
| `ARCHAI_PROTECT_READS` | optional (`1`) | Require the key on every read except `/health` and `/readiness`. The Studio sends the sidebar key on reads too. |
| `ARCHAI_DOCS_ENABLED` | optional | `1` re-enables `/docs`, `/redoc`, `/openapi.json` in production. |
| `ARCHAI_LOG_LEVEL` | optional | Level for `archai.*` loggers on stderr (default `INFO`); audit events go here even without a file. |
| `FORWARDED_ALLOW_IPS` | yes behind a proxy | Proxy addresses uvicorn trusts for `X-Forwarded-For` (`--proxy-headers`), so rate limits see client IPs. Render uses `'*'` in `render.yaml` because its proxy IPs are not fixed. |
| `WEB_CONCURRENCY` | optional | uvicorn worker processes in the Docker image (default 1; Compose 2). |
| `ARCHAI_REQUIRE_API_KEY` | yes (`1`) | The API **refuses to boot** unless `ARCHAI_API_KEY` or `ARCHAI_API_KEY_SHA256` is set. |
| `ARCHAI_API_KEY_SHA256` | yes (preferred) | SHA-256 hex of the write key. Prefer this over storing the plaintext key on Render. Imani generates a random key, hashes it locally, and pastes only the hash. Studio and API clients use the plaintext key. |
| `ARCHAI_API_KEY` | alternative to the hash | Plaintext key. Avoid on Render if the hash is set. |
| `ARCHAI_CORS_ORIGINS` | yes | Comma-separated origins, e.g. `https://archai-studio.vercel.app`. Do not leave this as `*` and do not keep the localhost defaults in production. |
| `ARCHAI_EMBED_WORKER` | yes (`1`) | Starts `WorkerRunner` on a daemon thread inside the API process. Required because Render has no free background workers or cron jobs. |
| `ARCHAI_DB_AUTO_CREATE` | `0` in production | Schema comes from `alembic upgrade head` on deploy. |
| `ARCHAI_NATS_BENCH_PATH` | yes | Hosted demo uses the committed fixture file `datasets/fixtures/natsbench-tss-cifar10-256/cells.jsonl`. Do **not** point this at the official 1.15 GB archive on Render (ephemeral disk, 512 MB RAM). |
| `ARCHAI_NATS_BENCH_SHA256` | yes | Fixture cells file SHA-256: `4a4b956ad6ae53b9d0b17fcf04b4935d17db030661afe23bbdb111c27ac5a148`. |
| `ARCHAI_NATS_BENCH_INDICES` | yes | `fixture` means every index in the fixture (0–255). A comma-separated list is also accepted. |
| `ARCHAI_ALLOWED_PATHS` | yes | Colon-separated absolute roots. Render: `/tmp:/opt/render/project/src`. |
| `ARCHAI_GENERATOR_CHECKPOINT` | optional | Leave unset on the 512 MB free instance unless a tiny non-torch path exists. The hosted API is installed **without** the `ml` extra; generate/training that needs PyTorch will error. |
| `ARCHAI_ARTIFACT_STORE` | optional | Defaults under `/tmp` (ephemeral on Render; job results still go through Redis/Postgres). |
| `ARCHAI_AUDIT_LOG` | optional | JSONL path; enables `GET /v1/audit` and the Studio audit viewer. `render.yaml` uses `/tmp/archai-audit.jsonl` (ephemeral). Audit events are always logged to stderr too. |
| `ARCHAI_BENCHMARK_CACHE` | optional | Defaults to `/tmp/archai-benchmark-cache.sqlite`. |
| `PORT` | set by Render | `render.yaml` binds `0.0.0.0:$PORT`. |
| `ARCHAI_BIND_HOST` | optional | Unused when uvicorn is started with `--host` in `render.yaml`. |

## Studio (Vercel Hobby)

| Name | Required | Notes |
| --- | --- | --- |
| `NEXT_PUBLIC_ARCHAI_API_URL` | yes, **at build time** (Docker: `--build-arg`; Compose: `ARCHAI_PUBLIC_API_URL`) | Public Render URL, no trailing slash, e.g. `https://archai-api.onrender.com`. Next inlines this into the browser bundle. |
| (browser) API key | user-entered | The Studio already has an API-key field. Imani (or a collaborator) pastes the plaintext write key in the UI. Do not bake the key into the Vercel project. |

## Hugging Face publish (later, Imani's laptop or a trusted shell)

| Name | Required | Notes |
| --- | --- | --- |
| `HF_TOKEN` | only for `scripts/publish_hf.py --execute` | Fine-grained write token. `--dry-run` (the default) never reads it to call the API and never prints it. |

## Kaggle

No production secrets are required. If Imani clones a **private** fork, she would attach a GitHub token in the notebook; this repo is public, so a token is not needed to `git clone` / `pip install`.
