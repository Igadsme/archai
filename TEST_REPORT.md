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
