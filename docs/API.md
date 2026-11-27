# API

Redis workers publish heartbeats used by `/v1/infrastructure/workers`, including worker ID, hostname, process ID, liveness timestamp, status, and active job ID. Heartbeats older than 30 seconds are treated as stale and omitted. Experiment creation requires a registered dataset version; supplied evidence checksums must match its registered digest.

`GET /health` and `GET /readiness` report service/configuration status. `GET /v1/infrastructure/workers` and `/v1/infrastructure/queue` expose operational state. `POST /v1/architectures/validate` accepts a strict Architecture JSON document and returns its canonical hash plus analytical metrics. `POST /v1/architectures`, `GET /v1/architectures`, `GET /v1/architectures/{architecture_id}`, and `GET /v1/architectures/compare` provide the local registry surface. `GET /v1/models`, `GET /v1/models/{model_id}`, and authenticated `POST /v1/models` expose and register checksum-backed checkpoint metadata; reads also report whether the artifact exists and still matches its registered digest. `POST /v1/architectures/generate` loads a configured generator checkpoint from `ARCHAI_GENERATOR_CHECKPOINT` and returns independently seeded, canonicalized candidates; it returns `503` when no checkpoint is configured. `POST /v1/searches` creates a budgeted search job and accepts optional benchmark indices; `GET /v1/searches` lists bounded search history; `GET /v1/searches/{search_id}` reports the authoritative job-store status and `POST /v1/searches/{search_id}/cancel` transitions queued/running jobs to cancelled. `POST /v1/training` creates validated candidate, generator, or predictor jobs; `GET /v1/jobs`, `GET /v1/jobs/{job_id}`, and `POST /v1/jobs/{job_id}/cancel` expose generic job lifecycle state. Candidate jobs require synthetic data, generator jobs require explicit corpus/checkpoint paths, and predictor jobs require an archive checksum plus indices. Starting a search returns `503` without Redis, and the durable worker requires `ARCHAI_NATS_BENCH_PATH` plus `ARCHAI_NATS_BENCH_SHA256` before it will query the benchmark. `POST /v1/experiments` accepts predicted evidence directly; benchmark and measured evidence additionally require a dataset checksum, while measured training also requires a model-checkpoint hash and records hardware/code revision. `GET /v1/experiments` lists bounded history, `GET /v1/experiments/{experiment_id}` retrieves a record, and `PATCH /v1/experiments/{experiment_id}` applies validated lifecycle transitions and persists updated metrics. If `ARCHAI_API_KEY` or `ARCHAI_API_KEY_SHA256` is configured, write operations require `x-api-key` or `Authorization: Bearer ...`; request-size limits inspect the actual body when `Content-Length` is absent. Set `ARCHAI_REQUIRE_API_KEY=1` so the process refuses to boot when neither is set (required on the hosted API). Set `ARCHAI_EMBED_WORKER=1` to run `WorkerRunner` in a background thread of the API process (used on Render Free, which has no free background workers or cron jobs).

`ARCHAI_MAX_REQUEST_BYTES` and `ARCHAI_RATE_LIMIT_PER_MINUTE` configure request guards. When `ARCHAI_RATE_LIMIT_REDIS_URL` (or `ARCHAI_REDIS_URL`) is set, per-client limits are shared across API replicas through Redis fixed one-minute windows (`INCR` + `EXPIRE`). If Redis errors, the API falls back to an in-process sliding window rather than failing open; `/readiness` reports `rate_limit_backend` and the last Redis error, and 429 responses carry `x-ratelimit-backend`.

Training, model-artifact, and generator-checkpoint paths are constrained by `ARCHAI_ALLOWED_PATHS`, a colon-separated list of absolute roots. Local mode defaults to `/tmp` plus Python's temporary directory; Compose sets `/var/lib/archai` so API and workers cannot read or write arbitrary host paths.

Readiness checks database connectivity when `DATABASE_URL` is set. Set `ARCHAI_REQUIRE_REDIS=1` to make Redis connectivity a readiness requirement as well.

Browser clients are allowed only the origins in `ARCHAI_CORS_ORIGINS` (comma-separated); local defaults are `http://localhost:3000` and `http://127.0.0.1:3000`.

Set `DATABASE_URL` to use the SQLAlchemy-backed architecture, search, experiment, model, and dataset registries. The API expects the Alembic schema to have been applied; set `ARCHAI_DB_AUTO_CREATE=1` only for local development or tests. Without `DATABASE_URL`, the API uses process-local registries and the JSON model manifest.

Every `POST`/`PUT`/`PATCH`/`DELETE` request, including ones rejected with 401/413/429, emits one JSON audit event (UTC timestamp, method, path, status, allowed/rejected outcome, client host, a 12-hex SHA-256 fingerprint of the presented credential, and duration) to the `archai.audit` logger. Set `ARCHAI_AUDIT_LOG` to also append it to a JSONL file; Compose writes to `/var/lib/archai/audit/api-writes.jsonl`. Credentials are never written in clear text.

## Production hardening

`ARCHAI_ENV=production` validates configuration at boot (see `docs/deploy/PRODUCTION.md`). `POST /v1/architectures/generate` requires the write key like every other expensive route. `ARCHAI_PROTECT_READS=1` requires the key on all reads except `/health` and `/readiness`. Every response carries `x-request-id` (a valid client-supplied value is echoed, otherwise a new one is generated) plus `nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: no-referrer`, `Cache-Control: no-store`, and a `default-src 'none'` CSP (HSTS in production). CORS exposes `content-disposition`, `x-archai-sha256`, `x-archai-output-shape`, and `x-request-id` so cross-origin downloads keep their file names. A malformed `Content-Length` returns 400.

`GET /v1/audit?limit=100&outcome=allowed|rejected` returns the newest audit events first (key required when configured). Without `ARCHAI_AUDIT_LOG` it returns `{"available": false}`; events still go to the `archai.audit` logger on stderr. Each event includes the `request_id`.

## Live job progress and cancellation

Workers write advisory progress to `payload.progress` of the job (visible through `GET /v1/jobs/{id}` and `GET /v1/searches/{id}`): candidate training reports `{"phase": "training", "epochs_completed", "epochs", "history": [...]}` per epoch, and benchmark search reports `{"phase": "searching", "evaluations", "budget", "best_validation_accuracy"}`. Writes are throttled to about one per second (first and last always written), and the final result is stored next to the last progress record. Cancelling a running job is cooperative: candidate training stops after the current epoch and search stops before its next query, so a cancelled job no longer keeps consuming CPU. Generator and predictor training report only on completion.

## Users and API keys

Auth is on when `ARCHAI_API_KEY` / `ARCHAI_API_KEY_SHA256` (the bootstrap admin key) is set or any managed key is active; otherwise the API is in open local mode. Scopes: `read` < `write` < `admin` (`admin` implies the others). Writes need `write`; key, user and audit endpoints need `admin`. A missing or invalid key gets `401`; a valid key without the scope gets `403`.

| Method and path | Scope | Purpose |
| --- | --- | --- |
| `GET /v1/auth/whoami` | none | Whether auth is on and who the presented key belongs to. `401` for an invalid key. |
| `GET /v1/users`, `POST /v1/users` | admin | List or create accounts (`email`, `display_name`, `role` = `admin` or `member`). |
| `PATCH /v1/users/{id}` | admin | Change `display_name` or `role`, or set `disabled`. Disabled users' keys stop working. |
| `GET /v1/api-keys[?user_id=]` | admin | Key metadata: prefix, scopes, last use, expiry, state. Never the secret or hash. |
| `POST /v1/api-keys` | admin | Issue a key (`user_id`, `name`, `scopes`, optional `expires_in_days`). The secret is in this response only. |
| `POST /v1/api-keys/{id}/rotate` | admin | New secret with the same owner, name and scopes; the old key is revoked at once. |
| `POST /v1/api-keys/{id}/revoke` | admin | Revoke immediately. |

Only `admin`-role users can hold `admin`-scoped keys. Without a bootstrap key, the first managed key must be admin-scoped and the last active admin key cannot be revoked (`409`).

## Telemetry, latency and job retry

| Method and path | Scope | Purpose |
| --- | --- | --- |
| `GET /v1/infrastructure/telemetry` | read | Host metrics for the API process plus every live worker's last heartbeat. GPUs come from NVML (`pynvml`) when it is installed, else `torch.cuda`; with no GPU, `gpu.available` is `false` and `gpu.reason` says why (`No GPU: …`). Nothing is estimated. |
| `POST /v1/architectures/{id}/latency` | write | Time forward passes of the registered architecture on the API host (`batch_size` 1–64, `warmup` 0–50, `iterations` 2–500, `device` `cpu` or `cuda`). Returns mean, p50, p90, p99, min, max, stdev and throughput with the device, hardware and torch version; `evidence_type` is `measured_latency`. Weights are seeded, not trained. Capped at `ARCHAI_LATENCY_MAX_SECONDS` (default 20); `503` without torch or when `cuda` is requested but unavailable. |
| `GET /v1/architectures/{id}/latency` | read | Stored measurements, newest first. |
| `POST /v1/jobs/{id}/retry` | write | Queue a new job with the same kind and inputs as a `failed` or `cancelled` one. The new job carries `retry_of`; the original gets `retried_as`. Other states return `409`. |
