# Blockers and open questions

Updated 2026-11-25 11:28 PM ET (America/New_York). Each entry names who can unblock it.

| # | Blocker | Impact | Owner / unblock |
| --- | --- | --- | --- |
| B1 | ~~`main` @ e322b6b empties `integrity.py` and `tests/test_benchmark.py`; CI on `main` fails~~ **Resolved.** Imani approved the revert; `28feaa7` is on `main` and `main`'s CI is green. `review/main-benchmark-integrity` is unchanged. | — | — |
| B2 | ~~Studio page names were in a truncated part of the spec~~ **Resolved.** Exact names and acceptance text are in `docs/SPEC_ACCEPTANCE.md`; the Studio is realigned to those ten pages. | — | — |
| B3 | Hugging Face publication (M12) | No public model release | Imani: HF authorization and release decision |
| B4 | GPU / large-scale training | Only CPU smoke-scale training is allowed on the box; ArchAI-V1 quality numbers are smoke-scale only | Imani: approve compute if larger runs are wanted |
| B5 | ~~The GitHub token lacked `workflow` scope, so `.github/workflows/ci.yml` could not be updated and the python job failed the hardcoded 0006 Alembic grep.~~ **Resolved** at `a69f60a` (11:26–11:27 PM ET, America/New_York). The token now has Workflows read/write. The proposal is applied: ruff, Node 22, `npm ci`, a CPU-only `python-torch` job, and an Alembic check that compares `alembic current` to `alembic heads` (no hardcoded revision). Push and PR CI are green: python 156 passed / 35 skipped; python-torch 188 passed / 3 skipped; web succeeded. | — | — |
| B6 | ~~Full experiment spec text truncated~~ **Resolved.** Acceptance criteria (including the report title and sections) are in `docs/SPEC_ACCEPTANCE.md`. | — | — |
| B7 | ~~No research-project entity~~ **Resolved** at `f6ccb2d` (Alembic 0007, API CRUD, Studio create/select). Live E2E step 1 passed at `71756c3`. | — | — |
| B8 | Constraint *inputs* are in the API, generator, search, and Studio (`a61f4e7`). At CPU smoke scale, ceiling conditioning improved raw param-budget satisfaction from 0.690 (earlier point estimate) to 0.762, but that is still worse than uniform random (0.915). Hard rejection (yield 0.781, 1000/1280 draws) keeps a quality edge (mean val 89.82% vs 82.73% random feasible). | No honest claim that the condition alone meets a param budget better than random. A non-smoke corpus would be needed to revisit that. | Imani: approve more compute only if a larger training run is wanted |
| B9 | Browser E2E and live-stack tests are not in GitHub Actions. A CI job was not added because it cannot run reliably on GitHub-hosted runners: it needs a live API, worker, Postgres, Redis, and the checksum-verified NATS-Bench archive, which are not available there. Local E2E is **32/32** at `71756c3`. | Actions does not run the live Studio journey | Imani: a runner (or self-hosted stack) that has the archive and services, if CI E2E is wanted |
