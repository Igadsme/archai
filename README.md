# ArchAI — AI That Designs AI

ArchAI is a research platform for constrained neural architecture search. The initial implementation targets the NAS-Bench-201/NATS-Bench cell search space and keeps analytical metrics, learned predictions, benchmark lookups, and real training results separate.

## Current evidence status

This repository contains an executable research foundation: a typed architecture schema, strict validation, deterministic hashing, a restricted PyTorch compiler, graph encoder models, budget-aware search policies, and an API surface. No model checkpoint or benchmark result is claimed by this repository until a user runs the documented experiments and stores the resulting provenance manifest.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
uvicorn archai_api.main:app --port 8000   # or: python -m archai_api.main
```

Studio (dashboard): `cd apps/web && npm ci && npm run dev` with the API on port 8000. Run `npm test` for the Studio unit tests; `npm run build` runs them first.

Install `.[ml,benchmark]` for real model/benchmark runs and `.[platform]` for SQLAlchemy/Alembic/Redis/Celery integrations. Core graph validation and serialization do not require PyTorch.

## Research workflow

1. Run `python scripts/smoke_search.py` for a deterministic, benchmark-free controller smoke test.
2. Install the benchmark extras and acquire only a checksummed dataset manifest; the acquisition command is `python scripts/acquire_dataset.py --manifest <verified-manifest.json> --destination /data/natsbench.pth`.
3. Run a matched-budget matrix from `research/experiments/` (see its README): `python scripts/run_experiment_matrix.py --config research/experiments/<name>.json --benchmark-path ... --benchmark-sha256 ... --output artifacts/experiments/<name>`; use `--dry-run` to inspect the plan without data.
4. Store raw metrics and provenance manifests; only then generate a report.

## Deploying

- Single host: copy `.env.example` to `.env`, then `docker compose --env-file .env -f infrastructure/docker/docker-compose.yml --profile worker up -d --build`.
- Production: set `ARCHAI_ENV=production`; the API refuses to boot with unsafe settings. Follow [docs/deploy/PRODUCTION.md](docs/deploy/PRODUCTION.md) (checklist and post-deploy checks) and [docs/deploy/ENV.md](docs/deploy/ENV.md) (every variable).
- Free hosted path (Render + Vercel + Neon + Upstash): [docs/deploy/HOSTING_RUNBOOK.md](docs/deploy/HOSTING_RUNBOOK.md).

See [ROADMAP.md](ROADMAP.md), [RESEARCH.md](RESEARCH.md), and [SECURITY.md](SECURITY.md).

Register a trained artifact with `python scripts/register_model.py --model-id ArchAI-Predictor --kind predictor --version v1 --artifact checkpoint.pt`; use [the model-card template](docs/MODEL_CARD_TEMPLATE.md) for release evidence.
