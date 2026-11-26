# Test report

Executed results only. Nothing here is predicted or estimated. Every row was run on the box
(Debian, Python 3.13.5, torch 2.15.0+cpu, Node 24.22.1) unless it says GitHub Actions.

| Date (ET) | Commit | Check | Result |
| --- | --- | --- | --- |
| 2026-11-25 | 30dc46a | `pytest -q` (extras dev, platform, ml) | 113 passed, 0 skipped |
| 2026-11-25 | 30dc46a | `alembic upgrade head` (SQLite) | `0006_experiment_started_at (head)` |
| 2026-11-25 | 30dc46a | `python scripts/smoke_search.py` | `controller_smoke_passed`, 3 evaluations |
| 2026-11-25 | 30dc46a | `npm run typecheck` / `npm run build` (Next 14.2.5) | pass / pass |
| 2026-11-25 | e322b6b (`main`) | `pytest -q` | 5 collection errors (ImportError: `acquire_file`/`sha256_file`) |
| 2026-11-25 | bdd4bc8 | `npm ci`, `tsc --noEmit`, `next build` (Next 16.4.6) | pass; `npm audit --omit=dev`: 0 vulnerabilities |
| 2026-11-25 | e5152db | `pytest -q` | 120 passed, 0 skipped |
| 2026-11-25 | e5152db | GitHub Actions CI (python, web) | success |
| 2026-11-25 | a9e5423 | `ruff check .` (pinned rule set) | All checks passed |
| 2026-11-25 | 92938c3 | `pytest -q` | 125 passed, 0 skipped |
| 2026-11-25 | 63ace4e | `sha256_tree` of extracted official `NATS-tss-v1_0-3ffb9-simple` (15,626 files) | `183b6ad8…4ba3`, 1.8 s; tar SHA-256 `580fd8f3…8bb6` |
| 2026-11-25 | 6423b08 | `run_experiment_matrix.py` smoke_matrix on the real archive (4 arms × 2 seeds × 8 queries) | exit 0, 3 s |
| 2026-11-25 | 1dae919 | `nasbench201_cifar10_cpu_small` (5 arms × 5 seeds × 50 queries, 15,625 cells) | exit 0, 26 s; results in `research/results/nasbench201_cifar10_cpu_small/` |
| 2026-11-25 | 56f8cab+ | Live stack: Postgres 17.12 + Redis (local), `alembic upgrade head` | `0006_experiment_started_at (head)` on PostgreSQL |
| 2026-11-25 | 56f8cab+ | `scripts/live_service_check.py` (Bayesian, budget 10, indices 0:256) | exit 0: search job succeeded via the Redis worker; benchmark experiment persisted in Postgres; synthetic candidate training job succeeded; `/readiness` shows `ready`, `rate_limit_backend=redis`; 10/10 write requests audit-logged |
| 2026-11-25 | 56f8cab+ | `pytest tests/test_live_services.py` against local Redis/Postgres | 3 passed |
| 2026-11-25 | 56f8cab+ | `pytest -q` (no live env) | 135 passed, 3 skipped (the live-service tests) |
| 2026-11-25 | 5b95d00 | Studio `vitest run` (forms, leaderboard) | 12 passed |
| 2026-11-25 | 5b95d00 | `npm run typecheck` / `npm run build` (prebuild vitest; Next 16.4.6) | pass / pass, 10 page routes prerendered; `npm audit`: 0 vulnerabilities (vitest 5.1.2) |
| 2026-11-25 | 5b95d00 | `next start` + `curl` of all 10 routes | HTTP 200 for each |
| 2026-11-25 | 5b95d00 | `pytest -q` (no live env) incl. `tests/test_studio_contract.py` | 137 passed, 3 skipped; `ruff check .`: all checks passed |
| 2026-11-25 | ab95052 | GitHub Actions CI (python, web; push and pull_request runs) | success |
