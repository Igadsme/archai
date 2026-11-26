# Blockers and open questions

Updated 2026-11-25 10:50 PM ET (America/New_York). Each entry names who can unblock it.

| # | Blocker | Impact | Owner / unblock |
| --- | --- | --- | --- |
| B1 | ~~`main` @ e322b6b empties `integrity.py` and `tests/test_benchmark.py`; CI on `main` fails~~ **Resolved.** Imani approved the revert; `28feaa7` is on `main` and `main`'s CI is green. `review/main-benchmark-integrity` is unchanged. | — | — |
| B2 | ~~Studio page names were in a truncated part of the spec~~ **Resolved.** Exact names and acceptance text are in `docs/SPEC_ACCEPTANCE.md`; the Studio is realigned to those ten pages. | — | — |
| B3 | Hugging Face publication (M12) | No public model release | Imani: HF authorization and release decision |
| B4 | GPU / large-scale training | Only CPU smoke-scale training is allowed on the box; ArchAI-V1 quality numbers are smoke-scale only | Imani: approve compute if larger runs are wanted |
| B5 | CI installs `.[dev,platform]` (no torch). Workflow file edits may need the token's `workflow` scope | Torch tests skip in GitHub Actions (`5670f3f`); `docs/ci/ci.yml` remains a proposal | Imani: add the ml extra to CI, or apply the proposal / grant scope |
| B6 | ~~Full experiment spec text truncated~~ **Resolved.** Acceptance criteria (including the report title and sections) are in `docs/SPEC_ACCEPTANCE.md`. | — | — |
| B7 | No research-project entity | E2E journey step 1 is NOT STARTED | Engineering: add a project resource and a Studio flow |
| B8 | Architecture constraints are not inputs to the API generator; at smoke scale the NB201 parameter-budget condition is not met better than random | E2E journey step 3 is NOT STARTED; no constraint-satisfaction quality claim | Engineering: constraint inputs, and a non-smoke corpus if quality is to be claimed |
| B9 | Browser E2E and the live Postgres/Redis tests are not in GitHub Actions | Green CI does not imply the 31/31 live Studio journey still passes | Engineering: a CI job would need the stack (currently out of scope) |
