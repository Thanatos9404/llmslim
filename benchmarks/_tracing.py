"""Opt-in LangSmith tracing for benchmark reader calls. Benchmarks only.

Tracing is off unless both ``LLMSLIM_LANGSMITH_TRACING=1`` and
``LANGSMITH_API_KEY`` are set. When on, each reader call (inputs, answer,
provider-reported tokens, cost and latency) is recorded as one ``llm`` run in
the LangSmith project ``LANGSMITH_PROJECT`` (default ``llmslim-benchmarks``).

- The ``langsmith`` SDK is used when it imports; otherwise the REST API is
  called over ``httpx``. If neither works, tracing becomes a no-op after one
  warning; a benchmark never fails because tracing failed.
- Only datasets explicitly marked public are traced: either the dataset JSON
  has ``"public": true`` at the top level, or its repository path and SHA-256
  are listed in :data:`PUBLIC_DATASETS`. Asking to trace anything else raises
  :class:`TracingRefused` before any reader call is made.
- Every post goes through ``UsageGuard.from_env("langsmith", ...)``; a refused
  post is dropped (with one warning), never queued.

This module lives under ``benchmarks/`` and must never be imported by the
``llmslim`` library.
"""

from __future__ import annotations

import hashlib
import json
import os
import uuid
import warnings
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

from llmslim.integrations._guard import (
    UsageCapExceeded,
    UsageGuard,
    UsageLimitExceeded,
    UsageLimits,
)

ROOT = Path(__file__).resolve().parents[1]

ENABLE_ENV = "LLMSLIM_LANGSMITH_TRACING"
API_KEY_ENV = "LANGSMITH_API_KEY"
PROJECT_ENV = "LANGSMITH_PROJECT"
ENDPOINT_ENV = "LANGSMITH_ENDPOINT"
DEFAULT_PROJECT = "llmslim-benchmarks"
DEFAULT_ENDPOINT = "https://api.smith.langchain.com"
GUARD_DEFAULTS = UsageLimits(requests_per_minute=120, max_requests=5000)

#: Datasets cleared for third-party tracing: committed to this public repository,
#: synthetic, no personal data. The hash pins the reviewed content; an edited file
#: is not public until it is reviewed and the hash is updated here.
PUBLIC_DATASETS: Dict[str, str] = {
    "benchmarks/datasets/v06_context_planning.json": (
        "2cb35850b8eab2026a849c6451b24864f1dc22aee98c69d277c9e085ac820deb"
    ),
}


class TracingRefused(RuntimeError):
    """Tracing was requested for a dataset that is not marked public."""


def dataset_sha256(path: Union[str, Path]) -> str:
    """SHA-256 of a dataset with line endings normalized to LF (Windows checkouts use CRLF)."""

    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def is_public_dataset(path: Union[str, Path]) -> bool:
    """True only for a dataset explicitly marked public (flag in the file, or pinned here)."""

    dataset = Path(path).resolve()
    try:
        payload = json.loads(dataset.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    if isinstance(payload, dict) and payload.get("public") is True:
        return True
    try:
        relative = dataset.relative_to(ROOT).as_posix()
    except ValueError:
        return False
    pinned = PUBLIC_DATASETS.get(relative)
    return pinned is not None and pinned == dataset_sha256(dataset)


def _isoformat(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).isoformat()


class BenchmarkTracer:
    """Records benchmark reader calls to LangSmith when explicitly enabled; otherwise does nothing."""

    def __init__(
        self,
        *,
        enabled: bool,
        api_key: Optional[str] = None,
        project: str = DEFAULT_PROJECT,
        endpoint: str = DEFAULT_ENDPOINT,
        guard: Optional[UsageGuard] = None,
        backend: Optional[Any] = None,
        http_transport: Optional[Any] = None,
    ) -> None:
        self.enabled = bool(enabled and api_key)
        self.project = project
        self.endpoint = endpoint.rstrip("/")
        if guard is None and self.enabled:
            guard = UsageGuard.from_env("langsmith", GUARD_DEFAULTS)
        self.guard = guard
        self.recorded = 0
        self.dropped = 0
        self._api_key = api_key
        self._backend = backend
        self._http_transport = http_transport
        self._warned = False

    @classmethod
    def from_env(
        cls,
        *,
        dataset_public: bool,
        env: Optional[Mapping[str, str]] = None,
        guard: Optional[UsageGuard] = None,
        http_transport: Optional[Any] = None,
    ) -> "BenchmarkTracer":
        """Build a tracer from the environment; refuse non-public datasets when tracing is on."""

        source = os.environ if env is None else env
        api_key = source.get(API_KEY_ENV) or None
        enabled = source.get(ENABLE_ENV) == "1" and api_key is not None
        if enabled and not dataset_public:
            raise TracingRefused(
                "LangSmith tracing is enabled but the dataset is not marked public; "
                "unset LLMSLIM_LANGSMITH_TRACING or mark the dataset public after review"
            )
        if guard is None and enabled:
            guard = UsageGuard.from_env("langsmith", GUARD_DEFAULTS, env=source)
        return cls(
            enabled=enabled,
            api_key=api_key,
            project=source.get(PROJECT_ENV) or DEFAULT_PROJECT,
            endpoint=source.get(ENDPOINT_ENV) or DEFAULT_ENDPOINT,
            guard=guard,
            http_transport=http_transport,
        )

    def _warn_once(self, message: str) -> None:
        if not self._warned:
            self._warned = True
            warnings.warn(message, RuntimeWarning, stacklevel=3)

    def _disable(self, message: str) -> None:
        self.enabled = False
        self._warn_once(message)

    def _resolve_backend(self) -> Optional[Any]:
        if self._backend is not None:
            return self._backend
        try:
            from langsmith import Client
        except Exception:
            Client = None
        if Client is not None:
            kwargs: Dict[str, Any] = {"api_key": self._api_key, "api_url": self.endpoint}
            try:
                self._backend = _SdkBackend(Client(auto_batch_tracing=False, **kwargs))
            except TypeError:
                self._backend = _SdkBackend(Client(**kwargs))
            except Exception:
                self._backend = None
            if self._backend is not None:
                return self._backend
        try:
            import httpx
        except Exception:
            return None
        self._backend = _RestBackend(
            httpx.Client(
                base_url=self.endpoint,
                headers={"x-api-key": str(self._api_key)},
                timeout=10.0,
                transport=self._http_transport,
            )
        )
        return self._backend

    def record_reader_call(
        self,
        *,
        name: str,
        inputs: Mapping[str, Any],
        outputs: Mapping[str, Any],
        prompt_tokens: Optional[int],
        completion_tokens: Optional[int],
        cost: Optional[float],
        currency: str,
        latency_ms: float,
        metadata: Optional[Mapping[str, Any]] = None,
        error: Optional[str] = None,
    ) -> bool:
        """Record one reader call. Returns True when the run was sent, False otherwise."""

        if not self.enabled:
            return False
        backend = self._resolve_backend()
        if backend is None:
            self._disable(
                "LangSmith tracing disabled: neither the langsmith SDK nor httpx is available"
            )
            return False
        try:
            if self.guard is not None:
                self.guard.acquire()
        except UsageCapExceeded as exc:
            self.dropped += 1
            self._disable(f"LangSmith tracing stopped: {exc}")
            return False
        except UsageLimitExceeded as exc:
            self.dropped += 1
            self._warn_once(f"LangSmith trace dropped: {exc}")
            return False
        end = datetime.now(timezone.utc)
        start = end - timedelta(milliseconds=max(0.0, float(latency_ms)))
        usage: Dict[str, Any] = {}
        if prompt_tokens is not None:
            usage["input_tokens"] = int(prompt_tokens)
        if completion_tokens is not None:
            usage["output_tokens"] = int(completion_tokens)
        if prompt_tokens is not None and completion_tokens is not None:
            usage["total_tokens"] = int(prompt_tokens) + int(completion_tokens)
        if cost is not None:
            usage["total_cost"] = float(cost)
        run_metadata = dict(metadata or {})
        run_metadata.update(
            {
                "cost": cost,
                "currency": currency,
                "latency_ms": round(float(latency_ms), 3),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }
        )
        run_outputs = dict(outputs)
        if usage:
            run_outputs["usage_metadata"] = usage
        run_id = uuid.uuid4()
        run = {
            "id": str(run_id),
            "trace_id": str(run_id),
            "dotted_order": start.strftime("%Y%m%dT%H%M%S%fZ") + str(run_id),
            "name": name,
            "run_type": "llm",
            "inputs": dict(inputs),
            "outputs": run_outputs,
            "start_time": _isoformat(start),
            "end_time": _isoformat(end),
            "extra": {"metadata": run_metadata},
            "error": error,
        }
        try:
            backend.post_run(run, self.project)
        except Exception as exc:
            self._disable(f"LangSmith tracing disabled after an error ({type(exc).__name__})")
            return False
        self.recorded += 1
        return True

    def close(self) -> None:
        backend = self._backend
        if backend is not None:
            try:
                backend.close()
            except Exception:
                pass

    def summary(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "project": self.project if self.enabled or self.recorded else None,
            "recorded": self.recorded,
            "dropped": self.dropped,
        }

    def __repr__(self) -> str:
        return (
            f"BenchmarkTracer(enabled={self.enabled!r}, project={self.project!r}, "
            "credentials=<redacted>)"
        )


class _SdkBackend:
    def __init__(self, client: Any) -> None:
        self._client = client

    def post_run(self, run: Mapping[str, Any], project: str) -> None:
        payload = dict(run)
        payload["start_time"] = datetime.fromisoformat(str(run["start_time"]))
        payload["end_time"] = datetime.fromisoformat(str(run["end_time"]))
        name = payload.pop("name")
        inputs = payload.pop("inputs")
        run_type = payload.pop("run_type")
        self._client.create_run(name, inputs, run_type, project_name=project, **payload)

    def close(self) -> None:
        flush = getattr(self._client, "flush", None)
        if callable(flush):
            flush()


class _RestBackend:
    def __init__(self, client: Any) -> None:
        self._client = client

    def post_run(self, run: Mapping[str, Any], project: str) -> None:
        payload = dict(run)
        payload["session_name"] = project
        response = self._client.post("/runs", json=payload)
        response.raise_for_status()

    def close(self) -> None:
        self._client.close()


__all__ = [
    "BenchmarkTracer",
    "DEFAULT_PROJECT",
    "PUBLIC_DATASETS",
    "TracingRefused",
    "dataset_sha256",
    "is_public_dataset",
]
