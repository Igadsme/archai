# ArchAI completion plan, tracked against the acceptance list

Source of truth: `docs/SPEC_ACCEPTANCE.md` (Imani's spec, Studio §10 and acceptance §13/15/16).
The earlier audit-driven plan (passes 1–3) is kept in `docs/history/COMPLETION_PLAN_passes_1-3.md`.

**Status vocabulary (spec):** COMPLETE = implemented *and* verified by an executed check ·
IN PROGRESS · BLOCKED · NOT STARTED · FAILED. Interface-only work is never COMPLETE, and smoke tests
alone never count as success. Evidence points at tests, scripts, or `TEST_REPORT.md` rows. "CI"
means GitHub Actions. CI installs `.[dev,platform]` without torch, so torch-dependent tests run on
the box only (see BLOCKERS B5).

**Current verdict: PARTIALLY COMPLETE.** COMPLETE AND VERIFIED requires the entire acceptance suite,
and the E2E journey and several Studio capabilities are not done.

## 1. Studio pages (§10)

The ten pages were built under inferred names (now superseded by the spec list). Renaming and
realigning them is the next Studio step. No page is COMPLETE until it is wired to real backend data
and an automated desktop and mobile E2E check exercises it.

| # | Spec page | Current route / page | Status | Gap |
| --- | --- | --- | --- | --- |
| 1 | Research Dashboard | `/` Overview | IN PROGRESS | rename; no E2E |
| 2 | Architecture Generator | `/generator` | IN PROGRESS | API generate only supports chain-vocabulary checkpoints; constraints UI missing |
| 3 | Architecture Graph Explorer | `/architectures` | IN PROGRESS | rename; no PyTorch export action |
| 4 | Autonomous Search Laboratory | `/search` | IN PROGRESS | API search jobs support random/evolution/bayesian only; search-history view missing |
| 5 | Pareto Optimization Explorer | — | NOT STARTED | needs a front view over measured runs |
| 6 | Training Laboratory | `/training` | IN PROGRESS | rename; training progress view missing |
| 7 | Model Comparison | — (Leaderboard is related) | NOT STARTED | compare architectures and benchmark results side by side |
| 8 | Research Results | `/experiments` + `/leaderboard` | IN PROGRESS | merge; link measured matrix results |
| 9 | Model Registry | `/models` | IN PROGRESS | checkpoint inspection (metadata, SHA-256 check) missing |
| 10 | System Administration | `/infrastructure` (+ `/datasets`) | IN PROGRESS | rename; error reporting view |

| Required capability | Status | Evidence / gap |
| --- | --- | --- |
| Architecture generation | IN PROGRESS | `POST /v1/architectures/generate`; returns 503 without a compatible checkpoint |
| Architecture visualization | IN PROGRESS | node/edge view in `/architectures`; not E2E-tested |
| Real search sessions | IN PROGRESS | launch form → Redis worker (live check, TEST_REPORT); UI path not E2E-tested |
| Experiment monitoring | IN PROGRESS | job polling and cancel |
| Training progress | NOT STARTED | only job status is shown, no per-epoch progress |
| Search-history inspection | NOT STARTED | the API stores search records; no history/trace view |
| Checkpoint inspection | NOT STARTED | |
| Benchmark comparisons | NOT STARTED | the measured tables exist in `research/results/`; not surfaced in the UI |
| Architecture export | NOT STARTED | JSON/safetensors/ONNX exist in `archai_compiler.export`; no PyTorch-source export, no API or UI |
| Error reporting | IN PROGRESS | API errors are surfaced in forms; no central error view |
| Unavailable features marked, no decorative controls | IN PROGRESS | to be audited during realignment |
| Desktop and mobile layouts, accessible navigation | IN PROGRESS | responsive CSS exists; no mobile test |

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
| Artifact exports | IN PROGRESS | JSON/safetensors/ONNX helpers tested; PyTorch export missing |

## 4. End-to-end journey (§15) — no automated E2E exists yet

| Step | Status |
| --- | --- |
| 1 Create research project | NOT STARTED (there is no project entity) |
| 2 Select task | IN PROGRESS (dataset field on search form) |
| 3 Configure architecture constraints | NOT STARTED |
| 4 Generate candidates | IN PROGRESS |
| 5 Inspect graphs | IN PROGRESS |
| 6 Start experiment | IN PROGRESS |
| 7 Monitor execution | IN PROGRESS |
| 8 View real results | IN PROGRESS |
| 9 Compare architectures | IN PROGRESS (`GET /v1/architectures/compare` only) |
| 10 Export valid PyTorch architectures | NOT STARTED |

## 5. ML verification (§16)

| Check | Status | Evidence |
| --- | --- | --- |
| Training updates parameters | COMPLETE | `test_training_updates_parameters_and_checkpoint_reloads_them` |
| Checkpoints reload | COMPLETE | same test, plus `research/results/archai_v1_smoke/checkpoint_verification.json` |
| Generated architectures execute | COMPLETE | `test_generator_samples_valid_compilable_graphs` |
| Gradients propagate | COMPLETE | `test_compiler_handles_serialized_order_and_backward` |
| Predictor evaluated on held-out data | COMPLETE (smoke scale) | `research/results/archai_v1_smoke/` (100 held-out cells) |
| Search budgets enforced | COMPLETE | `BenchmarkEvaluator` budget + `test_every_algorithm_runs_at_a_matched_budget_with_hypervolume` |
| Reproducible within documented tolerances | IN PROGRESS | seeded determinism tested; no documented tolerance or repeat of a full matrix |
| Baselines fair | IN PROGRESS | matched budget, same pool, fresh cache, a-priori hyperparameters, in-budget learning only; confirmed when the full-suite matrix completes |

## 6. Deployment verification (§16)

| Check | Status | Evidence |
| --- | --- | --- |
| Services start reliably | IN PROGRESS | local stack started once (`infrastructure/local/README.md`); no repeated-start test |
| Migrations succeed | COMPLETE | Alembic on SQLite (CI) and PostgreSQL 17 (live) |
| Workers connect | COMPLETE | live check: Redis worker heartbeat and job execution |
| Auth works | COMPLETE | API-key tests in `tests/test_api.py`; live run with a key |
| APIs respond | COMPLETE | `scripts/live_service_check.py` |
| Frontend builds | COMPLETE | `next build` in CI (web job) |
| E2E journeys work | NOT STARTED | |
| Restart / recovery tests | IN PROGRESS | lease-based recovery unit test; no live kill-and-recover test |
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
| Predictor-guided | IN PROGRESS → COMPLETE when the full-suite matrix is recorded | `IndexPredictorGuided` |
| Generator-guided | IN PROGRESS → COMPLETE when the full-suite matrix is recorded | `IndexGeneratorGuided` |
| Multi-objective / Pareto | IN PROGRESS → COMPLETE when the full-suite matrix is recorded | `IndexParetoEvolution`, hypervolume |
| Acquisition strategies | IN PROGRESS | UCB is used in the BO baseline; EI is implemented and unit-tested but not benchmarked |
| Budget accounting | COMPLETE | per-run `search_cost`, `BenchmarkEvaluator` |
| Closed loop (Generate → Validate → Rank → Train/Evaluate → Learn → Optimize → Repeat) with dedup, scheduling, recovery, cancellation and budgets | IN PROGRESS | `archai_search.learned.LearnedSearch` (persist/resume/cancel tested); generator-guided search closes the loop on benchmark lookups; not run as a worker job |

## Work order (current)

1. Finish the full-suite measured matrix and record it (`scripts/build_report.py`, `scripts/summarize_matrix.py`).
2. This plan (done in this commit; statuses are updated as work lands).
3. Studio realignment to the ten spec pages, plus the Pareto explorer, model comparison, PyTorch export
   and checkpoint inspection; mark unavailable features explicitly; desktop and mobile checks.
4. Search suite exposed through API jobs (policies in item 8).
5. `docs/FINAL_REPORT_TEMPLATE.md` → spec title and sections; first draft filled with measured results only.
