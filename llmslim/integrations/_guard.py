"""Rate limits and usage caps for integrations that spend a vendor credit.

Every integration that calls a paid API takes a :class:`UsageGuard`. The guard
is checked before each call and refuses it, without touching the network, when
the per-minute rate or the lifetime cap would be exceeded. Refusals raise
:class:`UsageLimitExceeded` subclasses; nothing waits or retries silently.

A guard is in-process state. It protects one process from runaway loops and
accidental fan-out; it is not a distributed quota. Hosted deployments that run
many processes keep using the MongoDB spend ledger in :mod:`llmslim.hosted`.
"""

from __future__ import annotations

import math
import os
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque, Dict, Mapping, Optional

__all__ = [
    "UsageLimitExceeded",
    "RateLimitExceeded",
    "UsageCapExceeded",
    "UsageLimits",
    "UsageReservation",
    "UsageGuard",
]

Clock = Callable[[], float]


class UsageLimitExceeded(RuntimeError):
    """A call was refused before reaching the vendor."""


class RateLimitExceeded(UsageLimitExceeded):
    """The per-minute request rate would be exceeded."""

    def __init__(self, message: str, retry_after_seconds: float) -> None:
        super().__init__(message)
        self.retry_after_seconds = retry_after_seconds


class UsageCapExceeded(UsageLimitExceeded):
    """The guard's lifetime request or unit cap would be exceeded."""


def _optional_positive_int(value: Optional[int], name: str) -> Optional[int]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{name} must be a positive integer or None")
    return value


def _optional_positive_float(value: Optional[float], name: str) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a positive number or None")
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise ValueError(f"{name} must be a positive number or None")
    return number


@dataclass(frozen=True)
class UsageLimits:
    """Limits for one guard. ``None`` disables that limit.

    ``max_units`` caps a vendor-specific quantity (characters, pages, rupees,
    credits); ``unit`` names it in error messages and snapshots.
    """

    requests_per_minute: Optional[int] = 60
    max_requests: Optional[int] = 1000
    max_units: Optional[float] = None
    unit: str = "units"

    def __post_init__(self) -> None:
        _optional_positive_int(self.requests_per_minute, "requests_per_minute")
        _optional_positive_int(self.max_requests, "max_requests")
        _optional_positive_float(self.max_units, "max_units")
        if not isinstance(self.unit, str) or not self.unit.strip():
            raise ValueError("unit must be a non-empty string")


@dataclass(frozen=True)
class UsageReservation:
    """Units reserved by :meth:`UsageGuard.acquire`; settle it with the actual amount."""

    units: float


def _env_number(env: Mapping[str, str], name: str, kind: type) -> Optional[Any]:
    raw = env.get(name)
    if raw is None or not raw.strip():
        return None
    text = raw.strip().lower()
    if text in {"none", "off", "unlimited"}:
        return "unset"
    try:
        return kind(text)
    except ValueError:
        raise ValueError(f"{name} must be a number, or 'none' to disable the limit") from None


class UsageGuard:
    """Thread-safe sliding-window rate limit plus lifetime request and unit caps."""

    def __init__(
        self,
        limits: Optional[UsageLimits] = None,
        *,
        name: str = "integration",
        clock: Optional[Clock] = None,
    ) -> None:
        self.limits = limits or UsageLimits()
        self.name = name
        self._clock: Clock = clock or time.monotonic
        self._lock = threading.Lock()
        self._window: Deque[float] = deque()
        self._requests = 0
        self._units = 0.0

    @classmethod
    def unlimited(cls, *, name: str = "integration") -> "UsageGuard":
        """A guard that never refuses; use only where the caller enforces its own limits."""

        return cls(
            UsageLimits(requests_per_minute=None, max_requests=None, max_units=None),
            name=name,
        )

    @classmethod
    def from_env(
        cls,
        prefix: str,
        defaults: Optional[UsageLimits] = None,
        *,
        env: Optional[Mapping[str, str]] = None,
        name: Optional[str] = None,
    ) -> "UsageGuard":
        """Build a guard from ``LLMSLIM_<PREFIX>_REQUESTS_PER_MINUTE``, ``_MAX_REQUESTS`` and
        ``_MAX_UNITS``. Missing variables keep ``defaults``; ``none`` disables a limit."""

        if not prefix or not prefix.replace("_", "").isalnum():
            raise ValueError("prefix must contain only letters, digits and underscores")
        source = os.environ if env is None else env
        base = defaults or UsageLimits()
        stem = f"LLMSLIM_{prefix.upper()}_"
        values: Dict[str, Any] = {
            "requests_per_minute": base.requests_per_minute,
            "max_requests": base.max_requests,
            "max_units": base.max_units,
        }
        for field, kind in (
            ("requests_per_minute", int),
            ("max_requests", int),
            ("max_units", float),
        ):
            parsed = _env_number(source, stem + field.upper(), kind)
            if parsed == "unset":
                values[field] = None
            elif parsed is not None:
                values[field] = parsed
        limits = UsageLimits(unit=base.unit, **values)
        return cls(limits, name=name or prefix.lower())

    def acquire(self, units: float = 0.0) -> UsageReservation:
        """Admit one request reserving ``units``, or raise without recording anything."""

        amount = _non_negative_units(units)
        with self._lock:
            now = self._clock()
            rpm = self.limits.requests_per_minute
            if rpm is not None:
                while self._window and now - self._window[0] >= 60.0:
                    self._window.popleft()
                if len(self._window) >= rpm:
                    retry_after = max(0.0, 60.0 - (now - self._window[0]))
                    raise RateLimitExceeded(
                        f"{self.name}: rate limit of {rpm} requests per minute reached; "
                        f"retry in {retry_after:.1f}s",
                        retry_after,
                    )
            cap = self.limits.max_requests
            if cap is not None and self._requests >= cap:
                raise UsageCapExceeded(f"{self.name}: request cap of {cap} reached")
            unit_cap = self.limits.max_units
            if unit_cap is not None and self._units + amount > unit_cap + 1e-9:
                raise UsageCapExceeded(
                    f"{self.name}: usage cap of {unit_cap:g} {self.limits.unit} reached "
                    f"({self._units:g} used, {amount:g} requested)"
                )
            if rpm is not None:
                self._window.append(now)
            self._requests += 1
            self._units += amount
        return UsageReservation(amount)

    def settle(self, reservation: UsageReservation, actual_units: float) -> None:
        """Replace a reservation's estimate with the amount the vendor reported."""

        actual = _non_negative_units(actual_units)
        with self._lock:
            self._units = max(0.0, self._units - reservation.units + actual)

    def release(self, reservation: UsageReservation) -> None:
        """Return a reservation's units after a call that the vendor did not bill.

        The request itself still counts toward the rate and request cap, so a
        failing endpoint cannot be hammered.
        """

        self.settle(reservation, 0.0)

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            now = self._clock()
            recent = sum(1 for stamp in self._window if now - stamp < 60.0)
            return {
                "name": self.name,
                "requests": self._requests,
                "requests_last_minute": recent,
                "units": round(self._units, 6),
                "unit": self.limits.unit,
                "limits": {
                    "requests_per_minute": self.limits.requests_per_minute,
                    "max_requests": self.limits.max_requests,
                    "max_units": self.limits.max_units,
                },
            }

    def __repr__(self) -> str:
        return f"UsageGuard(name={self.name!r}, limits={self.limits!r})"


def _non_negative_units(value: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("units must be a non-negative number")
    number = float(value)
    if not math.isfinite(number) or number < 0:
        raise ValueError("units must be a non-negative number")
    return number
