# ArchAI completion plan, tracked against the acceptance list

Source of truth: `docs/SPEC_ACCEPTANCE.md` (Imani's spec, Studio §10 and acceptance §13/15/16).
The earlier audit-driven plan (passes 1–3) is kept in `docs/history/COMPLETION_PLAN_passes_1-3.md`.

**Status vocabulary (spec):** COMPLETE = implemented *and* verified by an executed check ·
IN PROGRESS · BLOCKED · NOT STARTED · FAILED. Interface-only work is never COMPLETE, and smoke tests
alone never count as success. Evidence points at tests, scripts, or `TEST_REPORT.md` rows. "CI"
means GitHub Actions. CI installs `.[dev,platform]` without torch, so torch-dependent tests run on
the box only (see BLOCKERS B5).

**Current verdict: PARTIALLY COMPLETE.** COMPLETE AND VERIFIED requires the entire acceptance suite;
E2E steps 1 and 3 (projects, architecture constraints) are not implemented, and several ML/deployment
checks are smoke-scale or single-run only.

"Browser E2E" below = `apps/web/e2e/studio.e2e.mjs` executed against the live local stack (API + Redis
worker + Postgres + NATS-Bench), 31/31 checks at 1280×900 and 390×844 (TEST_REPORT.md, 02a6b00). It is not in
CI because it needs the stack.

## 1. Studio pages (§10)

| # | Spec page | Route | Status | Verified by / gap |
| --- | --- | --- | --- | --- |
| 1 | Research Dashboard | `/` | COMPLETE | browser E2E (loads registry/job/model counts, measured-suite table, failed jobs) |
| 2 | Architecture Generator | `/generator` | IN PROGRESS | E2E: generate → save to registry works; constraint-conditioned generation is marked Unavailable, and the configured API checkpoint is a 2-example smoke checkpoint |
| 3 | Architecture Graph Explorer | `/explorer` | COMPLETE | E2E: register → SVG DAG → JSON + TorchScript export; export loaded and run without archai (TEST_REPORT) |
| 4 | Autonomous Search Laboratory | `/search` | COMPLETE | E2E: multi_objective search launched, run on the worker, 20-step history shown; all 7 policies selectable |
| 5 | Pareto Optimization Explorer | `/pareto` | COMPLETE | E2E: measured-suite fronts per policy/seed + live-session front and hypervolume (TS hypervolume = Python, vitest + pytest fixture) |
| 6 | Training Laboratory | `/training` | IN PROGRESS | E2E: synthetic candidate job → measured loss table; live per-epoch progress is marked Unavailable |
| 7 | Model Comparison | `/compare` | COMPLETE | E2E: 2 architectures compared (analytical metrics); policy table with CIs, regret, hypervolume, CI-overlap flag |
| 8 | Research Results | `/results` | COMPLETE | E2E: committed result sets with config, tables, README, smoke reports; experiment leaderboard |
| 9 | Model Registry | `/models` | COMPLETE | E2E: checkpoint inspection (tensors, parameters, metadata); tampered files refused (pytest) |
| 10 | System Administration | `/admin` | COMPLETE | E2E: readiness, queue, live worker, failed jobs, datasets; audit-log viewer and key management marked Unavailable |

| Required capability | Status | Evidence / gap |
| --- | --- | --- |
| Architecture generation | IN PROGRESS | works end to end, but only with a smoke checkpoint and without constraints |
| Architecture visualization | COMPLETE | `DagView` + `layoutDag` (vitest), E2E |
| Real search sessions | COMPLETE | E2E on the Redis worker against the verified archive |
| Experiment monitoring | COMPLETE | polled sessions/jobs with cancel; E2E |
| Training progress | IN PROGRESS | final loss curve per epoch after completion; no live progress channel |
| Search-history inspection | COMPLETE | per-step history table (worker `history`), E2E |
| Checkpoint inspection | COMPLETE | `GET /v1/models/{id}/inspect`, E2E |
| Benchmark comparisons | COMPLETE | Model Comparison + Pareto pages over `research/results/nasbench201_cifar10_full_suite` |
| Architecture export | COMPLETE | `GET /v1/architectures/{id}/export?format=json|pytorch`, E2E download + standalone load |
| Error reporting | COMPLETE | API detail surfaced per form/load (`Errors`, `Loaded`); failed jobs on dashboard/admin |
| Unavailable features marked, no decorative controls | COMPLETE | `Unavailable` notes; E2E asserts no unnamed buttons; disabled policy options carry the reason |
| Desktop and mobile layouts, accessible navigation | COMPLETE | E2E at 1280×900 and 390×844 (no overflow, menu toggle, `aria-current`, skip link) |

## 2. Unit tests (§13)

| Area | Status | Evidence |
| --- | --- | --- |
| Architecture validation | COMPLETE | `tests/test_core.py` (cycles, duplicate edges, fan-in, metadata) — CI |
| Graph hashing | COMPLETE | `test_validation_hash_is_deterministic` — CI |
| Serialization | COMPLETE | `tests/test_export.py`, SQL round trips in `tests/test_db_optional.py` — CI |
| Compiler logic | COMPLETE | `test_compiler_handles_serialized_order_and_backward`, `test_nasbench201_cell_uses_sum_fanin_semantics` |
| Generator sampling | COMPLETE | `tests/test_generator.py`, `tests/test_generator_nb201.py` (box; torch) |
| Predictor outputs | COMPLETE | `tests/test_predictor.py` (box; torch) |
| Search policies | COMPLETE | `tests/test_index_bayesian.py`, `tests/test_evolution.py`, `tests/test_index_learned_policies.py` |
| Pareto optimization | COMPLETE | `test_pareto_frontier`, `test_two_dimensional_hypervolume`, `test_pareto_evolution_needs_costs_and_uses_dominance` |
| Resource accounting | IN PROGRESS | analytical params/FLOPs and query budgets are tested; per-job compute/memory accounting is not |

## 3. Integration tests (§13)

| Pair | Status | Evidence / gap |
| --- | --- | --- |
| API ↔ DB | COMPLETE | `tests/test_db_optional.py`, Alembic up/down, live Postgres check (`tests/test_live_services.py`) |
| Search engine ↔ benchmark | COMPLETE | measured matrices on the real archive; `test_benchmark_worker_runs_bayesian_search_on_verified_directory` |
| Generator ↔ compiler | COMPLETE | `test_generator_samples_valid_compilable_graphs` |
| Predictor ↔ search | COMPLETE | `IndexPredictorGuided` uses the ArchAI predictor online; measured in the full-suite matrix |
| Experiment controller ↔ workers | IN PROGRESS | API jobs → Redis worker verified live; `SearchController` closed loop not executed by workers |
| Checkpoint persistence | COMPLETE | `scripts/verify_checkpoints.py` (SHA-256 + reload reproduces outputs), `test_training_updates_parameters_and_checkpoint_reloads_them` |
| Artifact exports | COMPLETE | JSON/safetensors/ONNX helpers tested; TorchScript export via API (`test_pytorch_export_loads_without_archai_and_runs`) and E2E |

## 4. End-to-end journey (§15) — browser E2E on the live stack

| Step | Status | Evidence / gap |
| --- | --- | --- |
| 1 Create research project | NOT STARTED | there is no project entity in the API or Studio |
| 2 Select task | IN PROGRESS | dataset field on search/training forms; no task catalogue |
| 3 Configure architecture constraints | NOT STARTED | constraint-conditioned generation exists only offline (NB201 generator) and is ineffective at smoke scale |
| 4 Generate candidates | COMPLETE | E2E (generator → registry), smoke checkpoint |
| 5 Inspect graphs | COMPLETE | E2E |
| 6 Start experiment | COMPLETE | E2E (search + training jobs) |
| 7 Monitor execution | COMPLETE | E2E (session status → succeeded) |
| 8 View real results | COMPLETE | E2E (search history, measured result sets) |
| 9 Compare architectures | COMPLETE | E2E |
| 10 Export valid PyTorch architectures | COMPLETE | E2E download; module loads and runs with no archai import |

## 5. ML verification (§16)

| Check | Status | Evidence |
| --- | --- | --- |
| Training updates parameters | COMPLETE | `test_training_updates_parameters_and_checkpoint_reloads_them` |
| Checkpoints reload | COMPLETE | same test, plus `research/results/archai_v1_smoke/checkpoint_verification.json` |
| Generated architectures execute | COMPLETE | `test_generator_samples_valid_compilable_graphs` |
| Gradients propagate | COMPLETE | `test_compiler_handles_serialized_order_and_backward` |
| Predictor evaluated on held-out data | COMPLETE (smoke scale) | `research/results/archai_v1_smoke/` (100 held-out cells) |
| Search budgets enforced | COMPLETE | `BenchmarkEvaluator` budget + `test_every_algorithm_runs_at_a_matched_budget_with_hypervolume` |
| Reproducible within documented tolerances | IN PROGRESS | seeded unit tests plus an exact-match repeat of random and Bayesian seed 0 (`research/results/nasbench201_cifar10_full_suite/reproducibility_seed0.json`, rev 07d729c vs recorded 2fe79d1). The other nine seeds and the torch policies were not repeated; no numeric tolerance is documented for them |
| Baselines fair | COMPLETE | matched budget (100), same 15,625-cell pool, fresh cache per run, hyperparameters fixed a priori in the committed config, learned policies trained only on in-budget queries; full-suite matrix recorded |

## 6. Deployment verification (§16)

| Check | Status | Evidence |
| --- | --- | --- |
| Services start reliably | IN PROGRESS | started twice from `infrastructure/local/README.md` (second time after a box replacement, with Postgres crash recovery); no automated repeated-start test |
| Migrations succeed | COMPLETE | Alembic on SQLite (CI) and PostgreSQL 17 (live) |
| Workers connect | COMPLETE | live check: Redis worker heartbeat and job execution |
| Auth works | COMPLETE | API-key tests in `tests/test_api.py`; live run with a key |
| APIs respond | COMPLETE | `scripts/live_service_check.py` |
| Frontend builds | COMPLETE | `next build` in CI (web job) |
| E2E journeys work | IN PROGRESS | browser E2E 31/31 on the live stack; journey steps 1 and 3 not implemented; not in CI |
| Restart / recovery tests | IN PROGRESS | lease-based recovery unit test; Postgres recovered after an unplanned box replacement (not a planned test); no scripted kill-and-recover test |
| Security checks | IN PROGRESS | `npm audit` 0, rate limiting, audit log, checksum gates; no Python dependency audit or static analysis |

## 7. Model metrics (§16)

| Metric set | Status | Evidence |
| --- | --- | --- |
| Generator: validity, uniqueness, diversity, constraint satisfaction, candidate quality | IN PROGRESS (measured at smoke scale only) | `research/results/archai_v1_smoke/generator_report.json`; the parameter constraint is not met better than random |
| Predictor: MAE, RMSE, Spearman, Kendall, calibration, held-out ranking | IN PROGRESS (measured at smoke scale only) | `research/results/archai_v1_smoke/predictor_report.json` |

## 8. Search suite and closed loop (§16)

| Item | Status | Evidence |
| --- | --- | --- |
| Random | COMPLETE | measured, `research/results/nasbench201_cifar10_full_suite/` |
| Regularized evolution | COMPLETE | same |
| Bayesian optimization | COMPLETE | same (GP-UCB) |
| Predictor-guided | COMPLETE | `IndexPredictorGuided`; measured in `research/results/nasbench201_cifar10_full_suite/` (10 seeds) and runnable as API/worker jobs (`policy_registry`) |
| Generator-guided | COMPLETE | `IndexGeneratorGuided`; measured in `research/results/nasbench201_cifar10_full_suite/` (10 seeds) and runnable as API/worker jobs (`policy_registry`) |
| Multi-objective / Pareto | COMPLETE | `IndexParetoEvolution`, hypervolume; measured in `research/results/nasbench201_cifar10_full_suite/` (10 seeds) and runnable as API/worker jobs (`policy_registry`) |
| Acquisition strategies | IN PROGRESS | UCB is used in the BO baseline; EI is implemented and unit-tested but not benchmarked |
| Budget accounting | COMPLETE | per-run `search_cost`, `BenchmarkEvaluator` |
| Closed loop (Generate → Validate → Rank → Train/Evaluate → Learn → Optimize → Repeat) with dedup, scheduling, recovery, cancellation and budgets | IN PROGRESS | `archai_search.learned.LearnedSearch` (persist/resume/cancel tested); generator-guided search closes the loop on benchmark lookups; not run as a worker job |

## Work order (current)

1. Done: full-suite matrix recorded; this plan; Studio realignment + browser E2E; search suite via API jobs;
   report template renamed to the spec title/sections; first report draft (`research/reports/2026-11-25-final-report-draft.md`).
2. Next: project entity + task selection (E2E steps 1–2); constraint inputs for generation (step 3);
   a non-smoke generator corpus; live training progress; torch in CI (B5); scripted restart/recovery test.
