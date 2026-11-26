# ArchAI final engineering report — template

Copy this file to `research/reports/<YYYY-MM-DD>-<slug>.md` and fill every section. Leave a section
in place and write "not run" rather than deleting it. Rules that apply to every number in the report:

- **Label every number with its evidence type:** `measured_training`, `benchmark_lookup` (a tabular
  benchmark read, not a training run), or `predicted` (surrogate output). Never mix types in one column.
- **Selection uses validation data only.** Test accuracy is reported for the selected architecture
  and is never used to choose it.
- **Cite the exact config** (committed JSON path plus the commit hash) and the dataset or archive
  SHA-256 for each result. A number without a config and a commit does not belong in the report.
- **Report spread, not just means:** seeds, the number of runs, and a 95% bootstrap CI. If the
  intervals overlap, say so and make no superiority claim.
- **Smoke-scale runs are labeled smoke-scale.** Synthetic-data training shows that the pipeline
  works. It says nothing about quality.

## 1. Summary

- Question asked:
- Answer, in one or two sentences, with the evidence type:
- Commit(s): `<sha>` · Branch/PR:
- Report date (ET):

## 2. Scope and status

| Milestone | Status (done / partial / not started) | Evidence (file, test, or run) |
| --- | --- | --- |
| | | |

## 3. Environment

| Item | Value |
| --- | --- |
| Hardware | e.g. box CPU, cores, RAM; GPU: none |
| OS / Python / torch / Node | |
| Services | e.g. local Postgres <ver> (port), Redis <ver> (maxmemory) — or "none" |
| Paid or hosted resources used | must be "none" unless explicitly approved |

## 4. Data and benchmark provenance

| Artifact | Source (official URL) | Version | SHA-256 | Verified against published value? | Location (outside git) |
| --- | --- | --- | --- | --- | --- |
| | | | | yes / no published value | |

## 5. Experimental protocol

- Search space and candidate pool (indices):
- Budget (benchmark queries or training epochs) per run:
- Seeds:
- Selection metric and split:
- Reported metric and split:
- Config file(s): `research/experiments/<name>.json` at commit `<sha>`
- Command(s), verbatim:

## 6. Results

Evidence type: `<measured_training | benchmark_lookup | predicted>`. Config: `<path>@<sha>`.

| Arm / variant | Runs | Best validation (mean, 95% CI) | Test of selected (mean, 95% CI) | Wall clock |
| --- | --- | --- | --- | --- |
| | | | | |

Interpretation, including whether the CIs overlap:

## 7. Ablations

| Ablation | What changed | Δ validation vs. parent arm (mean, CI) | Conclusion |
| --- | --- | --- | --- |
| | | | |

## 8. Predicted numbers (if any)

List the surrogate and generator outputs here, kept apart from the measured results. Include the
predictor checkpoint SHA-256 and its held-out error (`measured`) next to each prediction (`predicted`).

## 9. Tests and CI

| Check | Command | Commit | Result (executed) |
| --- | --- | --- | --- |
| Python tests | `pytest -q` | | |
| Lint | `ruff check .` | | |
| Studio tests / typecheck / build | `npm test`, `npm run typecheck`, `npm run build` | | |
| GitHub Actions | workflow run URL | | |

## 10. Security and safety review

- Auth, rate limiting, and the audit log: what was exercised and how.
- Integrity gates (checksums on datasets, archives, and checkpoints):
- Known gaps:

## 11. Limitations and threats to validity

- Benchmark-lookup results reflect the benchmark's training protocol, not new training.
- Scale limits (CPU-small budgets, small seed counts):
- Anything not run, and why:

## 12. Open blockers and decisions needed

| ID | Blocker | Owner | Decision needed |
| --- | --- | --- | --- |
| | | | |

## 13. Reproduction

Exact steps from a clean checkout, including the data download and checksum verification, the
service startup, and every command whose output appears above.

## Appendix: raw artifacts

Paths to the `report.json` and `runs.json` files, the logs, and the audit-log excerpts.
