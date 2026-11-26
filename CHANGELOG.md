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
- Final engineering report template (`docs/FINAL_REPORT_TEMPLATE.md`).

## 0.1.0 (master @ 30dc46a)

- Research foundation: schema/validation, compiler, search policies, predictor, generator, benchmark adapter, training engine, API, workers, migrations 0001–0006, Studio shell.
