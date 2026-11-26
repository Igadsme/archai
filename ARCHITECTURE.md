# ArchAI architecture

ArchAI is a monorepo. Python packages live under `packages/`, apps under `apps/`. Packages depend inward
on `archai_core` and never import the API.

| Layer | Package / app | Responsibility |
| --- | --- | --- |
| Schema | `packages/architecture-core` (`archai_core`) | Typed `Architecture` DAG, strict validation (acyclic, reachable, typed fan-in), canonical JSON + content hash |
| Compiler | `packages/architecture-compiler` (`archai_compiler`) | Allowlisted ops → PyTorch modules, analytical metrics, safetensors/ONNX export |
| Search | `packages/search-engine` (`archai_search`) | Random, regularized evolution, Bayesian, learned closed-loop search; acquisition (EI/UCB); Pareto; persistent controller with cancel/resume |
| Predictor | `packages/performance-predictor` (`archai_predictor`) | Graph message-passing predictor with Gaussian uncertainty, baselines, calibration/OOD metrics |
| Generator | `packages/graph-generator` (`archai_generator`) | Constrained conditional autoregressive generator, checkpoints |
| Benchmark | `packages/benchmark-engine` (`archai_benchmark`) | Checksum-gated acquisition, NATS-Bench adapter, query budget + cache, index search policies, research metrics and leakage-aware reports |
| Training | `packages/training-engine` (`archai_training`) | Reproducible training loop, AMP, early stopping, safe checkpoints, CIFAR adapters (opt-in download) |
| Shared | `packages/shared-schemas` (`archai_shared`) | Provenance records, artifact store, model registry, job stores (memory/Redis), worker runner, allowed-path policy, rate limiter |
| API | `apps/api` (`archai_api`) | FastAPI: registries, searches, training jobs, experiments, models, datasets, infrastructure status; SQLAlchemy/Alembic persistence; durable Redis worker |
| Studio | `apps/web` | Next.js dashboard over the API |
| Space | `apps/huggingface-space` | Status-only Hugging Face Space (verifies configured artifact hashes) |
| Scripts | `scripts/` | CLIs: acquisition, benchmark search, experiment matrix, predictor/generator training, report building, model registration |

## Data flow

1. Datasets/benchmarks are registered with a SHA-256 checksum (`/v1/datasets`, `scripts/acquire_dataset.py`).
2. Searches and training are queued as jobs (`/v1/searches`, `/v1/training`). The Redis worker
   (`archai_api.worker`) claims them, verifies benchmark checksums, and runs them.
3. Results are written as provenance-bearing experiment records (`predicted`, `benchmark_lookup`,
   `measured_training`). Selection uses validation metrics only; test metrics are reported separately.
4. `scripts/run_experiment_matrix.py` and `scripts/build_report.py` aggregate repeated seeds into
   matched-budget reports with bootstrap intervals.

## Persistence and operations

- Local mode keeps registries in process. `DATABASE_URL` switches to SQLAlchemy (Alembic head
  `0006_experiment_started_at`). `ARCHAI_REDIS_URL` enables the durable queue, worker heartbeats and
  shared rate limits.
- Security controls: API key (plaintext or SHA-256), body-size limits, rate limits, CORS allowlist,
  allowed-path policy, and a JSONL audit log of write requests.
- Containers: `infrastructure/docker/docker-compose.yml` (api, worker, web, postgres, redis).
