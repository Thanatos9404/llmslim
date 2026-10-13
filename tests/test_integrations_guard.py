"""UsageGuard: the shared rate limit and usage cap for paid integrations."""

from __future__ import annotations

import threading

import pytest

from llmslim.integrations._guard import (
    RateLimitExceeded,
    UsageCapExceeded,
    UsageGuard,
    UsageLimitExceeded,
    UsageLimits,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def test_rate_limit_refuses_then_recovers_after_the_window() -> None:
    clock = FakeClock()
    guard = UsageGuard(UsageLimits(requests_per_minute=2, max_requests=None), clock=clock)
    guard.acquire()
    clock.now += 10
    guard.acquire()
    with pytest.raises(RateLimitExceeded) as info:
        guard.acquire()
    assert info.value.retry_after_seconds == pytest.approx(50.0)
    assert guard.snapshot()["requests"] == 2  # the refused call is not recorded
    clock.now += 50
    guard.acquire()  # the first stamp left the window
    assert guard.snapshot()["requests_last_minute"] == 2


def test_request_cap_is_a_lifetime_cap() -> None:
    clock = FakeClock()
    guard = UsageGuard(UsageLimits(requests_per_minute=None, max_requests=3), clock=clock)
    for _ in range(3):
        guard.acquire()
        clock.now += 3600
    with pytest.raises(UsageCapExceeded, match="request cap of 3"):
        guard.acquire()


def test_unit_cap_reserve_settle_and_release() -> None:
    guard = UsageGuard(
        UsageLimits(requests_per_minute=None, max_requests=None, max_units=10, unit="pages")
    )
    first = guard.acquire(6)
    with pytest.raises(UsageCapExceeded, match="10 pages"):
        guard.acquire(5)
    guard.settle(first, 2)  # vendor billed less than the estimate
    second = guard.acquire(8)
    assert guard.snapshot()["units"] == pytest.approx(10)
    guard.release(second)  # failed call, not billed
    assert guard.snapshot()["units"] == pytest.approx(2)
    assert guard.snapshot()["requests"] == 2


def test_exact_cap_is_allowed() -> None:
    guard = UsageGuard(UsageLimits(requests_per_minute=None, max_requests=None, max_units=1.5))
    guard.acquire(1.0)
    guard.acquire(0.5)
    with pytest.raises(UsageCapExceeded):
        guard.acquire(0.01)


@pytest.mark.parametrize("bad", [-1, float("nan"), float("inf"), True, "3"])
def test_invalid_units_are_rejected(bad: object) -> None:
    guard = UsageGuard()
    with pytest.raises(ValueError):
        guard.acquire(bad)  # type: ignore[arg-type]
    assert guard.snapshot()["requests"] == 0


@pytest.mark.parametrize(
    "kwargs",
    [
        {"requests_per_minute": 0},
        {"max_requests": -2},
        {"max_requests": True},
        {"max_units": 0},
        {"max_units": float("nan")},
        {"max_units": True},
        {"unit": " "},
    ],
)
def test_invalid_limits_are_rejected(kwargs: dict) -> None:
    with pytest.raises(ValueError):
        UsageLimits(**kwargs)


def test_unlimited_never_refuses() -> None:
    guard = UsageGuard.unlimited(name="x")
    for _ in range(5000):
        guard.acquire(1e9)
    assert guard.snapshot()["requests"] == 5000


def test_from_env_overrides_and_disables() -> None:
    env = {
        "LLMSLIM_EXA_REQUESTS_PER_MINUTE": "5",
        "LLMSLIM_EXA_MAX_REQUESTS": "none",
        "LLMSLIM_EXA_MAX_UNITS": "2.5",
    }
    guard = UsageGuard.from_env("exa", UsageLimits(max_requests=9, unit="usd"), env=env)
    assert guard.limits == UsageLimits(
        requests_per_minute=5, max_requests=None, max_units=2.5, unit="usd"
    )
    assert guard.name == "exa"


def test_from_env_keeps_defaults_and_rejects_garbage() -> None:
    defaults = UsageLimits(requests_per_minute=7, max_requests=8)
    assert UsageGuard.from_env("example", defaults, env={}).limits == defaults
    with pytest.raises(ValueError, match="LLMSLIM_EXAMPLE_MAX_REQUESTS"):
        UsageGuard.from_env("example", defaults, env={"LLMSLIM_EXAMPLE_MAX_REQUESTS": "lots"})
    with pytest.raises(ValueError):
        UsageGuard.from_env("bad-prefix", defaults, env={})
    with pytest.raises(ValueError):
        UsageGuard.from_env("example", defaults, env={"LLMSLIM_EXAMPLE_MAX_REQUESTS": "0"})


def test_concurrent_acquire_never_exceeds_the_cap() -> None:
    guard = UsageGuard(UsageLimits(requests_per_minute=None, max_requests=50))
    admitted = []
    refused = []

    def worker() -> None:
        for _ in range(20):
            try:
                guard.acquire()
                admitted.append(1)
            except UsageLimitExceeded:
                refused.append(1)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(admitted) == 50
    assert len(refused) == 110


def test_repr_has_no_state_secrets() -> None:
    assert "UsageGuard(name='sarvam'" in repr(UsageGuard(name="sarvam"))
