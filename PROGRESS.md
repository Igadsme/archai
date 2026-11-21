# ArchAI progress

Updated 2026-11-20.

## Verified in this checkout

- Foundation schemas validate unique, acyclic, reachable DAGs, reject duplicate edges, and reject incompatible fan-in channels.
- Compiler tests execute a real forward and backward pass when PyTorch is installed; compilation is topological-order independent and supports convolution, pooling, skip, none, and output nodes.
- Analytical metrics propagate upstream channel counts instead of assuming every operation reads the image input.
- Predictor training supports masked variable-size graph batches, Gaussian NLL uncertainty, deterministic hash-disjoint splits, checkpoint save/load, and MAE/RMSE/Spearman/Kendall/interval coverage metrics.
- Generator training supports a constrained valid-chain decoder, deterministic sampling, generation quality metrics, and checkpoint boundaries.
- Benchmark integration supports checksum-gated acquisition, NAS-Bench-201 encoding conversion, and an explicit query budget.
- Autonomous search control supports validation, deduplication, injected evaluation, atomic JSON persistence, cancellation requests, budget enforcement, and resume with an expanded budget.
- Training engine supports reproducible classification loops, gradient accumulation, optional AMP, early stopping, safe state-dict checkpoints, and resume.
- Provenance records and an append-only artifact store preserve evidence type and dataset/checkpoint/hardware/seed metadata.
- Local API registry supports architecture create/list/retrieve/validate with optional API-key protection for writes.
- First normalized PostgreSQL schema migration is present for users, credentials, datasets, architectures, checkpoints, searches, and experiments.
- Benchmark access now records architecture encodings, caches queries with a uniqueness constraint, and refuses acquisition until a verified checksum is supplied.
- API now exposes lifecycle surfaces for searches and provenance-backed experiments; local job transitions reject invalid terminal-state changes and worker start reports an explicit unconfigured-worker response.
- ArchAI Studio now has a responsive dark research dashboard shell, API health/registry reads, evidence-aware empty states, and container definitions for API/web/Postgres/Redis.
- Test suite: 22 passing tests.

## Evidence boundaries

No NATS-Bench archive, trained research checkpoint, benchmark table, GPU run, repeated-seed comparison, or deployment credential was available/configured during this pass. Therefore no scientific performance claim is made.

## Exact blockers

1. A real NATS-Bench/NATS-Bench-201 archive and its verified checksum are needed to run benchmark queries and train the predictor on real labels.
2. The full NAS-Bench-201 cell semantics require a dedicated compiler representation for operation-per-edge cells; the current canonical converter preserves the encoding as an explicit typed DAG for validation and metadata, while the research compiler supports the allowlisted tensor graph.
3. PostgreSQL, Redis, durable workers, authentication, and the complete frontend remain unimplemented.
4. Hugging Face publishing requires user-provided authorization and release decisions.
5. Frontend dependency installation hung without output in this environment; `next build` therefore could not run because the `next` binary was unavailable.

## Repository state

The supplied directory was not a Git repository; a local Git history was initialized for this continuation. The working tree remains directly inspectable under `/Volumes/PX4DRIVE/archai`.
