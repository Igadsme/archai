# Changelog

## Unreleased (production readiness, stacked on PR #1)

- `ARCHAI_ENV=production` boot validation (`archai_api/settings.py`): key required, explicit https CORS origins only, durable Postgres/Redis required, no `ARCHAI_DB_AUTO_CREATE`, `/docs` off unless `ARCHAI_DOCS_ENABLED=1`.
- Auth on `POST /v1/architectures/generate`; optional `ARCHAI_PROTECT_READS=1`; 400 on malformed `Content-Length`.
- Security headers on every API response (HSTS in production), `x-request-id` on every response and audit event, CORS exposes download headers.
- `GET /v1/audit` and a Studio audit-log viewer (System Administration).
- Live job progress (`payload.progress`) for candidate training (per epoch) and benchmark search (per evaluation), with cooperative cancellation; Studio progress bars on Training and Search pages. The Studio sends the API key on reads.
- `archai.*` logs (including audit events) are emitted on stderr by default (`ARCHAI_LOG_LEVEL`).
- Containers: CPU-only torch API image with a non-root data dir and health check; Studio image on Node 22 with Next standalone output, build-time API URL, CSP and security headers; Compose with `ARCHAI_ENV`, proxy headers, Redis AOF persistence, restart policies; `.env.example`.
- Render runs with `ARCHAI_ENV=production` and proxy headers.
- CI: least-privilege permissions, concurrency cancel, `security` job (`pip-audit`, `npm audit`, ruff flake8-bandit rules), `docker` job (build + smoke-test both images); Dependabot. pytest bumped to 9.0.3+ (PYSEC-2026-1845).
- Dataset acquisition accepts only `https`/`http`/`file` URLs.
- Docs: `SECURITY.md` (reporting, threat model, controls), `docs/deploy/PRODUCTION.md`, updated `ENV.md` and `API.md`.

## Unreleased (feat/complete-archai, PR #1)

- Free-tier path chosen (2026-11-26, 12:46 AM America/New_York): Kaggle free GPU, Hugging Face free private hosting, Vercel Hobby + Render free web + Neon Free + Upstash Redis Free. Official limits and card/not-actually-free flags are in `docs/deploy/FREE_TIER_PLAN.md`. Surprises: Render has **no** free background workers or cron jobs (the worker is embedded in the API via `ARCHAI_EMBED_WORKER=1`); adding a payment method on Upstash converts every free database to paid; Render bills bandwidth/build overages only if a card is on file (otherwise it suspends); Render free Postgres expires in 30 days and is not used.
- Kaggle training notebook and script (`notebooks/archai_v1_kaggle_train.ipynb`, `scripts/kaggle_train_archai_v1.py`) with a planned ~9 h GPU recipe, 15-minute checkpoints, resume, official-archive checksums, and real CIFAR-10 eval of a few generated cells (this repo's engine, not the official NATS-Bench protocol). A CPU `--smoke` path was executed on the box (tiny fixture scale, synthetic candidate training, ~1.6 s). Runbook: `docs/deploy/KAGGLE_RUNBOOK.md`.
- Draft `MODEL_CARD.md` (measured smoke fields only; GPU fields marked **PLACEHOLDER (not yet measured)**) and `scripts/publish_hf.py` (private by default, `--dry-run` default, token from `HF_TOKEN`). Dry-run was tested and did not call the Hub API.
- Hosting configs without creating accounts: `render.yaml` (single free web service, `alembic upgrade head` on deploy, fixture dataset, no `ml` extra), `apps/web/vercel.json`, `docs/deploy/ENV.md`, `docs/deploy/HOSTING_RUNBOOK.md`. Production boot requires `ARCHAI_REQUIRE_API_KEY=1`. The hosted demo uses the 256-cell fixture, not the official archive.
- The live box API process now enforces a write key (401 without a key or with a wrong key; 200 with the configured key). The key is not in the git tree and was not written to `env.sh`.
- Binned budget-ceiling generator conditioning (`ceiling_bins`, 8-d condition + tight-budget oversampling) at CPU smoke scale: raw param-budget satisfaction 0.983 vs uniform random 0.908, mean val acc 89.49 vs 83.41 (`6ca450d`, `f7b7e48`; report `research/results/generator_budget_bins_smoke/`). A 40-epoch rejection-penalty ablation reached satisfaction 1.0 but dropped quality below random and was not selected.
- Studio browser E2E runs in GitHub Actions on a committed 256-cell NATS-Bench fixture (fixture-only) with Postgres and Redis service containers (`0339a9c`). Green at `0dff0de`: **33/33** (`studio-e2e`), python 159 passed / 35 skipped, python-torch 191 passed / 3 skipped, web succeeded.
- Live restart/recovery on the box stack (API restart mid-search succeeded; worker kill + 65 s lease wait + new worker recovered a running search; Postgres stop/start mid-search, project row persisted, readiness returned to ready). Security: auth/rate-limit unit tests 4 passed; live-service tests 3 passed; `npm audit` 0 vulnerabilities; `pip-audit` reported 14 known issues in pip 25.1.1 and pytest 8.4.2 (dev tooling); secret scan did not find the live API key or private-key/token patterns in the git tree. The live API process on the box does not enforce a write key (open local development).
- Research projects: Alembic 0007, API CRUD, Studio create/select, optional `project_id` on search/generate/training/experiment (`f6ccb2d`).
- Architecture constraints (param/FLOP/latency budgets, allowed ops) on projects, generate, and search; unevaluable constraints are rejected rather than ignored (`a61f4e7`).
- Measured CPU-smoke generator retraining with sampled budget ceilings (`research/results/generator_budget_ceiling_smoke/`); raw satisfaction still worse than random; hard rejection keeps the quality edge.
- Live browser E2E now creates a research project (step 1) and checks generator constraint fields: **32/32** at `71756c3`.
- 429 responses from the request-limit middleware include CORS headers; GET polls use a separate 600/min default (`8a7cb36`, `71756c3`).
- CI workflow applied at `a69f60a` once the token had Workflows read/write: ruff, Node 22, `npm ci`, CPU-only `python-torch` job, Alembic `current` vs `heads` (no hardcoded revision). Browser E2E was added later as `studio-e2e (fixture-only)` and is green at `0dff0de`.
- Completion audit and plan (`docs/COMPLETION_PLAN.md`) and the required docs set (ARCHITECTURE, BLOCKERS, CHANGELOG, TEST_REPORT).
- Studio: committed lockfile; Next 16.4.6 / React 19 (`npm audit`: 0 vulnerabilities); the web image uses `npm ci`.
- Matched-budget experiment matrix runner (`scripts/run_experiment_matrix.py`, `research/experiments/`).
- Reusable `run_search()` in `scripts/run_benchmark_search.py`.
- JSONL audit log for state-changing API requests.
- Rate limits shared through Redis, with an in-process fallback; `/readiness` reports the backend.
- Ruff rule set pinned and lint findings cleaned up, with no behavior changes.
- README quick start fixed.
- Bayesian optimization baseline (GP-UCB over index encodings), repeated-seed baselines and named ablations in the experiment matrix.
- NATS-Bench TSS adapter fixed to the official CIFAR-10 split protocol (select on `cifar10-valid`, report `cifar10` test); directory digests for extracted archives.
- Measured CPU-small benchmark-lookup results in `research/results/nasbench201_cifar10_cpu_small/`.
- Local live-service runbook (`infrastructure/local/`), `scripts/live_service_check.py`, and opt-in live tests.
- Studio: ten pages (overview, generator, search lab, training jobs, experiments, architecture explorer, leaderboard, models, datasets, infrastructure) behind a shared navigation shell, with search and training launch forms, API-key entry, and a validation-only leaderboard.
- Studio tests: vitest unit tests (run as `prebuild`, so `npm run build` runs them) and a shared request fixture that pytest posts to the API.
- Final report template renamed to the spec title and sections (`docs/FINAL_COMPLETION_REPORT_TEMPLATE.md`). First draft: `research/reports/2026-11-25-final-report-draft.md`.
- Search-policy registry shared by scripts, worker and API (random, regularized evolution, REINFORCE, GP-UCB, predictor-guided, generator-guided, multi-objective).
- Measured full NATS-Bench TSS suite: 7 policies + 4 ablations, 10 seeds, budget 100 (`research/results/nasbench201_cifar10_full_suite/`).
- ArchAI-V1 predictor and generator trained at CPU smoke scale; checkpoints live outside git with SHA-256 verification.
- Studio realigned to the ten spec pages (Research Dashboard, Architecture Generator, Architecture Graph Explorer, Autonomous Search Laboratory, Pareto Optimization Explorer, Training Laboratory, Model Comparison, Research Results, Model Registry, System Administration), with Pareto explorer, model comparison, TorchScript export, checkpoint inspection, explicit Unavailable notes, and desktop/mobile layouts.
- Live browser E2E (`apps/web/e2e/studio.e2e.mjs`) against the local API + worker + NATS-Bench (not in CI).
- Worker job results are read from `job.payload.result` (where `WorkerRunner` stores them).
- Random and Bayesian seed-0 runs repeat exactly at a later revision (`reproducibility_seed0.json`).

## 0.1.0 (master @ 30dc46a)

- Research foundation: schema/validation, compiler, search policies, predictor, generator, benchmark adapter, training engine, API, workers, migrations 0001–0006, Studio shell.
