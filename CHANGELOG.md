# Changelog

## Unreleased (feat/complete-archai, PR #1)

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
