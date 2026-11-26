import pytest
from archai_shared.ratelimit import InProcessRateLimiter, RedisRateLimiter, make_rate_limiter
from fastapi.testclient import TestClient


class Clock:
    def __init__(self, now=1000.0):
        self.now = now

    def __call__(self):
        return self.now


class FakeRedis:
    """Minimal INCR/EXPIRE pipeline shared by several limiter instances (= API replicas)."""
    def __init__(self):
        self.values, self.expiry, self.fail = {}, {}, False

    def pipeline(self, transaction=True):
        return FakePipeline(self)


class FakePipeline:
    def __init__(self, parent):
        self.parent, self.commands = parent, []

    def incr(self, key):
        self.commands.append(("incr", key))

    def expire(self, key, seconds):
        self.commands.append(("expire", key, seconds))

    def execute(self):
        if self.parent.fail:
            raise ConnectionError("redis down")
        results = []
        for command in self.commands:
            if command[0] == "incr":
                self.parent.values[command[1]] = self.parent.values.get(command[1], 0) + 1
                results.append(self.parent.values[command[1]])
            else:
                self.parent.expiry[command[1]] = command[2]
                results.append(True)
        return results


def test_in_process_limiter_uses_sliding_window():
    clock = Clock()
    limiter = InProcessRateLimiter(60, clock=clock)
    assert [limiter.hit("a", 2).allowed for _ in range(3)] == [True, True, False]
    assert limiter.hit("b", 2).allowed is True  # independent clients
    clock.now += 60
    assert limiter.hit("a", 2).allowed is True


def test_redis_limiter_shares_budget_across_replicas_and_expires_keys():
    redis, clock = FakeRedis(), Clock(1200.0)
    first = RedisRateLimiter(redis, clock=clock)
    second = RedisRateLimiter(redis, clock=clock)
    assert first.hit("client", 3).allowed
    assert second.hit("client", 3).allowed
    assert first.hit("client", 3).allowed
    blocked = second.hit("client", 3)
    assert (blocked.allowed, blocked.count, blocked.backend) == (False, 4, "redis")
    assert set(redis.expiry.values()) == {120}
    clock.now += 60  # next fixed window
    assert first.hit("client", 3).allowed


def test_redis_limiter_degrades_to_in_process_instead_of_failing_open():
    redis = FakeRedis()
    redis.fail = True
    limiter = RedisRateLimiter(redis, fallback=InProcessRateLimiter(60, clock=Clock()))
    decisions = [limiter.hit("client", 1) for _ in range(2)]
    assert [d.allowed for d in decisions] == [True, False]
    assert {d.backend for d in decisions} == {"in_process_fallback"}
    assert "redis down" in limiter.last_error
    redis.fail = False
    assert limiter.hit("client", 1).backend == "redis"
    assert limiter.last_error is None


def test_factory_selects_backend(monkeypatch):
    monkeypatch.delenv("ARCHAI_RATE_LIMIT_REDIS_URL", raising=False)
    monkeypatch.delenv("ARCHAI_REDIS_URL", raising=False)
    assert isinstance(make_rate_limiter(), InProcessRateLimiter)
    pytest.importorskip("redis")
    assert isinstance(make_rate_limiter("redis://127.0.0.1:1/0"), RedisRateLimiter)


def test_api_uses_shared_limiter_and_reports_backend(monkeypatch):
    from archai_api import main as api_main
    redis = FakeRedis()
    monkeypatch.setattr(api_main, "_rate_limiter", RedisRateLimiter(redis))
    monkeypatch.setenv("ARCHAI_RATE_LIMIT_PER_MINUTE", "2")
    client = TestClient(api_main.app)
    assert client.get("/health").status_code == 200
    readiness = client.get("/readiness")
    assert readiness.json()["rate_limit_backend"] == "redis"
    blocked = client.get("/health")
    assert blocked.status_code == 429
    assert blocked.headers["x-ratelimit-backend"] == "redis"
