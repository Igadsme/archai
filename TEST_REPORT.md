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
| 2026-11-25 | 2fe79d1 | Full-space TSS table (`scripts/benchmark_table.py`) | 15,625 rows × 3 trials + cost, `/workspace/archai-data/table/cifar10.jsonl` |
| 2026-11-25 | 2fe79d1 | `run_experiment_matrix.py` full suite (7 policies + 4 ablations, 10 seeds, budget 100) | exit 0, 850 s; recorded in `research/results/nasbench201_cifar10_full_suite/` |
| 2026-11-25 | 2fe79d1 | Predictor smoke (1,000 cells, 30 epochs, CPU) | held-out n=100: MAE 0.0539, Spearman 0.753; ckpt sha `3392b86c…13d2` |
| 2026-11-25 | b6fb591 | Generator smoke (2,000 cells, 300 epochs, CPU) | loss 1.613→1.278; high-acc mean val. 89.18 vs random 83.24; ckpt sha `0ad684a2…784e` |
| 2026-11-25 | d308cc6 | `scripts/verify_checkpoints.py` | both smoke checkpoints reload and reproduce outputs |
| 2026-11-25 | 2fe79d1 / b6fb591 / d308cc6 | GitHub Actions | python failed (torch without ml extra); web passed |
| 2026-11-25 | 5670f3f | `pytest -q` (no live env) | 168 passed, 3 skipped; no-torch mimic: 140 passed, 31 skipped |
| 2026-11-25 | 5670f3f | GitHub Actions (python, web) | success |
| 2026-11-25 | 08d4476 | GitHub Actions (python, web) | success (https://github.com/Igadsme/archai/actions/runs/45748164004) |
| 2026-11-25 | 3e7e9a7 | `pytest -q` (no live env) | 168 passed, 3 skipped; no-torch 140 passed, 31 skipped; ruff clean |
| 2026-11-25 | 3e7e9a7 | GitHub Actions (python, web) | success (https://github.com/Igadsme/archai/actions/runs/45748468981) |
| 2026-11-25 | 6fffab5 | GitHub Actions (python, web; two runs) | success (https://github.com/Igadsme/archai/actions/runs/45748566766) |
| 2026-11-25 22:35 ET | c03bd67 (local) | Live stack restarted after box replacement | Postgres recovered to 0006; `/readiness` ready, redis rate limits; worker idle; all 7 search algorithms available |
| 2026-11-25 | c03bd67 (local) | `npm run typecheck` / `npx vitest run` / `pytest tests/test_studio_contract.py` | tsc clean; 21 then 22 vitest passed; contract tests passed |
| 2026-11-25 22:40 ET | 02a6b00 (local) | Browser E2E `apps/web/e2e/studio.e2e.mjs` at 1280×900 and 390×844 against the live stack | **31/31 passed**, 0 console errors. TorchScript export loaded standalone, output (2, 10) |
| 2026-11-25 | 02a6b00 (local) | `pytest -q` (no live env) | **174 passed, 3 skipped**; ruff clean |
| 2026-11-25 | 02a6b00 (local) | CI mimic without torch | **146 passed, 31 skipped** |
| 2026-11-25 | 02a6b00 (local) | `pytest tests/test_live_services.py` against local Redis/Postgres | **3 passed** |
| 2026-11-25 22:50 ET | 07d729c (local) | Repeat random + Bayesian seed 0 on the same archive | exact match to the recorded `2fe79d1` runs (`reproducibility_seed0.json`) |

| 2026-11-25 23:06 ET | a61f4e7 | `scripts/train_generator_nb201.py --condition-mode ceiling` (2000 cells, 300 epochs, seed 0, CPU smoke) | wall ~5.3 s; loss 1.613→1.405; checkpoint SHA-256 `524b81c8…c6b9ae` (outside git). Raw constraint satisfaction 0.762 vs random 0.915 vs untrained 0.850 vs earlier point-estimate 0.690. Mean val acc 89.73% vs random 82.72%. Hard reject: 1000 accepted / 1280 draws, yield 0.781, mean val 89.82% vs 82.73% random feasible. Evidence: `research/results/generator_budget_ceiling_smoke/` |
| 2026-11-25 | 71756c3 (local) | `pytest -q` (no live env) | **187 passed, 3 skipped**; ruff clean |
| 2026-11-25 | 71756c3 (local) | CI mimic without torch (`PYTHONPATH=/tmp/notorch`) | **157 passed, 33 skipped** |
| 2026-11-25 | 71756c3 (local) | `npx vitest run` / `tsc --noEmit` / `npm run build` | 26 vitest passed; tsc clean; Next 16.4.6 build, 10 routes |
| 2026-11-25 | 71756c3 (local) | `pytest tests/test_live_services.py` against local Redis/Postgres | **3 passed** |
| 2026-11-25 | live Postgres | `alembic upgrade head` | `0007_research_projects (head)` |
| 2026-11-25 23:14 ET | 71756c3 (local) | Browser E2E at 1280×900 and 390×844 against the live stack | **32/32 passed**, 0 console errors (project create/select and generator constraint fields included) |
| 2026-11-25 23:13 ET | 71756c3 | GitHub Actions | **python failed** (Alembic grep still requires `0006_experiment_started_at`; pytest and compileall on that job succeeded). **web succeeded**. https://github.com/Igadsme/archai/actions/runs/45753820023 |
| 2026-11-25 22:55 PM and 11:14 PM ET | local attempts `47eec5f`, `5bc54e9` (reset, not pushed) | `git push` of `.github/workflows/ci.yml` | rejected: `refusing to allow a Personal Access Token to create or update workflow `.github/workflows/ci.yml` without \`workflow\` scope` |

| 2026-11-25 11:26–11:27 PM ET | a69f60a | GitHub Actions CI (push) | **success**: python 156 passed, 35 skipped (no torch); Alembic `current` matches `heads` (`0007_research_projects (head)`); ruff clean; python-torch 188 passed, 3 skipped (CPU torch extra-index); web typecheck + build, 26 vitest. https://github.com/Igadsme/archai/actions/runs/45755199041 |
| 2026-11-25 11:26–11:27 PM ET | a69f60a | GitHub Actions CI (pull_request) | **success** (python, python-torch, web). https://github.com/Igadsme/archai/actions/runs/45755205996 |
| 2026-11-25 11:26–11:27 PM ET | 1be8d0e | GitHub Actions CI (push and PR; docs after a69f60a) | **success** (python, python-torch, web). https://github.com/Igadsme/archai/actions/runs/45755495474 (push), https://github.com/Igadsme/archai/actions/runs/45755500732 (PR) |
| 2026-11-25 11:59 PM ET | 6ca450d (rerun on a clean tree) | CPU-smoke generator `ceiling_bins` (2000 cells, 300 epochs, seed 0, ~10 s, penalty-epochs 0) | Raw param-budget satisfaction **0.983 vs uniform random 0.908** vs untrained 0.889; mean val acc 89.49 vs 83.41; hard-reject yield 0.977 (1000/1024), mean val 89.71 vs 82.73 random feasible (`benchmark_lookup`). Checkpoint SHA-256 `954cfab0…20cfe` (outside git). Report: `research/results/generator_budget_bins_smoke/` |
| 2026-11-25 11:58 PM ET | same scale / seed, ablation | `ceiling_bins` + 40 rejection-aware epochs | Satisfaction 1.0 but mean val acc 74.18 vs random 83.41 (not selected). Recorded in `ablation_penalty40.json` |
| 2026-11-26 12:16 AM ET | 0dff0de tree (local live stack) | Restart/recovery: API mid-search, worker mid-search + lease recovery (65 s wait), Postgres stop/start mid-search | API restart: search stayed running and **succeeded**. Worker restart: status stayed `running` during the lease wait, then **succeeded** after a new worker started. Postgres: `database_ready` returned true, project `recovery-persist-check` persisted, search seed 703 **succeeded**. The checker hung on `pg_ctl start -w` capturing stdout (postgres inherited the pipe); only the checker was stopped; API/worker/Postgres stayed up. |
| 2026-11-26 12:17 AM ET | 0dff0de tree | Auth / rate-limit unit tests | **4 passed** (`test_write_operations_honor_x_api_key`, `test_rate_limited_writes_are_audited`, `test_rate_limit_response_includes_cors_headers`, `test_api_compose_passes_hashed_auth_configuration`) |
| 2026-11-26 12:17 AM ET | 0dff0de tree | `pytest tests/test_live_services.py` (Redis db 15, Postgres :5433) | **3 passed** |
| 2026-11-26 12:17 AM ET | 0dff0de tree | Live write-auth probe on the box API process | POST /v1/projects returned **200** with no key and with a wrong key (`auth_enforced=false`). This process has no `ARCHAI_API_KEY` / `ARCHAI_API_KEY_SHA256` set (open local development). Unit tests cover enforcement when a key is configured. |
| 2026-11-26 12:17 AM ET | 0dff0de tree | `python -m pip_audit` | Exit 1: **14** known vulnerabilities in pip 25.1.1 and pytest 8.4.2 (dev tooling). `archai`, `torch 2.15.0+cpu`, and `torchvision 0.29.2+cpu` skipped (not on the default PyPI index). Log: `/workspace/archai-notes/pip-audit.txt` |
| 2026-11-26 12:17 AM ET | 0dff0de tree | `npm audit` in `apps/web` | **0** vulnerabilities (info/low/moderate/high/critical all 0), exit 0 |
| 2026-11-26 12:17 AM ET | 0dff0de tree | Secret scan (`git grep` of the live API key value, private-key/AWS/Slack patterns, `git ls-files` for `api-key`) | Live key **not** in the git tree; **0** pattern hits; `api-key` is not tracked |
| 2026-11-26 12:26 AM ET | 0dff0de | GitHub Actions CI (push) | **success**: python 159 passed / 35 skipped; python-torch 191 passed / 3 skipped; web succeeded; **studio-e2e (fixture-only) 33/33 passed**. https://github.com/Igadsme/archai/actions/runs/45761551116 |
| 2026-11-26 12:26 AM ET | 0dff0de | GitHub Actions CI (pull_request) | **success** (python, python-torch, web, studio-e2e). https://github.com/Igadsme/archai/actions/runs/45761556382 |
