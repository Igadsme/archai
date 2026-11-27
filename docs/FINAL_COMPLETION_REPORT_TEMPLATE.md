# ARCHAI — FINAL ENGINEERING & RESEARCH COMPLETION REPORT

<!-- Template. Title and section list are fixed by docs/SPEC_ACCEPTANCE.md (line 27). Copy to
research/reports/<YYYY-MM-DD>-final-report.md and fill every section. Keep a section and write "not run"
rather than deleting it. Every section ends with an **Evidence** list of links (file@commit, test id, CI
run URL, result-set path). -->

Rules for every number:

- **Label its evidence type:** `benchmark_lookup` (tabular-benchmark read, not new training),
  `measured_training`, `synthetic_training` / smoke-scale (pipeline check only, says nothing about quality),
  `analytical` (computed from the graph), or `predicted` (surrogate output). Never mix types in one column.
- **Selection uses validation data only.** Test accuracy is reported for the selected architecture only.
- **Cite config + commit + data checksum.** A number without all three does not belong here.
- **Report spread:** seeds, run count, 95% bootstrap CI. Overlapping CIs → no superiority claim.
- **Statuses** (spec vocabulary): COMPLETE (implemented *and verified*), IN PROGRESS, BLOCKED, NOT STARTED,
  FAILED. Interface-only work is never COMPLETE. "No success from smoke tests alone."

## 1. Executive Summary

- Scope of this report, date (ET), branch / PR, head commit.
- Verdict (from §11) and the 3–5 facts that justify it, each with its evidence type.
- **Evidence:**

## 2. GitHub

| Item | Value |
| --- | --- |
| Repository / branch / PR (draft?) | |
| Commits in scope (sha — subject) | |
| CI runs (URL — conclusion) per commit | |
| Branch protections, merges, force-pushes | must be "none" unless approved |

**Evidence:**

## 3. Implementation

Acceptance status per subsystem (core schema/hashing, compiler, generator, predictor, search, benchmark
adapter, training engine, API, worker/queue, persistence, Studio), using the spec statuses.

| Subsystem | Status | What is verified (test / run) | Gaps |
| --- | --- | --- | --- |

**Evidence:**

## 4. Machine Learning

- ML verification checklist (spec §16): training updates params · checkpoints reload · generated archs
  execute · gradients propagate · predictor on held-out data · budgets enforced · reproducible within
  tolerance · fair baselines — each with status and test/run.
- Predictor metrics (MAE, RMSE, Spearman, Kendall, calibration, held-out ranking) with split sizes.
- Generator metrics (validity, uniqueness, diversity, constraint satisfaction, candidate quality).
- Checkpoints: path (outside git), SHA-256, scale label.

**Evidence:**

## 5. Research Results

- Protocol: search space, candidate pool, budget, seeds, selection split, reported split, config@commit,
  archive SHA-256, verbatim command.
- Main table (mean [95% CI]) per policy: best validation, test of selected, regret vs. oracle,
  hypervolume, search cost. Ablations table with Δ vs. parent arm. CI-overlap interpretation.
- Predicted numbers, if any, in a separate table next to the predictor's measured held-out error.

**Evidence:**

## 6. Frontend and Backend

- Studio pages (spec §10) and the capability each provides; unavailable features as stated in the UI.
- API surface exercised; auth, rate limiting, audit log; integrity gates.
- E2E journeys (spec §15, steps 1–10): status per step with the run that shows it.

**Evidence:**

## 7. QA

| Check | Command | Commit | Result (executed) |
| --- | --- | --- | --- |
| Python unit + integration | `pytest -q` | | |
| CI mimic without torch | | | |
| Live-service tests | `pytest tests/test_live_services.py` | | |
| Lint | `ruff check .` | | |
| Studio unit / typecheck / build | `npm test`, `npm run typecheck`, `npm run build` | | |
| Browser E2E (desktop + mobile) | `npm run e2e` | | |
| GitHub Actions | run URL | | |

**Evidence:**

## 8. Deployment

Deployment verification (spec §16): services start · migrations · workers connect · auth · APIs respond ·
frontend builds · E2E journeys · restart/recovery · security checks — status each. Environment table
(hardware, OS, Python, torch, Node, Postgres, Redis, paid/hosted resources = none).

**Evidence:**

## 9. Resource Efficiency

CPU/RAM/disk budget used, wall clock per experiment, data footprint (outside git), memory caps
(Redis maxmemory, Postgres shared_buffers), and what was deliberately not run to stay small.

**Evidence:**

## 10. Blockers

| ID | Blocker | Type (external / decision / engineering) | Owner | What unblocks it |
| --- | --- | --- | --- | --- |

Also list every acceptance item that was **not measured** and why.

## 11. Final Verdict

One of: COMPLETE AND VERIFIED (only if the entire acceptance suite passes) / FUNCTIONAL BUT NOT
PRODUCTION-READY / PARTIALLY COMPLETE / BLOCKED BY EXTERNAL DEPENDENCIES — with the deciding reasons.

**Evidence:**
