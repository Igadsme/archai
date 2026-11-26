# Changelog

## Unreleased (feat/complete-archai, PR #1)

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
- Live browser E2E (`apps/web/e2e/studio.e2e.mjs`) against the local API + worker + NATS-Bench: 31/31 at 1280×900 and 390×844 (not in CI).
- Worker job results are read from `job.payload.result` (where `WorkerRunner` stores them).
- Random and Bayesian seed-0 runs repeat exactly at a later revision (`reproducibility_seed0.json`).

## 0.1.0 (master @ 30dc46a)

- Research foundation: schema/validation, compiler, search policies, predictor, generator, benchmark adapter, training engine, API, workers, migrations 0001–0006, Studio shell.
