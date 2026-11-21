"""Durable worker entry point for the API job queue."""
from __future__ import annotations

import os

from archai_shared.jobs import RedisJobStore
from archai_shared.worker import WorkerRunner


def main() -> int:
    url = os.getenv("ARCHAI_REDIS_URL")
    if not url:
        raise SystemExit("ARCHAI_REDIS_URL is required for the durable worker")
    store = RedisJobStore.from_url(url)
    store.client.ping()
    # Search/training handlers are injected by the deployed experiment service.
    # The generic worker still records unsupported kinds as terminal failures.
    WorkerRunner(store, {}).run_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
