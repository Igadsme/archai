# Local hosting (macOS)

One command starts the whole stack in Docker: Postgres, Redis, database migrations, the API, the worker and the Studio. Data persists in Docker volumes across restarts.

## Requirements

- **Docker Desktop** 4.30 or newer (Apple Silicon or Intel), running. Under Settings > Resources give it at least 4 CPUs and 6 GB of memory; the first image build needs the memory.
- **python3**, which macOS provides through the Xcode command line tools (`xcode-select --install`). The setup script uses only the standard library.
- About 6 GB of free disk for images and volumes.

The repository can live on an external drive. Docker Desktop shares `/Volumes` by default (Settings > Resources > File sharing), and `.dockerignore` excludes the `._*` AppleDouble files that exFAT drives create.

## Start

```bash
cd /Volumes/PX4DRIVE/archai
git checkout main && git pull origin main
scripts/local/archai.sh up
```

On the first run `up`:

1. Creates `.env` from `.env.example` with a random Postgres password and a new bootstrap API key, through `scripts/local/init_env.py`. The key goes to `.archai/bootstrap-api-key` (mode 0600, git-ignored), and `.env` holds only its SHA-256. Nothing secret is printed.
2. Builds the API and Studio images. The first build downloads about 1.5 GB and takes 5–15 minutes; later runs are cached.
3. Starts Postgres and Redis, runs `alembic upgrade head` in the one-shot `migrate` service, and trains the small CPU generator checkpoint once (about 10–60 s) in the one-shot `generator-init` service. See `docs/GENERATOR.md`.
4. Starts the API, worker and Studio, and waits until the API reports ready (Postgres and Redis reachable).

Then open the Studio and enter the key:

```bash
open http://localhost:3000
pbcopy < .archai/bootstrap-api-key   # paste into the sidebar's API KEY field
```

| What | URL |
| --- | --- |
| Studio | http://localhost:3000 |
| API | http://localhost:8000 |
| API reference (OpenAPI) | http://localhost:8000/docs |

The bootstrap key is an admin key. Under **System > Users & API keys**, create personal users and scoped keys (read, write, admin) for day-to-day use; keys can be rotated and revoked there.

## Check it

```bash
scripts/local/archai.sh smoke    # health, readiness, auth, worker heartbeat, generator, Studio
scripts/local/archai.sh status   # container state and /readiness
scripts/local/archai.sh logs api # or worker, web, postgres, redis, migrate, generator-init
```

## Stop, upgrade, reset

```bash
scripts/local/archai.sh down                            # stop; data is kept
git pull origin main && scripts/local/archai.sh up      # upgrade; migrations run automatically
scripts/local/archai.sh reset                           # delete all local data volumes (asks first)
python3 scripts/local/init_env.py --rotate-key && scripts/local/archai.sh up   # new bootstrap key
```

Back up the database with:

```bash
docker compose --env-file .env -f infrastructure/docker/docker-compose.yml exec -T postgres \
  pg_dump -U archai archai > archai-$(date +%F).sql
```

## Configuration

Edit `.env`, then run `scripts/local/archai.sh up` again. Full reference: `docs/deploy/ENV.md`.

- **Ports.** Set `ARCHAI_WEB_PORT` and `ARCHAI_API_PORT`. If you change the API port, also set `ARCHAI_PUBLIC_API_URL=http://localhost:<port>`; `up` rebuilds the Studio, which has the URL built in. The ports bind to `127.0.0.1` only; set `ARCHAI_BIND_ADDRESS=0.0.0.0` to reach the stack from other machines on your network, and add their origins to `ARCHAI_CORS_ORIGINS`.
- **Generator.** `ARCHAI_TRAIN_GENERATOR=0` skips the first-boot training, so generation answers 503 (unavailable). To use your own checkpoint, put it in the artifact volume and set `ARCHAI_GENERATOR_CHECKPOINT`.
- **Benchmark searches.** The worker starts with the bundled 256-cell NATS-Bench TSS fixture (`datasets/fixtures/natsbench-tss-cifar10-256`). It is fixture-only: good for trying the Search Laboratory, not for research claims. For real searches, download the full archive as described in `docs/deploy/KAGGLE_RUNBOOK.md` (section 1), place it under `datasets/raw/` (mounted read-only at `/var/lib/archai/datasets`), and set `ARCHAI_NATS_BENCH_PATH=/var/lib/archai/datasets/<file>` plus `ARCHAI_NATS_BENCH_SHA256`.

## What runs where

- **No GPU in Docker on a Mac.** Docker Desktop cannot pass the Apple GPU (Metal/MPS) or any CUDA device into Linux containers. The Training and System screens therefore report "No GPU" with the reason, and training and latency measurements run on the container's CPUs. GPU training uses the Kaggle runbook, or a Linux host with an NVIDIA GPU and the image built with `TORCH_INDEX_URL=https://download.pytorch.org/whl/cu124`.
- **Deployments** (Registry > Deployments) serve models from the API container, on CPU.
- **Apple Silicon** runs the native `linux/arm64` images; PyTorch publishes CPU wheels for it.

## Troubleshooting

- **`Docker is installed but not running`:** start Docker Desktop and wait for the whale icon to settle.
- **`port is already allocated`:** another process holds 3000 or 8000. Change `ARCHAI_WEB_PORT` / `ARCHAI_API_PORT` (see Configuration above), or find the process with `lsof -i :3000`.
- **The build is killed or very slow:** raise Docker Desktop's memory limit to 6–8 GB.
- **`up` times out waiting:** run `scripts/local/archai.sh logs migrate generator-init api`. The wait limit is `ARCHAI_WAIT_TIMEOUT` (default 900 s).
- **The Studio says "invalid API key":** paste the contents of `.archai/bootstrap-api-key`, not its path. Run `scripts/local/archai.sh key` to see the path.
