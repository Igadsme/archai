# Blockers and open questions

Updated 2026-11-26 12:31 AM ET (America/New_York). Each entry names who can unblock it.

| # | Blocker | Impact | Owner / unblock |
| --- | --- | --- | --- |
| B1 | ~~`main` @ e322b6b empties `integrity.py` and `tests/test_benchmark.py`; CI on `main` fails~~ **Resolved.** Imani approved the revert; `28feaa7` is on `main` and `main`'s CI is green. `review/main-benchmark-integrity` is unchanged. | — | — |
| B2 | ~~Studio page names were in a truncated part of the spec~~ **Resolved.** Exact names and acceptance text are in `docs/SPEC_ACCEPTANCE.md`; the Studio is realigned to those ten pages. | — | — |
| B3 | Hugging Face publication (M12) | No public model release | Imani: HF authorization and release decision |
| B4 | GPU / large-scale training | Only CPU smoke-scale training is allowed on the box; ArchAI-V1 quality numbers are smoke-scale only | Imani: approve compute if larger runs are wanted |
| B5 | ~~The GitHub token lacked `workflow` scope, so `.github/workflows/ci.yml` could not be updated and the python job failed the hardcoded 0006 Alembic grep.~~ **Resolved** at `a69f60a` (11:26–11:27 PM ET, America/New_York). The token now has Workflows read/write. The proposal is applied: ruff, Node 22, `npm ci`, a CPU-only `python-torch` job, and an Alembic check that compares `alembic current` to `alembic heads` (no hardcoded revision). Push and PR CI are green: python 156 passed / 35 skipped; python-torch 188 passed / 3 skipped; web succeeded. | — | — |
| B6 | ~~Full experiment spec text truncated~~ **Resolved.** Acceptance criteria (including the report title and sections) are in `docs/SPEC_ACCEPTANCE.md`. | — | — |
| B7 | ~~No research-project entity~~ **Resolved** at `f6ccb2d` (Alembic 0007, API CRUD, Studio create/select). Live E2E step 1 passed at `71756c3`. | — | — |
| B8 | ~~Smoke-scale param-budget *condition* worse than random~~ **Resolved** at `6ca450d` / `f7b7e48` (CPU smoke, 2000 cells, 300 epochs, seed 0, `ceiling_bins`). Raw satisfaction **0.983 vs uniform random 0.908**, mean val acc 89.49 vs 83.41 (`benchmark_lookup`). Hard-reject yield 0.977 (1000/1024), mean val 89.71 vs 82.73 random feasible. A 40-epoch rejection-penalty ablation hit satisfaction 1.0 but dropped mean val below random (74.18 vs 83.41) and was not selected. This is still smoke-scale, not a production-quality claim. | — | — |
| B9 | ~~Browser E2E not in GitHub Actions~~ **Resolved** at `0339a9c` (fixture + adapter) / `0dff0de` (CI green). `studio-e2e (fixture-only)` boots Postgres 16 and Redis 7 service containers, uses the committed 256-cell fixture (`datasets/fixtures/natsbench-tss-cifar10-256`, labeled fixture-only, not a research result), and runs Playwright. **33/33 passed** at `0dff0de`. Local official-archive E2E remains **32/32** at `71756c3`. | — | — |
