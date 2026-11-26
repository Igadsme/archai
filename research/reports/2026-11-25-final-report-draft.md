# ARCHAI — FINAL ENGINEERING & RESEARCH COMPLETION REPORT

Draft, 25 November 2026 (updated 11:15 PM ET), America/New_York. Filled only with executed, labeled numbers. Anything not
measured is listed under §10. Verdict is in §11.

Template: `docs/FINAL_COMPLETION_REPORT_TEMPLATE.md`. Acceptance list: `docs/SPEC_ACCEPTANCE.md`.

## 1. Executive Summary

- Scope: complete the ArchAI monorepo on `feat/complete-archai` (draft PR #1) against Imani’s
  acceptance list: measured NATS-Bench search-suite comparison, smoke-scale ArchAI-V1 training,
  Studio realigned to the ten spec pages, and this report.
- Head of the branch at this update: `71756c3` and a following docs commit on `feat/complete-archai`
  (draft PR #1). All of this work is pushed (no force-push).
- **Verdict: PARTIALLY COMPLETE.** A matched-budget search suite is measured with CIs; the Studio
  talks to a real local stack; a 32/32 live browser E2E covers research-project create/select,
  constraint inputs, and the previous journey steps; generator and predictor quality numbers exist
  only at CPU smoke scale. GitHub python CI is red because the workflow still greps Alembic 0006
  and cannot be updated without `workflow` scope. COMPLETE AND VERIFIED is not claimed.
- Facts that justify the verdict:
  1. At 100 NATS-Bench TSS queries, 10 seeds, Bayesian optimization’s mean best validation accuracy
     is 91.59% [91.47, 91.67] vs. random 91.03% [90.93, 91.16] (`benchmark_lookup`; CIs do not
     overlap). Config `research/experiments/nasbench201_cifar10_full_suite.json` @ `2fe79d1`.
  2. Generator-guided, REINFORCE and multi-objective CIs overlap random on the same budget; the
     multi-objective hypervolume is not distinguishable from random (`benchmark_lookup`).
  3. ArchAI-V1 predictor, smoke-scale, held-out n=100: MAE 0.0539, Spearman 0.753 (`predicted`
     outputs scored against `benchmark_lookup` labels; training itself is smoke-scale).
  4. Live browser E2E, 32/32 checks at 1280×900 and 390×844 against API + Redis worker + Postgres +
     the verified archive (not in CI), including E2E step 1 (create/select project).
  5. CPU-smoke generator with sampled budget-ceiling conditioning (`a61f4e7`, 2000 cells, 300
     epochs, ~5.3 s): raw param-budget satisfaction 0.762 vs uniform random 0.915 vs the earlier
     point-estimate run 0.690. Hard rejection yield 0.781 (1000/1280), mean val acc 89.82% vs
     82.73% random feasible (`benchmark_lookup`). The condition alone is still not better than
     random; a budget must be enforced by filtering.
  5. Random and Bayesian seed-0 runs repeated at `07d729c` matched the recorded `2fe79d1` values
     exactly (`benchmark_lookup`).

**Evidence:** this report; `research/results/nasbench201_cifar10_full_suite/`;
`research/results/archai_v1_smoke/`; `TEST_REPORT.md`; `docs/COMPLETION_PLAN.md`;
`apps/web/e2e/README.md`.

## 2. GitHub

| Item | Value |
| --- | --- |
| Repository / branch / PR | https://github.com/Igadsme/archai · `feat/complete-archai` · draft PR #1 (https://github.com/Igadsme/archai/pull/1). Stays draft; no merges. |
| Last pushed commit | `6fffab5` Record the measured full search-suite matrix (7 policies + 4 ablations, 10 seeds, budget 100) |
| Local, unpushed (box) | `c03bd67` Studio realignment to the ten spec pages; `02a6b00` payload.result fix + live browser E2E; `07d729c` report template + completion plan; plus the commit that lands this draft. Push blocked: `GITHUB_TOKEN` unset after the 22:30 ET box replacement. |
| Earlier commits in scope (pushed) | `2fe79d1` policies; `b6fb591` smoke-train scripts; `d308cc6` smoke results + `docs/SPEC_ACCEPTANCE.md`; `5670f3f` skip torch tests in CI; `08d4476` completion plan; `3e7e9a7` policy registry and Studio API endpoints; `6fffab5` measured matrix. |
| CI on pushed commits | `3a83c53` success. `2fe79d1`, `b6fb591`, `d308cc6`: python job failed (torch imported in CI, which installs `.[dev,platform]` only); web passed. `5670f3f`, `08d4476`, `3e7e9a7`, `6fffab5`: python and web **success**. Unpushed commits have no Actions run. |
| CI URLs (green heads) | `08d4476`: https://github.com/Igadsme/archai/actions/runs/45748164004 · `3e7e9a7`: https://github.com/Igadsme/archai/actions/runs/45748468981 · `6fffab5`: https://github.com/Igadsme/archai/actions/runs/45748566766 |
| Branch protections, merges, force-pushes | none performed. `main` was not touched in this work (Imani’s revert `28feaa7` of `e322b6b` is already on `main`, CI green; `review/main-benchmark-integrity` left as is). No HF publishing, no paid resources. |

**Evidence:** GitHub Actions check runs for the SHAs above; local `git log`; `BLOCKERS.md` B1 (resolved).

## 3. Implementation

Statuses use the spec vocabulary. Details and gaps: `docs/COMPLETION_PLAN.md`.

| Subsystem | Status | What is verified | Gaps |
| --- | --- | --- | --- |
| Core schema / hashing | COMPLETE | `tests/test_core.py` (CI) | |
| Compiler | COMPLETE | serialization, backward, NAS-Bench-201 sum fan-in (CI / box torch) | |
| Generator | IN PROGRESS | unit tests + smoke training + API generate in E2E; constraint inputs + ceiling-conditioning rerun | raw budget-condition satisfaction still worse than random at smoke scale; API generate checkpoint is 2-example smoke |
| Predictor | IN PROGRESS | unit tests + smoke held-out metrics | smoke-scale only |
| Search policies | COMPLETE | unit tests + measured 10-seed matrix + API/worker registry | EI acquisition unit-tested, not benchmarked |
| Benchmark adapter | COMPLETE | official TSS protocol, checksum, measured matrices, live worker jobs | |
| Training engine | COMPLETE | param-update and reload test; live synthetic candidate job in E2E | no live per-epoch progress channel |
| API | COMPLETE | contract and Studio-endpoint tests; project CRUD; constraint merge; live `/readiness` | no audit-log read API; GitHub python CI red on stale Alembic grep |
| Worker / queue | COMPLETE | Redis worker ran the measured searches and E2E jobs; `tests/test_live_services.py` | closed-loop `LearnedSearch` not driven by the worker |
| Persistence | COMPLETE | Alembic 0007 on PostgreSQL 17 (live) and on local SQLite tests; experiment records and research projects | GitHub Actions still greps 0006, so the python job is red |
| Studio | IN PROGRESS | ten spec pages, real backend, 32/32 live E2E (including project + constraint fields), desktop + mobile | E2E not in GitHub Actions (B9) |

**Evidence:** `docs/COMPLETION_PLAN.md`; `TEST_REPORT.md`; `tests/`.

## 4. Machine Learning

ML verification checklist (spec §16):

| Check | Status | Evidence |
| --- | --- | --- |
| Training updates parameters | COMPLETE | `test_training_updates_parameters_and_checkpoint_reloads_them` |
| Checkpoints reload | COMPLETE | same test; `research/results/archai_v1_smoke/checkpoint_verification.json` |
| Generated architectures execute | COMPLETE | `test_generator_samples_valid_compilable_graphs`; E2E TorchScript load |
| Gradients propagate | COMPLETE | `test_compiler_handles_serialized_order_and_backward` |
| Predictor on held-out data | COMPLETE (smoke scale only) | `research/results/archai_v1_smoke/predictor_report.json` |
| Search budgets enforced | COMPLETE | `BenchmarkEvaluator`; full-suite `search_cost` = 100 on every run |
| Reproducible within tolerance | IN PROGRESS | random + Bayesian seed 0 exact-match repeat (below). Torch policies and the other seeds were not repeated. |
| Fair baselines | COMPLETE | matched budget, same 15,625-cell pool, fresh cache, a-priori hyperparameters in the committed config, in-budget learning only |

### Predictor (smoke-scale)

- Code revision: `2fe79d1`. Archive SHA-256 `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`.
- Split: 800 train / 100 validation / 100 held-out test cells; 30 epochs; seed 0. Test was not used for selection.
- Checkpoint (outside git): `/workspace/archai-data/checkpoints/archai_v1_predictor_smoke.pt`, SHA-256 `3392b86c628be7d4b627ac6ff23a0367efe0c2c80b12854e403f9c2906c613d2`.

| Split | MAE | RMSE | Spearman | Kendall | Interval coverage | Calibration error |
| --- | --- | --- | --- | --- | --- | --- |
| Held-out test (n=100) | 0.0539 | 0.0922 | 0.753 | 0.558 | 0.98 | 0.115 |
| Validation (n=100) | 0.0401 | 0.0487 | 0.716 | 0.544 | 1.00 | 0.132 |

These are scores of **predicted** accuracies against **benchmark_lookup** labels. The training run is
CPU smoke-scale and is not a quality claim at production scale.

### Generator (smoke-scale)

- Code revision: `b6fb591`. 2,000 training cells, 300 epochs, seed 0. Loss 1.613 → 1.278.
- Conditions: validation-accuracy quantile and `params_m / 1.6`. 1,000 samples per row.
- Checkpoint (outside git): `/workspace/archai-data/checkpoints/archai_v1_generator_smoke.pt`, SHA-256 `0ad684a2ae3cd7d9db911da104ca78b17cd8fce30a52a378b29726d379ad784e`.
- Evidence type for quality columns: sampled cell strings looked up in the archive (`benchmark_lookup`).

| Sampling | Mean val. acc. | Best val. acc. | ≤0.8M params | Unique | Novel vs. train | Valid in space | Connected |
| --- | --- | --- | --- | --- | --- | --- | --- |
| High-accuracy condition | 89.18 | 91.47 | 0.690 | 0.714 | 0.881 | 1.000 | 0.999 |
| Low-accuracy condition | 83.95 | 91.08 | 0.576 | 0.531 | 0.853 | 1.000 | 0.975 |
| Uniform random cells | 83.24 | 91.49 | 0.924 | 0.964 | 0.872 | 1.000 | 0.973 |
| Untrained generator | 84.42 | 91.55 | 0.850 | 0.973 | 0.865 | 1.000 | 0.982 |

The high-accuracy condition raises mean validation accuracy above random and the untrained
generator. The parameter-budget condition is **not** met better than random (0.690 vs. 0.924).

A separate 2-example corpus was trained on the live worker so the Studio generator page could be
E2E-tested (`archai_v1_api_generator_smoke.pt`, SHA-256 `66931a042259b0fee2a88ede0548de891b8d4453be1eab263e62d28c2e0fe544`,
loss 1.333 → 0.518, evidence `generator_training`, smoke-scale). That checkpoint is not a research
result.

**Evidence:** `research/results/archai_v1_smoke/`; `scripts/verify_checkpoints.py`;
`research/results/nasbench201_cifar10_full_suite/reproducibility_seed0.json`.

## 5. Research Results

### Protocol

- Search space: NATS-Bench TSS, all 15,625 cells. Official source, directory SHA-256
  `183b6ad84c437a36fbbe03f711cdb3a4bd6f3b8675e1af0536d3975f98fa4ba3`; tar SHA-256
  `580fd8f3425fed9f495640b0f12ccb7744f89dec7aff263bd75aed37ab0b8bb6` (no upstream SHA-256 is published;
  see `datasets/manifests/natsbench201.json`).
- Budget: **100 benchmark queries** per run, matched across every policy. Seeds **0–9** (10). Fresh
  cache per run.
- Select on `cifar10-valid` validation accuracy (hp=200); report `cifar10` test accuracy of the
  selected cell. Seed *s* reads archive trial `available[s % n]` (777/888/999).
- Learned policies start untrained and learn only from in-budget observations. Hyperparameters were
  fixed in the committed config before any run.
- Config: `research/experiments/nasbench201_cifar10_full_suite.json` @ `2fe79d1`.
- Command: `python scripts/run_experiment_matrix.py --config research/experiments/nasbench201_cifar10_full_suite.json --benchmark-path <archive dir> --benchmark-sha256 183b6ad8… --output <dir>`
  then `python scripts/build_report.py --runs runs.json --output report.json --min-seeds 10 --require-algorithm …`
  and `python scripts/summarize_matrix.py`.
- Wall clock: 850 s for all 110 runs on the box CPU. Evidence type for every accuracy, regret and
  hypervolume below: **`benchmark_lookup`**. No network was trained in these runs.

### Main table (mean [95% bootstrap CI], 10 seeds)

| Policy | Best validation acc. | Test acc. of selected cell | Regret vs. oracle (pp) | Hypervolume (val. %, params M; ref 0, 1.6) | Wall clock (s, all seeds) |
| --- | --- | --- | --- | --- | --- |
| bayesian | 91.59 [91.47, 91.67] | 94.28 [94.15, 94.40] | 0.106 [0.027, 0.220] | 135.27 [134.06, 136.41] | 73 |
| predictor_guided | 91.44 [91.19, 91.64] | 94.18 [93.90, 94.39] | 0.253 [0.055, 0.506] | 134.58 [133.23, 135.84] | 429 |
| evolution | 91.41 [91.23, 91.55] | 94.19 [93.98, 94.39] | 0.286 [0.147, 0.464] | 137.25 [136.70, 137.72] | 19 |
| generator_guided | 91.15 [91.01, 91.32] | 93.78 [93.57, 94.02] | 0.542 [0.375, 0.686] | 137.12 [136.53, 137.59] | 63 |
| reinforce | 91.14 [90.94, 91.33] | 94.05 [93.92, 94.17] | 0.554 [0.368, 0.757] | 137.56 [137.24, 137.82] | 19 |
| random | 91.03 [90.93, 91.16] | 93.78 [93.64, 93.93] | 0.662 [0.530, 0.770] | 137.50 [137.31, 137.72] | 18 |
| multi_objective | 90.97 [90.78, 91.17] | 93.56 [93.31, 93.79] | 0.721 [0.523, 0.915] | 137.59 [137.39, 137.78] | 21 |

Oracle cells (context only, never visible to a policy): 6111 (91.684 on trial 777; 91.720 on trial 888) and 9930 (91.684 on trial 999).

Interpretation: Bayesian and regularized-evolution CIs on best validation accuracy do not overlap
random, so a superiority claim is supported at this budget. Predictor-guided only just clears
random (its lower CI 91.19 vs. random’s upper 91.16). Generator-guided, REINFORCE and
multi-objective overlap random: **no superiority claim**. Multi-objective hypervolume is not
distinguishable from random (CIs overlap almost completely). Predictor-guided used more wall clock
because of online refits, and some of those runs shared the box with generator training.

### Ablations (mean [95% CI], 10 seeds)

| Ablation | What changed | Best validation acc. | vs. parent (CI overlap) |
| --- | --- | --- | --- |
| bayesian_no_uncertainty | `beta=0` | 91.49 [91.32, 91.63] | overlaps parent Bayesian |
| predictor_guided_small_pool | `candidate_pool_size=16` | 91.42 [91.30, 91.53] | overlaps parent predictor-guided |
| evolution_no_tournament | `sample_size=1` | 91.12 [90.94, 91.32] | overlaps parent evolution; also overlaps random |
| generator_guided_no_learning | `learn=False` | 91.09 [90.82, 91.34] | overlaps parent generator-guided; no measurable benefit from in-budget fine-tuning |

### Reproducibility repeat

Random and Bayesian seed 0 were re-run on 25 Nov 2026, 10:50 PM ET, at `07d729c`, same archive.
Selected index, validation, test and hypervolume matched the recorded `2fe79d1` values exactly
(random: cell 2581, val. 91.488; Bayesian: cell 10439, val. 91.180). Documented tolerance for these
two `benchmark_lookup` policies, on this archive, is exact equality of those four fields. The other
seeds and the torch policies were not repeated.

### Predicted numbers

None of the search-suite table entries are predicted. Predictor outputs appear only in §4, next to
their measured held-out error, and are labeled `predicted`.

**Evidence:** `research/results/nasbench201_cifar10_full_suite/{report,runs,results,pareto,results.regret,README,reproducibility_seed0}.json|md`.

## 6. Frontend and Backend

Studio pages (spec §10), all wired to the live API:

| Page | Route | Notable capability | Unavailable (stated in the UI) |
| --- | --- | --- | --- |
| Research Dashboard | `/` | Counts, measured-suite table, failed jobs | |
| Architecture Generator | `/generator` | Generate and save to the registry | Constraint-conditioned generation |
| Architecture Graph Explorer | `/explorer` | SVG DAG; JSON and TorchScript export | |
| Autonomous Search Laboratory | `/search` | All 7 policies; launch, cancel, 20-step history | |
| Pareto Optimization Explorer | `/pareto` | Measured fronts + live session front / hypervolume | |
| Training Laboratory | `/training` | Queue jobs; measured loss table after completion | Live per-epoch progress |
| Model Comparison | `/compare` | Policy table with CIs/regret; architecture compare | |
| Research Results | `/results` | Committed result sets, README, smoke reports | |
| Model Registry | `/models` | Checksum + tensor inspection | |
| System Administration | `/admin` | Readiness, queue, workers, datasets, failed jobs | Audit-log viewer; user/key management |

A TorchScript export from the explorer loaded and ran with **no `archai` modules imported**, output
shape `(2, 10)` for the architecture’s declared 8×8 input (standalone check after the E2E download).

E2E journeys (spec §15):

| Step | Status | Evidence |
| --- | --- | --- |
| 1 Create research project | NOT STARTED | no project entity |
| 2 Select task | IN PROGRESS | dataset field only |
| 3 Configure architecture constraints | NOT STARTED | marked Unavailable; see §10 |
| 4 Generate candidates | COMPLETE | browser E2E (smoke checkpoint) |
| 5 Inspect graphs | COMPLETE | browser E2E |
| 6 Start experiment | COMPLETE | browser E2E (search + training) |
| 7 Monitor execution | COMPLETE | browser E2E |
| 8 View real results | COMPLETE | browser E2E |
| 9 Compare architectures | COMPLETE | browser E2E |
| 10 Export valid PyTorch architectures | COMPLETE | E2E download + standalone load |

Auth: write routes require `x-api-key` when `ARCHAI_API_KEY_SHA256` is set (pytest + live E2E).
Rate limits use Redis (`/readiness` reports `rate_limit_backend=redis`). The API appends an audit
log; there is no read endpoint. Dataset, archive and checkpoint SHA-256 gates are enforced
(tampered checkpoints return 409).

**Evidence:** `apps/web/e2e/studio.e2e.mjs` (31/31, 25 Nov 2026, ~10:40 PM ET); screenshots in
`/workspace/archai-notes/screens/` (outside git); `tests/test_api_studio_endpoints.py`;
`tests/test_studio_contract.py`; `apps/web/tests/studio.test.ts` (22 passed).

## 7. QA

| Check | Command | Commit | Result (executed) |
| --- | --- | --- | --- |
| Python unit + integration (no live env) | `pytest -q` | `71756c3` tree | **187 passed, 3 skipped** (live-service tests skip without env) |
| CI mimic without torch | `PYTHONPATH=/tmp/notorch pytest -q` | same | **157 passed, 33 skipped** |
| Live-service tests | `pytest tests/test_live_services.py` against local Redis/Postgres | same | **3 passed** |
| Lint | `ruff check .` | same | All checks passed |
| Studio unit / typecheck / build | `npx vitest run`, `npm run typecheck`, `npm run build` | `71756c3` | 26 vitest passed; tsc clean; Next 16.4.6 build, 10 routes prerendered |
| Browser E2E (desktop + mobile) | `apps/web/e2e/studio.e2e.mjs` against live API + worker + NATS-Bench | `71756c3` | **32/32 passed**, 0 console errors |
| GitHub Actions | python + web | `71756c3` | **python failed** (Alembic grep still requires 0006; pytest and compileall succeeded). **web succeeded**. https://github.com/Igadsme/archai/actions/runs/45753820023 |

**Evidence:** `TEST_REPORT.md`; `/tmp/pt.txt`; `/workspace/archai-notes/e2e-run5.log` (API key redacted).

## 8. Deployment

| Check | Status | Evidence |
| --- | --- | --- |
| Services start reliably | IN PROGRESS | Started from `infrastructure/local/README.md` twice (second time after the box replacement, including Postgres crash recovery). No automated repeated-start test. |
| Migrations succeed | IN PROGRESS | Alembic 0007 on PostgreSQL 17.12 (live) and local SQLite tests; GitHub Actions still greps 0006 and fails |
| Workers connect | COMPLETE | Heartbeat on `/v1/infrastructure/workers`; E2E jobs ran |
| Auth works | COMPLETE | pytest + live E2E; after a log leak the local key was rotated and the old key received HTTP 401 |
| APIs respond | COMPLETE | `/readiness` = ready, redis rate limits, database ready (25 Nov 2026, 10:35 PM ET and after) |
| Frontend builds | COMPLETE | `next build` locally and in CI (web job, last pushed SHA) |
| E2E journeys work | IN PROGRESS | 32/32 live browser E2E including steps 1 and 3 inputs; not in GitHub Actions |
| Restart / recovery | IN PROGRESS | Lease recovery unit test; Postgres recovered after the unplanned replacement. No scripted kill-and-recover of a mid-flight job. |
| Security checks | IN PROGRESS | `npm audit` 0 historically; API-key, rate limits, audit log, path allow-list, checksum gates. No Python dependency audit or static analysis this draft. |

Environment (box, 25 Nov 2026):

| Item | Value |
| --- | --- |
| Hardware | 8-core CPU, 15 GB RAM, **GPU: none** |
| OS / Python / torch / Node | Debian; Python 3.13.5; torch 2.15.0+cpu; Node 24.22.1; Next 16.4.6 |
| Services | PostgreSQL 17.12 on 127.0.0.1:5433 (`shared_buffers=64MB`); Redis 8.0.2 on 127.0.0.1:6379 (`maxmemory 128mb`) |
| Paid or hosted resources used | **none** |

**Evidence:** `infrastructure/local/README.md`; `TEST_REPORT.md`; `/workspace/archai-notes/PROGRESS.md`.

## 9. Resource Efficiency

- Full-suite matrix: 110 runs, **850 s** wall clock on the box CPU (shared with other jobs). Individual
  policy totals are in §5 (predictor-guided 429 s because of online refits).
- Reproducibility repeats: random seed 0 in 2.0 s, Bayesian seed 0 in 7.0 s.
- Predictor smoke: 1,000 cells, 30 epochs, CPU. Generator smoke: 2,000 cells, 300 epochs, CPU
  (one run slowed to 286 s under contention with the matrix; an earlier uncontended run was 53 s).
- Data outside git: NATS-Bench `-simple` directory 1.1 GB + tar 1.1 GB; full-space table 7.7 MB;
  checkpoints 348 KB. Box disk at writing had ~102 GB free of 125 GB.
- Memory caps: Redis 128 MB, Postgres `shared_buffers` 64 MB, `max_connections` 20. After the
  replacement, ~12 GB RAM was still available with the live stack running.
- Deliberately not run: any GPU or paid/cloud job; a second full 10-seed matrix; ImageNet or
  additional datasets; production-scale generator/predictor training.

**Evidence:** result-set READMEs; `/workspace/archai-notes/PROGRESS.md`; `du` of `/workspace/archai-data`.

## 10. Blockers

| ID | Blocker | Type | Owner | What unblocks it |
| --- | --- | --- | --- | --- |
| B1 | `main` @ e322b6b broke integrity tests | resolved | Imani | Revert `28feaa7` is on `main`, CI green. `review/main-benchmark-integrity` kept. |
| B2 / B6 | Truncated spec (page names, acceptance text) | resolved | Imani / Monday | `docs/SPEC_ACCEPTANCE.md` |
| B3 | Hugging Face publication (M12) | decision | Imani | Authorization and a release decision |
| B4 | GPU / large-scale training | decision / external | Imani | Approve compute if larger than CPU smoke is wanted |
| B5 | Token lacks `workflow` scope; CI still greps Alembic 0006 and the python job is red from `f6ccb2d` | engineering / decision | Imani | Grant `workflow` scope or apply `docs/ci/ci.yml` in the GitHub UI |
| B7 | Research-project entity | resolved | engineering | Alembic 0007, API CRUD, Studio create/select, E2E step 1 passed |
| B8 | Constraint inputs are implemented; smoke-scale param-budget *condition* is still worse than random (0.762 vs 0.915) | engineering (quality) | Imani | Hard filter is the honest enforcement path at this scale; a larger corpus if the condition itself is to be improved |
| B9 | Browser E2E is not in GitHub Actions (same `workflow` scope rejection as B5) | engineering / decision | Imani | Same as B5, plus a runner that has the live stack |
| — | Local API key was rotated 25 Nov 2026, 10:42 PM ET after an E2E Playwright error echoed the key field | process | engineering | Already rotated; E2E now redacts stdout/stderr. The key lives in `/workspace/archai-data/live/api-key` (never committed). |
| — | `GITHUB_TOKEN` is present again; later commits were pushed normally | process | — | — |

Unmeasured, and therefore **not** claimed: production-scale generator/predictor quality; a repeated
full 10-seed matrix (only seed 0 of random and Bayesian was repeated); EI vs. UCB on the archive;
ImageNet or datasets other than NATS-Bench TSS CIFAR-10; live per-epoch training progress; a
worker-driven Generate→…→Repeat closed loop that includes real training; Python dependency audit;
scripted mid-flight worker recovery; any GPU number.

## 11. Final Verdict

**PARTIALLY COMPLETE.**

The search suite is implemented and measured at a matched budget with CIs and fair-baseline
controls; the Studio’s ten spec pages talk to a real local backend and a live browser E2E covers
journey steps 4–10 at desktop and mobile widths; smoke-scale predictor and generator metrics exist
and are labeled as such. COMPLETE AND VERIFIED is reserved for the entire acceptance suite, which
this is not: GitHub python CI is red because the workflow cannot be edited without `workflow`
scope; the generator's param-budget condition is still not better than random at smoke scale
(filtering is required); CI does not install torch or run the browser E2E; and every quality
number for ArchAI-V1 itself is smoke-scale.

**Evidence:** §§1–10 of this draft; `docs/COMPLETION_PLAN.md`; `TEST_REPORT.md`; `BLOCKERS.md`.
