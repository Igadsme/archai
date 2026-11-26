# Blockers and open questions

Updated 2026-11-25 (America/New_York). Each entry names who can unblock it.

| # | Blocker | Impact | Owner / unblock |
| --- | --- | --- | --- |
| B1 | `main` @ e322b6b empties `integrity.py` and `tests/test_benchmark.py`; CI on `main` fails | Default branch is red | Imani: decide to revert or explain intent. Preserved on `review/main-benchmark-integrity` |
| B2 | Studio spec names 10 pages, but the names were in a truncated part of the spec | Page set is inferred | Imani: confirm or replace the inferred list in `docs/COMPLETION_PLAN.md` |
| B3 | Hugging Face publication (M12) | No public model release | Imani: HF authorization and release decision |
| B4 | GPU / large-scale training | Only CPU smoke-scale training is allowed on the box | Imani: approve compute if larger runs are wanted |
| B5 | CI workflow edits may need the token's `workflow` scope | `docs/ci/ci.yml` is a proposal | Imani: apply it manually, or grant scope |
| B6 | Full experiment spec text (middle section truncated) | Some acceptance criteria may be missing from the audit | Imani/Monday: resend the full spec |
