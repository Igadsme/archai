# ArchAI completion plan

Written 2026-11-25 (America/New_York) on `feat/complete-archai`, base `master` @ 30dc46a.

**Spec source.** The original spec message (relayed via Monday) was not available to this pass, so this
audit uses the repository's own spec: `ROADMAP.md` milestones M0–M12, the README research workflow,
`docs/EXPERIMENT_PROTOCOL.md`, `docs/API.md` and `SECURITY.md`. If the relayed spec adds items, append them
to the table below.

Status key: **done** = implemented and exercised by an executed test or command in this pass;
**partial** = code exists but a required real-data/live-service step is unexecuted; **missing** = no code.

## Executed verification (2026-11-25, box, Python 3.13.5, torch 2.15.0+cpu)

| Check | Command | Result |
| --- | --- | --- |
| Python tests (base 30dc46a) | `pytest -q` with `.[dev,platform]` + torch/torchvision/numpy/scikit-learn/safetensors (CPU) | **113 passed, 0 skipped** |
| Python tests (this branch, after matrix runner) | same | **118 passed, 0 skipped** |
| API boot | `uvicorn archai_api.main:app` then `GET /health`, `GET /readiness` | `ok`, `ready` (local mode, no DB/Redis) |
| Byte-compile | `python -m compileall -q packages apps scripts` | ok |
| Fresh Alembic schema | `alembic upgrade head` on SQLite, `alembic current` | `0006_experiment_started_at (head)` |
| Controller smoke | `python scripts/smoke_search.py` | `{'evaluations': 3, 'unique': 3, 'status': 'controller_smoke_passed'}` (deterministic, no benchmark data) |
| Frontend typecheck | `npm run typecheck` (apps/web) | pass |
| Frontend build | `npm run build` (Next 14.2.5 at base; Next 16.4.6 after upgrade) | pass both times; clears PROGRESS blocker 4 |
| Frontend audit | `npm audit --omit=dev` | 14.2.5/14.2.35: 1 critical + 1 high; 16.4.6: 0 |
| Lint (informational, not a CI gate) | `ruff check .` | 130 findings (56 import-order, 16 UP017, 14 UP037, 10 unused-import, …) |
| Docker Compose config | — | not run: no Docker on the box |
| GitHub Actions `CI` on master/feat @ 30dc46a | run #3 / #2 | success |
| GitHub Actions `CI` on main @ e322b6b | run #1 | failure: 5 collection `ImportError`s (see below) |

## Spec audit

| # | Spec item (source) | Status | Evidence |
| --- | --- | --- | --- |
| M0 | Repo layout, typed schemas, dependency extras, CI | done | `pyproject.toml` extras `ml/benchmark/platform/dev`; `.github/workflows/ci.yml` green on 30dc46a |
| M1a | Checksum-gated dataset acquisition | done | `archai_benchmark/integrity.py`, `scripts/acquire_dataset.py`, `tests/test_benchmark.py` |
| M1b | NAS-Bench-201 parser + compiler semantics | done | `archai_benchmark/nasbench201.py`, `tests/test_benchmark.py`, `tests/test_core.py` |
| M1c | Real NATS-Bench archive query | partial | `archai_benchmark/adapter.py` (`NATSBenchAdapter`); no archive/checksum available, `datasets/manifests/natsbench201.json` has no verified digest to run against |
| M2 | Graph validation, hashing, restricted compiler | done | `archai_core/validation.py`, `archai_compiler/pytorch_compiler.py`; forward/backward test executed with torch |
| M3 | Random/evolution search, Pareto, budgets | done | `archai_search/policies.py`, `controller.py`; `tests/test_search_controller.py`, `test_evolution.py` |
| M4 | Predictor (uncertainty, checkpoints, baselines, real-data CLI) | done (code) / partial (real data) | `archai_predictor/*`, `scripts/train_predictor.py`; CLI needs real archive |
| M5 | Constrained conditional generator + corpus CLI | done | `archai_generator/*`, `scripts/train_generator.py`, `tests/test_train_generator_cli.py` |
| M6a | Trained generator + predictor checkpoints with provenance | missing | no checkpoint in repo or artifact store; needs real NATS-Bench labels (predictor) and a real corpus (generator) |
| M6b | Closed-loop controller (persist/cancel/resume/exhaustion/acquisition) | partial | `archai_search/learned.py`, `acquisition.py`; trained closed-loop benchmark run pending M6a |
| M7 | Random/evolution/Bayesian/learned policies + matched real-data comparison | partial | policies done; **gap:** `scripts/run_benchmark_search.py` report keys (`selected_validation_accuracy`, `held_out_test_accuracy`) do not match `build_report.py` run-record keys (`best_validation_accuracy`, `final_test_accuracy`); no multi-seed matrix runner |
| M8 | Training engine, CIFAR adapters, Redis jobs, workers | partial | `archai_training/*`, `archai_api/worker.py`, `archai_shared/jobs.py`; no measured larger run, CIFAR download opt-in only |
| M9 | DB schema, Alembic, registries, job/model APIs, containers | partial | `apps/api/archai_api/db.py`, migrations 0001–0006 (upgrade executed); no live Postgres/Redis run; auth is API-key only (users table unused by API) |
| M10 | ArchAI Studio dashboard | partial | `apps/web/app/page.tsx` (69 lines) reads health + 6 registries and inspects graphs; build now verified; no lockfile committed, Next 14.2.5 flagged by npm as vulnerable; read-only (no search/job launch UI) |
| M11 | Repeated-seed report builder, leakage checks, ablations | partial | `archai_benchmark/reporting.py`, `scripts/build_report.py`; README step 3 references `research/experiments/` which does **not exist**; no real repeated-seed results or ablations |
| M12 | Authorized Hugging Face publication | missing (blocked) | `apps/huggingface-space/app.py` status view only; publishing needs Imani's HF authorization |
| R1 | README quick start runs the API | partial | `python -m archai.apps.api.main` is not an importable module; correct entry is `uvicorn archai_api.main:app` |
| R2 | Experiment protocol fields on every result | done (records) | `archai_shared/records.py`, worker provenance tests |
| S1 | Security: allowlisted compiler ops, safe checkpoints, auth, quotas, audit log | partial | allowlist + safetensors + API key + size/rate limits done; no audit log, rate limiter is process-local |

## Progress on this branch

- M10: done for build reproducibility (lockfile, Next 16.4.6, `npm ci` image). The launch UI is still pending.
- M7/M11 key mismatch: fixed by `scripts/run_experiment_matrix.py` and `research/experiments/*.json` (tested with a synthetic adapter only). Real runs still need the archive.
- R1: fixed (README now uses `uvicorn archai_api.main:app`, checked by booting it).

## Priority order for this branch (no real data, no paid compute)

1. **This doc + executed results + CI proposal** (`docs/ci/ci.yml`).
2. **Studio reproducibility/security:** commit `package-lock.json`, bump Next to patched 14.2.x, re-verify typecheck/build.
3. **M7/M11 pipeline gap:** `research/experiments/*.json` matched-budget matrices and `scripts/run_experiment_matrix.py`, which runs seeds × algorithms through `run_benchmark_search` and emits run records `build_report.py` accepts. Tested with a fake evaluator; real numbers only after a verified archive.
4. **README quick start fix.**
5. Next (later passes): audit log for write endpoints; Studio launch-search form; ruff cleanup; Redis-backed rate limiting.

Blocked on Imani: NATS-Bench archive + checksum (M1c/M4/M6/M7 real runs); live Postgres/Redis host (M9);
Hugging Face authorization (M12); applying `docs/ci/ci.yml` changes if the token lacks `workflow` scope.

## Imani's `main` commit e322b6b

`main` = `master` (30dc46a) + one commit "Apply current ArchAI changes" (parent 30dc46a — not unrelated history).
It truncates `packages/benchmark-engine/archai_benchmark/integrity.py` (39 lines → empty) and `tests/test_benchmark.py`
(85 lines → empty). Every importer of `sha256_file`/`acquire_file` breaks (package `__init__`, worker, API model
integrity, three scripts); GitHub CI run #1 on main failed with 5 collection errors, reproduced locally.
Preserved unchanged on `review/main-benchmark-integrity`. It cherry-picks trivially onto master but would delete
the checksum gate, so no PR was opened; it looks like an accidental empty-file upload. Decision needed from Imani.
