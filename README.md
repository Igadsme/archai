# ArchAI — AI That Designs AI

ArchAI is a research platform for constrained neural architecture search. The initial implementation targets the NAS-Bench-201/NATS-Bench cell search space and keeps analytical metrics, learned predictions, benchmark lookups, and real training results separate.

## Current evidence status

This repository contains an executable research foundation: a typed architecture schema, strict validation, deterministic hashing, a restricted PyTorch compiler, graph encoder models, budget-aware search policies, and an API surface. No model checkpoint or benchmark result is claimed by this repository until a user runs the documented experiments and stores the resulting provenance manifest.

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
pytest
python -m archai.apps.api.main
```

Install `.[ml,benchmark]` for real model/benchmark runs and `.[platform]` for SQLAlchemy/Alembic/Redis/Celery integrations. Core graph validation and serialization do not require PyTorch.

## Research workflow

1. Run `python scripts/smoke_search.py` for a deterministic, benchmark-free controller smoke test.
2. Install the benchmark extras and place checksummed benchmark data under the configured artifact directory.
3. Run the experiment configs under `research/experiments/` with multiple seeds.
4. Store raw metrics and provenance manifests; only then generate a report.

See [ROADMAP.md](ROADMAP.md), [RESEARCH.md](RESEARCH.md), and [SECURITY.md](SECURITY.md).
