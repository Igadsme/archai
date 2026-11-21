# ArchAI progress

Updated 2026-11-21.

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
- The worker now has an explicit NATS-Bench random-search handler with mandatory archive SHA-256 verification, seeded indices, query budgets, validation-selected reporting, and held-out test recording; missing benchmark configuration fails the job instead of fabricating results.
- Experiment API records now support validated running/completed/failed/cancelled lifecycle transitions with persisted metrics and timestamps.
- API security now supports constant-time plaintext or SHA-256 key verification, Bearer authorization, and body-size enforcement even when clients omit `Content-Length`.
- Bounded search and experiment list endpoints now expose dashboard/operator history while preserving job-store status as the search authority.
- Compose deployment now wires API containers to PostgreSQL and Redis, installs the required platform/benchmark extras, and runs Alembic before serving.
- Alembic migration `0003_platform_metadata` now covers users, API credentials, datasets, and model-checkpoint metadata in the same SQLAlchemy metadata used by deployment.
- The model registry now selects the SQLAlchemy checkpoint table under `DATABASE_URL`, retaining SHA-256 manifests and the existing JSON fallback for local mode.
- Model checkpoints now retain a named `model_id` independent of model kind through Alembic migration `0004_model_identifiers`.
- Dataset registry endpoints now require a 64-character SHA-256 checksum and enforce immutable dataset versions in both local and SQLAlchemy-backed stores.
- Added a dataset acquisition CLI that refuses manifests without a checksum and atomically promotes only verified downloads.
- Added a database-aware model registration CLI with SHA-256 manifests and a model-card template for reproducibility evidence.
- ArchAI Studio now reads architecture, search, experiment, and dataset registries and renders live evidence/status counts with explicit unavailable/empty states.
- Readiness now probes configured database connectivity and supports an explicit `ARCHAI_REQUIRE_REDIS=1` gate for durable deployments.
- CI now installs the platform extra, verifies a fresh Alembic schema reaches `0004_model_identifiers`, and validates Docker Compose configuration without requiring live services.
- API CORS is now explicit and environment-configured, with local Studio origins enabled by default and preflight coverage.
- Generator checkpoint save/load is now verified with deterministic post-reload sampling, matching predictor checkpoint evidence.
- Generator CLI execution is now covered end-to-end from conditional JSONL corpus through checkpoint/report generation.
- Benchmark worker rejects unsupported algorithm names instead of silently recording them as random search.
- Worker status and search start now require a successful Redis ping; Compose enables `ARCHAI_REQUIRE_REDIS=1` for durable deployment truthfulness.
- Redis job serialization, queue claiming, handler execution, and result persistence now have a dependency-free fake-client integration test.
- The shared direct `run_job` path now persists handler results identically to `WorkerRunner`, preventing local execution from losing metrics or artifact references.
- Durable workers now expose an explicit candidate-training handler with reproducible synthetic smoke data, real compiler/training-engine execution, checkpoint output, and refusal to substitute synthetic data for undeclared real datasets.
- Durable workers now expose generator-training and predictor-training handlers; generator training is locally exercised from JSONL, while predictor training requires an explicit checksum-verified NATS-Bench archive and non-empty train/validation/test indices.
- Training-worker results now include SHA-256 hashes of produced checkpoints, making model artifact provenance independently verifiable.
- FastAPI now exposes validated training-job creation plus generic job listing, retrieval, and cancellation for the durable worker handlers.
- Queue status now returns explicit degraded availability and error details when the selected Redis backend cannot be listed.
- Local search persistence now records cancellation/status transitions consistently with the SQLAlchemy registry, with an API regression test covering the persisted state.
- API now enforces configurable request-size and per-client rate limits; the limiter is intentionally process-local until a gateway/Redis limiter is deployed.
- ArchAI Studio now has a responsive dark research dashboard shell, API health/registry reads, evidence-aware empty states, and container definitions for API/web/Postgres/Redis.
- ArchAI Studio now polls live registries/jobs, displays model and worker state, and provides a validated architecture graph inspector with node/edge details; frontend package compilation remains unverified because the local dependency tree is incomplete.
- Container images now include the ML runtime required by API/worker handlers, and the web image no longer assumes an untracked package-lock file; static Dockerfile contracts and Compose parsing are verified.
- Research evaluation utilities now compute deterministic bootstrap intervals, multi-seed summaries, search regret, and 2D accuracy/resource hypervolume.
- Model artifact registry now stores versioned model manifests with SHA-256 checksums and exposes read-only API listing.
- The model registry now also supports authenticated API registration with artifact existence checks, immutable model/version enforcement, and checksum-backed retrieval.
- Benchmark baseline now includes seeded random index traversal under the existing query budget abstraction.
- Benchmark search now also supports finite-pool NAS-Bench-201 regularized evolution, with operation-label mutation, validation-only selection, and worker/CLI coverage under the same query budget.
- Search acquisition now supports expected improvement, upper-confidence bounds, and uncertainty-aware candidate ranking.
- Closed-loop learned search now connects proposal batches, predictor uncertainty, acquisition ranking, evaluator evidence, budget limits, and Pareto trace extraction.
- Learned closed-loop search now atomically persists observations/deduplication state and supports cancellation plus explicit resume with an expanded budget.
- Persistent search now bounds repeated duplicate proposals and records an explicit `exhausted` terminal state instead of spinning indefinitely on a finite candidate pool.
- Search baselines now include parent-based regularized evolution mutations plus dependency-light Bayesian optimization with seeded warmup, kernel/UCB scoring, and finite-pool deduplication.
- Predictor comparisons now include mean and graph-feature ridge baselines.
- NAS-Bench semantics now treat `none` as a zero tensor during compilation rather than an identity operation.
- NAS-Bench-201 parsing now validates the canonical six-edge cell shape and marks converted graphs for dedicated sum fan-in compilation; the compiler verifies the numerical cell reduction.
- Test suite: 87 passing tests, 1 optional export test skipped when Safetensors is unavailable.

## Evidence boundaries

No NATS-Bench archive, trained research checkpoint, benchmark table, GPU run, repeated-seed comparison, or deployment credential was available/configured during this pass. Therefore no scientific performance claim is made.

## Exact blockers

1. A real NATS-Bench/NATS-Bench-201 archive and its verified checksum are needed to run benchmark queries and train the predictor on real labels.
2. PostgreSQL/Redis services and durable worker code are implemented but were not run as live services in this environment; production authentication and the complete frontend remain incomplete.
3. Hugging Face publishing requires user-provided authorization and release decisions.
4. Frontend dependency installation repeatedly hung or failed in this environment; `next build` therefore could not run because the pinned dependency tree was unavailable.

## Repository state

The supplied directory was not a Git repository; a local Git history was initialized for this continuation. The working tree remains directly inspectable under `/Volumes/PX4DRIVE/archai`.
