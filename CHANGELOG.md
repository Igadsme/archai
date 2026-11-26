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

## 0.1.0 (master @ 30dc46a)

- Research foundation: schema/validation, compiler, search policies, predictor, generator, benchmark adapter, training engine, API, workers, migrations 0001–0006, Studio shell.
