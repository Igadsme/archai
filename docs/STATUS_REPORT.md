# ArchAI project status report

Status as of 27 November 2026. `main` is the default branch and holds all merged work; its CI (python, python-torch,
web, security, docker with a compose boot, studio-e2e) is green. ArchAI runs end to end on a single machine with one
command. It is not yet deployed anywhere public; "Path to production" below lists what that needs.

## 1. What has been done

### Merged pull requests

| PR | Into | What it delivered |
| --- | --- | --- |
| [#1](https://github.com/Igadsme/archai/pull/1) | master | Repository audit, Studio hardening, experiment matrix and reporting scripts. |
| [#2](https://github.com/Igadsme/archai/pull/2) | master | Production hardening of the API (production boot checks, rate limits, request-size limits, security headers, audit log), live job progress over Redis, Dockerfiles, CI security audits. |
| [#4](https://github.com/Igadsme/archai/pull/4) | master | Studio V3: the Figma Make "ArchAI Studio V3" export made the official frontend, every screen wired to the real API. |
| [#5](https://github.com/Igadsme/archai/pull/5) | main | Brought master (#1, #2, #4) into `main` without a force-push; `main` ended up with master's tree and stays the default branch. |
| [#19](https://github.com/Igadsme/archai/pull/19) | main | User accounts and managed API keys: multiple keys per user, stored as SHA-256 hashes, scoped `read` < `write` < `admin`, rotation and revocation; Studio "Users & API keys" panel. |
| [#20](https://github.com/Igadsme/archai/pull/20) | main | GPU and host telemetry (NVML, then `torch.cuda`, otherwise an explicit "No GPU" reason), measured inference latency, job retry; wired into the Training, System, Experiments and Explorer screens. |
| [#21](https://github.com/Igadsme/archai/pull/21) | main | Local model deployments with checksum-verified checkpoint weights and a predict endpoint; Studio Registry → Deployments tab. |
| [#22](https://github.com/Igadsme/archai/pull/22) | main | Generator training that produces a real checkpoint on CPU in seconds, conditioned on a FLOPs budget; fixed a teacher-forcing start-token bug; `docs/GENERATOR.md`. |
| [#23](https://github.com/Igadsme/archai/pull/23) | main | One-command local hosting: Docker Compose with Postgres, Redis, migrations, API, worker, generator initialisation and Studio; `.env` and key generation; `docs/deploy/LOCAL.md`. |

PR #3 does not exist in this repository. PRs #6–#18 are open Dependabot updates (section 4).

### Endpoints added after the Studio V3 merge

- Identity: `GET /v1/auth/whoami`; `GET`/`POST /v1/users`, `PATCH /v1/users/{id}`; `GET`/`POST /v1/api-keys`,
  `POST /v1/api-keys/{id}/rotate`, `POST /v1/api-keys/{id}/revoke`. The audit log now requires an admin key.
- Telemetry: `GET /v1/infrastructure/telemetry`.
- Latency: `POST`/`GET /v1/architectures/{id}/latency` (timed forward passes, p50/p90/p99, evidence type `measured_latency`).
- Job retry: `POST /v1/jobs/{id}/retry` for failed or cancelled jobs, linked through `retry_of` / `retried_as`.
- Deployments: `GET`/`POST /v1/deployments`, `GET`/`DELETE /v1/deployments/{id}`, `POST /v1/deployments/{id}/stop`,
  `/start` and `/predict`.
- Generation: `/v1/architectures/generate` derives the condition from `max_flops` for checkpoints that declare the
  encoding and reports `condition` and `condition_source`.
- Database migrations 0008 (identity), 0009 (latency measurements), 0010 (deployments).

Full reference: [`docs/API.md`](API.md).

### Studio V3 integration

Studio V3 (`apps/web`, described in [`docs/STUDIO_V3.md`](STUDIO_V3.md)) calls the real API on every screen and never
shows invented numbers. When the backend cannot answer, the screen shows an explicit "unavailable" state with the reason.
After #19–#23 the following moved from unavailable to real data:

- System: users and API keys (create, rotate, revoke), real host metrics, audit log for admin keys.
- Training: GPU telemetry, or "none detected" with the reasons reported by NVML and torch.
- Explorer: "Measure latency" runs a real measurement; the KPI shows the measured p50 or "NOT MEASURED".
- Experiments: a working Retry button on failed or cancelled jobs.
- Registry: Deployments tab with deploy, stop, start, delete and a test request; untrained weights are labelled as such.
- Generator: samples from the trained checkpoint and shows the checkpoint's own label and conditioning source.

## 2. What is working (verified)

- **Tests on `main`:** pytest 274 passed / 3 skipped; vitest 67 passed; TypeScript type check and ruff lint clean.
- **Browser end-to-end:** 75/75 checks across five viewports in CI, and 75/75 against the Docker stack booted from a
  clean clone.
- **CI:** builds both images, boots the full compose stack from a clean checkout and runs the 7-check smoke test;
  dependency audits (pip-audit, npm audit) and a static security lint run on every PR.
- **Local launch:** `scripts/local/archai.sh up` from a clean clone generates `.env` and an admin key, runs migrations,
  trains the generator checkpoint, starts API, worker and Studio, and passes `scripts/local/archai.sh smoke` (7/7).
- **Features verified end to end:** architecture registry and Explorer, search jobs on the durable Redis worker with live
  progress, cancel and retry, candidate training, measured latency, deployments with predict, generator sampling,
  users and scoped keys, audit log, telemetry.

Local launch on macOS (full guide: [`docs/deploy/LOCAL.md`](deploy/LOCAL.md)):

```bash
cd /Volumes/PX4DRIVE/archai && git checkout main && git pull origin main
scripts/local/archai.sh up
open http://localhost:3000
pbcopy < .archai/bootstrap-api-key   # paste into the Studio's API KEY field
```

Studio is at http://localhost:3000, the API at http://localhost:8000 and its docs at http://localhost:8000/docs. Other
subcommands: `smoke`, `status`, `logs`, `key`, `urls`, `down`, `reset`.

## 3. What is not working, still a fixture, or still unavailable

- **Benchmark data is a fixture.** Searches run against the bundled 256-cell NATS-Bench fixture, not the full archive,
  so results are for trying things out only, not research claims. The CI e2e job is labelled "fixture-only".
- **The generator optimises a FLOPs budget, not accuracy.** The local checkpoint is trained on random operator chains
  labelled with analytical FLOPs. Budget adherence at one third of the budget is 97% conditioned against 62%
  unconditioned, but it knows nothing about accuracy, and its label says so.
- **Accuracy-aware NB201 generator checkpoints cannot be served yet.** `scripts/train_generator_nb201.py` (Kaggle)
  produces checkpoints in the NB201 cell vocabulary; `/v1/architectures/generate` cannot decode them until a
  cell-to-graph decoder is written. This is a code gap, not a user decision.
- **Without a checkpoint, `/generate` returns 503**, and the Studio shows "trained generator unavailable".
- **CPU only.** Local Docker uses CPU PyTorch. Telemetry reports "No GPU" honestly.
- **Deployments run inside the API process** (in-memory cache of 8 loaded models, CPU). Fine for testing; not a serving tier.
- **Research policy editor** stays unavailable by design: evidence rules are enforced in code.
- **Predictor- and generator-guided search** need the `ml` extra (torch); without it the Studio marks them unavailable.
  The Docker images include it.
- **Explorer gradient and activation statistics** are unavailable for architectures without trained weights.
- **Rate limits are per client IP** (120 writes and 600 reads per minute by default), not per key or per user.
- **Accounts are API-key based.** There is no password or SSO login, email verification or self-service sign-up.

## 4. What needs your attention

1. **GPU.** Docker on a Mac cannot use the Apple GPU or CUDA, so local training is CPU-only. GPU training means running
   the Kaggle notebook on your free quota ([`docs/deploy/KAGGLE_RUNBOOK.md`](deploy/KAGGLE_RUNBOOK.md)) or paying for a
   GPU host.
2. **Full NATS-Bench archive** (about 1.15 GB) for real searches: download it and point the worker at it
   (KAGGLE_RUNBOOK section 1). Until then everything runs on the fixture.
3. **Hugging Face token**, only if you want to publish models with `scripts/publish_hf.py`.
4. **Thirteen open Dependabot PRs**, [#6](https://github.com/Igadsme/archai/pull/6)–[#18](https://github.com/Igadsme/archai/pull/18).
   Several are major upgrades that need a decision and testing, not a blind merge: TypeScript 7
   ([#11](https://github.com/Igadsme/archai/pull/11)), Node 26 ([#8](https://github.com/Igadsme/archai/pull/8),
   [#12](https://github.com/Igadsme/archai/pull/12)), Python 3.13 ([#6](https://github.com/Igadsme/archai/pull/6)),
   GitHub Actions v7 ([#7](https://github.com/Igadsme/archai/pull/7), [#9](https://github.com/Igadsme/archai/pull/9),
   [#10](https://github.com/Igadsme/archai/pull/10)). The Python library bumps (#13–#18) are lower risk.
5. **Apple Silicon is untested.** Everything was verified on x86_64 Linux. arm64 CPU PyTorch wheels exist, so it should
   work, but the first real run on your Mac is the check. Expect the first image build to take 5–15 minutes.

## 5. Path to production

Local hosting is a single-machine, localhost-only setup. Going public needs the items below. **[User decision]** marks
choices only you can make (cost, accounts, risk); **[Engineering]** marks work that can be done once those are made.
[`docs/deploy/PRODUCTION.md`](deploy/PRODUCTION.md) and [`docs/deploy/HOSTING_RUNBOOK.md`](deploy/HOSTING_RUNBOOK.md)
cover the parts that already exist.

1. **Hosting choice [User decision].** Either one VM running the existing compose file behind a reverse proxy (simplest,
   about 4 vCPU / 16 GB for CPU work), or the free-tier path (Render API, Vercel Studio, Neon Postgres, Upstash Redis,
   see `FREE_TIER_PLAN.md`), or a managed container platform. Free tiers sleep and have small memory limits that do not
   suit torch workers.
2. **Domain and TLS [User decision + Engineering].** Buy or choose a domain; terminate TLS with Caddy, nginx or a cloud
   load balancer; set `ARCHAI_CORS_ORIGINS`, `ARCHAI_PUBLIC_API_URL` and `FORWARDED_ALLOW_IPS`. The API already sends
   HSTS and the Studio a Content-Security-Policy.
3. **Secrets management [User decision + Engineering].** Store the database password, Redis URL, bootstrap key hash and
   any HF token in the host's secret store (platform secrets, Vault, 1Password, SOPS), not in a `.env` on disk. Set
   `ARCHAI_ENV=production` so the API refuses unsafe settings at boot. Plan regular key rotation (`POST /v1/api-keys/{id}/rotate`).
4. **Managed or backed-up data [User decision + Engineering].** Use managed Postgres with point-in-time recovery, or add
   scheduled `pg_dump` plus off-host copies of the `archai-artifacts` volume (checkpoints, audit log) and test a restore.
   No backup job exists in the repo yet. Move artifacts to object storage (S3, R2, GCS) if more than one host needs them.
5. **Monitoring and alerting [User decision + Engineering].** Pick a stack (Grafana Cloud, Datadog, Sentry, uptime
   checks). Today there are structured logs to stderr, `x-request-id` on every response, `/health`, `/readiness` and
   worker heartbeats, but no metrics endpoint, error tracking or alerts. Minimum: uptime checks on `/readiness`,
   alerts on 5xx rate, queue depth and stale workers, and log shipping.
6. **Scaling the worker [Engineering].** Run several worker replicas against the same Redis queue (stale jobs are already
   requeued after a 60-second heartbeat lapse), cap concurrency per worker, and move deployment serving out of the API
   process into its own service if prediction traffic matters.
7. **GPU [User decision].** Choose a paid GPU host or keep training on Kaggle. A GPU host needs the API/worker image
   built with `TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124` and the NVIDIA container runtime; telemetry
   will then report real GPU data.
8. **Real benchmark data and models [User decision + Engineering].** Provide the full NATS-Bench archive, train the
   accuracy-aware generator on a GPU, and write the NB201 cell-to-graph decoder so `/generate` can serve it.
9. **Security review [User decision + Engineering].** An independent review or penetration test before exposing it,
   focused on API-key handling, the file-path allowlist (`ARCHAI_ALLOWED_PATHS`), checkpoint loading (already
   `weights_only` with SHA-256 verification), and rate limits. Decide whether reads should be private
   (`ARCHAI_PROTECT_READS=1`). See [`SECURITY.md`](../SECURITY.md).
10. **Accounts and access [User decision].** Decide who the users are. For anything beyond a small trusted group, add
    real login (OAuth/SSO or passwords), per-key rate limits and quotas.
11. **Load testing [Engineering].** Run k6 or Locust against the API (search submission, predict, Studio polling) to size
    `WEB_CONCURRENCY`, worker count, Postgres connections and the rate limits.
12. **Dependency and release process [User decision + Engineering].** Resolve the 13 Dependabot PRs, add branch
    protection on `main` (required CI checks, reviews), tag releases, and push images to a registry so deploys use
    pinned versions instead of building on the host.
13. **Legal and operational basics [User decision].** Data retention for the audit log and experiments, privacy policy
    and terms if outside users sign up, licence and model-card text for any published models
    (`docs/MODEL_CARD_TEMPLATE.md`), cost budget and alerts on paid services.
