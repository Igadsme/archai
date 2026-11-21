# ArchAI progress

Updated 2026-11-20.

## Verified in this checkout

- Foundation schemas validate unique, acyclic, reachable DAGs, reject duplicate edges, reject incompatible fan-in channels, and enforce typed identity/input/output metadata.
- Compiler tests execute a real forward and backward pass when PyTorch is installed; compilation is topological-order independent and supports convolution, pooling, skip, none, and output nodes.
- Compiler exports canonical architecture JSON, state-dict fingerprints, dependency-gated Safetensors, and an ONNX export hook.
- Analytical metrics propagate upstream channel counts instead of assuming every operation reads the image input.
- Predictor training supports edge-aware message passing, a seeded ArchitectureDataset/DataLoader, masked variable-size graph batches, Gaussian NLL uncertainty, duplicate-safe architecture-hash splits, checkpoint save/load, MAE/RMSE/Spearman/Kendall/interval coverage, calibration error, and embedding OOD scores.
- Generator training supports a constrained valid-chain autoregressive decoder, teacher forcing, task/constraint condition vectors, deterministic token-by-token sampling, generation quality metrics, checkpoint boundaries, and a JSONL-corpus CLI.
- Benchmark integration supports checksum-gated acquisition, NAS-Bench-201 encoding conversion, and an explicit query budget.
- Autonomous search control supports validation, deduplication, injected evaluation, atomic JSON persistence, cancellation requests, budget enforcement, and resume with an expanded budget.
- Training engine supports reproducible classification loops, gradient accumulation, optional AMP, early stopping, safe state-dict checkpoints, and resume.
- Candidate training now compiles a canonical architecture into PyTorch and runs it through the training engine; CIFAR-10/CIFAR-100 adapters require explicit download opt-in.
- Provenance records and an append-only artifact store preserve evidence type and dataset/checkpoint/hardware/seed metadata.
- Local API registry supports architecture create/list/retrieve/validate with optional API-key protection for writes.
- Job infrastructure now includes a Redis adapter, local state adapter, legal transitions, queue claim, and terminal failure capture for worker handlers.
- Added a real NATS-Bench predictor training CLI that requires explicit archive/index inputs and writes checkpoint/report provenance with test-leakage metadata.
- Added `scripts/run_benchmark_search.py` for seeded, budgeted random search that selects on validation accuracy and reports held-out test accuracy separately.
- Added `scripts/build_report.py` and leakage-aware research reporting that aggregates repeated seeds with confidence intervals and rejects test-selected runs.
- First normalized PostgreSQL schema migration is present for users, credentials, datasets, architectures, checkpoints, searches, and experiments.
- SQLAlchemy model factories and Alembic environment/initial migration now correspond to the core architecture, search-session, and experiment tables while remaining lazy-imported locally.
- Benchmark access now records architecture encodings, caches queries with a uniqueness constraint, and refuses acquisition until a verified checksum is supplied.
- API now exposes lifecycle surfaces for searches and provenance-backed experiments; local job transitions reject invalid terminal-state changes and worker start reports an explicit unconfigured-worker response.
- API now exposes readiness, worker, and queue status endpoints; documented `x-api-key` enforcement is tested, and Redis status reflects the actual selected backend plus connectivity ping.
- API architecture comparison and model metadata retrieval routes are now covered, with static-route ordering fixed so `/compare` is not shadowed by the dynamic architecture route.
- API generator inference now loads a registered-format checkpoint when `ARCHAI_GENERATOR_CHECKPOINT` is configured, samples the requested number of seeded candidates, and returns canonical architecture IDs; the unconfigured path remains an explicit `503`.
- Search API status and cancellation now read and update the authoritative job-store state instead of maintaining a divergent in-memory status.
- The architecture registry now has a SQLAlchemy-backed implementation selected by `DATABASE_URL`, with canonical-document hash verification on reads and an SQLite round-trip test; process-local storage remains the explicit default.
- Search configurations and evidence-aware experiment records now persist through SQLAlchemy when `DATABASE_URL` is configured; migration `0002_experiment_provenance` preserves provenance and lifecycle timestamps.
- Durable worker infrastructure now has an atomic local claim path, Redis claim/execute loop, explicit handler registration, terminal failure capture for unsupported kinds, and a container entry point; the API only accepts search starts when Redis is selected.
- API now enforces configurable request-size and per-client rate limits; the limiter is intentionally process-local until a gateway/Redis limiter is deployed.
- ArchAI Studio now has a responsive dark research dashboard shell, API health/registry reads, evidence-aware empty states, and container definitions for API/web/Postgres/Redis.
- Research evaluation utilities now compute deterministic bootstrap intervals, multi-seed summaries, search regret, and 2D accuracy/resource hypervolume.
- Model artifact registry now stores versioned model manifests with SHA-256 checksums and exposes read-only API listing.
- Benchmark baseline now includes seeded random index traversal under the existing query budget abstraction.
- Search acquisition now supports expected improvement, upper-confidence bounds, and uncertainty-aware candidate ranking.
- Closed-loop learned search now connects proposal batches, predictor uncertainty, acquisition ranking, evaluator evidence, budget limits, and Pareto trace extraction.
- Search baselines now include parent-based regularized evolution mutations plus dependency-light Bayesian optimization with seeded warmup, kernel/UCB scoring, and finite-pool deduplication.
- Predictor comparisons now include mean and graph-feature ridge baselines.
- NAS-Bench semantics now treat `none` as a zero tensor during compilation rather than an identity operation.
- Test suite: 53 passing tests, 1 optional export test skipped when Safetensors is unavailable.

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
