"""Opt-in checks against real local services; skipped unless the URLs are provided.

    ARCHAI_LIVE_REDIS_URL=redis://127.0.0.1:6379/15 \
    ARCHAI_LIVE_DATABASE_URL=postgresql+psycopg://archai@127.0.0.1:5433/archai pytest tests/test_live_services.py
"""
import os
import uuid

import pytest

REDIS_URL = os.getenv("ARCHAI_LIVE_REDIS_URL")
DATABASE_URL = os.getenv("ARCHAI_LIVE_DATABASE_URL")


@pytest.mark.skipif(not REDIS_URL, reason="ARCHAI_LIVE_REDIS_URL not set")
def test_real_redis_rate_limit_is_shared_between_limiters():
    from archai_shared.ratelimit import RedisRateLimiter, make_rate_limiter
    first, second = make_rate_limiter(REDIS_URL), make_rate_limiter(REDIS_URL)
    assert isinstance(first, RedisRateLimiter)
    key = f"live-{uuid.uuid4().hex}"
    assert first.hit(key, 2).allowed and second.hit(key, 2).allowed
    blocked = first.hit(key, 2)
    assert (blocked.allowed, blocked.backend) == (False, "redis")


@pytest.mark.skipif(not REDIS_URL, reason="ARCHAI_LIVE_REDIS_URL not set")
def test_real_redis_job_round_trip():
    from archai_shared.jobs import RedisJobStore
    from archai_shared.worker import WorkerRunner
    store = RedisJobStore.from_url(REDIS_URL, prefix=f"archai-live-{uuid.uuid4().hex[:8]}")
    job = store.create("training", {"value": 3})
    runner = WorkerRunner(store, {"training": lambda item: {"doubled": item.payload["value"] * 2}},
                          worker_id="live-test")
    assert runner.run_once().status == "succeeded"
    assert store.get(job.job_id).payload["result"] == {"doubled": 6}


@pytest.mark.skipif(not DATABASE_URL, reason="ARCHAI_LIVE_DATABASE_URL not set")
def test_real_postgres_dataset_registry_is_immutable():
    from archai_api.db import SqlAlchemyDatasetStore
    store = SqlAlchemyDatasetStore.from_url(DATABASE_URL)
    dataset_id = f"live-{uuid.uuid4().hex[:8]}"
    stored = store.put(dataset_id=dataset_id, version="1", checksum="a" * 64, uri="file:///tmp/x")
    assert store.get(dataset_id, "1")["checksum"] == stored["checksum"]
    with pytest.raises(ValueError):
        store.put(dataset_id=dataset_id, version="1", checksum="b" * 64, uri="file:///tmp/x")
