import pytest


@pytest.fixture(autouse=True)
def _generous_rate_limits(monkeypatch):
    """The suite shares one in-process limiter bucket; tests that check limits set their own."""
    monkeypatch.setenv("ARCHAI_RATE_LIMIT_PER_MINUTE", "100000")
    monkeypatch.setenv("ARCHAI_RATE_LIMIT_GET_PER_MINUTE", "100000")
