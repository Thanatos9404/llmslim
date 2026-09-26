"""Bounded, offline Context Inspector endpoint for the v0.7 Studio."""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def _add_repository_package_to_path() -> None:
    for candidate in (Path.cwd(), Path(__file__).resolve().parents[1], Path(__file__).resolve().parents[2]):
        if (candidate / "llmslim" / "__init__.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    if importlib.util.find_spec("llmslim") is None:
        raise RuntimeError("LLMSlim is not available to this function.")


_add_repository_package_to_path()

try:
    from llmslim import ContextRuntime  # noqa: E402
except ImportError:  # Installed web dependency may still be v0.6.
    ContextRuntime = None  # type: ignore[assignment,misc]

MAX_BODY_BYTES = 160_000
MAX_TOTAL_CHARS = 96_000
MAX_ITEMS_PER_KIND = 100
RATE_LIMIT_MAX_REQUESTS = 20
RATE_LIMIT_WINDOW_SECONDS = 60
ALLOWED_MODELS = frozenset({"generic-128k", "sarvam-105b", "sarvam-105b-conversations"})
ALLOWED_OBJECTIVES = frozenset({"balanced", "quality", "cost", "latency", "minimize_tokens"})
ALLOWED_FIELDS = frozenset({
    "messages", "documents", "memories", "tool_results", "tools", "query", "model",
    "max_input_tokens", "reserve_output_tokens", "quality_floor", "objective",
})
_request_windows: defaultdict[str, deque[float]] = defaultdict(deque)


class RequestProblem(ValueError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _problem(status: int, code: str, message: str) -> RequestProblem:
    return RequestProblem(status, code, message)


def execute_context(payload: Mapping[str, Any]) -> dict[str, Any]:
    if ContextRuntime is None:
        raise _problem(503, "runtime_unavailable", "Context Inspector requires the LLMSlim v0.7 runtime on the Studio server.")
    if set(payload).difference(ALLOWED_FIELDS):
        raise _problem(400, "unsupported_field", "Request includes an unsupported field.")
    arrays: dict[str, list[Any]] = {}
    for name in ("messages", "documents", "memories", "tool_results", "tools"):
        value = payload.get(name, [])
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise _problem(422, f"invalid_{name}", f"{name} must be an array.")
        arrays[name] = list(value)
        if len(arrays[name]) > MAX_ITEMS_PER_KIND:
            raise _problem(413, "too_many_items", "A context category exceeds 100 items.")
    if not all(isinstance(value, Mapping) and isinstance(value.get("content"), str)
               and value.get("role") in {"system", "developer", "user", "assistant", "tool"}
               for value in arrays["messages"]):
        raise _problem(422, "invalid_messages", "Messages need a valid role and text content.")
    if not all(isinstance(value, (str, Mapping)) for value in arrays["documents"] + arrays["memories"]):
        raise _problem(422, "invalid_evidence", "Documents and memories must be strings or objects.")
    if not all(isinstance(value, Mapping) and isinstance(value.get("content"), str)
               for value in arrays["tool_results"]):
        raise _problem(422, "invalid_tool_results", "Tool results need text content.")
    if not all(isinstance(value, Mapping) for value in arrays["tools"]):
        raise _problem(422, "invalid_tools", "Tool schemas must be objects.")
    if len(json.dumps(arrays, ensure_ascii=False)) > MAX_TOTAL_CHARS:
        raise _problem(413, "input_too_large", "Context exceeds the Studio limit.")
    query = payload.get("query", "")
    model = payload.get("model", "sarvam-105b")
    objective = payload.get("objective", "balanced")
    floor = payload.get("quality_floor", 0.80)
    budget = payload.get("max_input_tokens", 8192)
    reserve = payload.get("reserve_output_tokens", 1024)
    if not isinstance(query, str):
        raise _problem(422, "invalid_query", "query must be text.")
    if not isinstance(model, str) or model not in ALLOWED_MODELS:
        raise _problem(422, "invalid_model", "model is not available in Studio.")
    if not isinstance(objective, str) or objective not in ALLOWED_OBJECTIVES:
        raise _problem(422, "invalid_objective", "objective is not available in Studio.")
    if isinstance(floor, bool) or not isinstance(floor, (int, float)) or not 0 <= floor <= 1:
        raise _problem(422, "invalid_quality_floor", "quality_floor must be between 0 and 1.")
    if isinstance(budget, bool) or not isinstance(budget, int) or not 256 <= budget <= 131072:
        raise _problem(422, "invalid_max_input_tokens", "max_input_tokens is outside Studio limits.")
    if isinstance(reserve, bool) or not isinstance(reserve, int) or not 0 <= reserve <= 32768:
        raise _problem(422, "invalid_reserve_output_tokens", "reserve_output_tokens is outside Studio limits.")
    try:
        prepared = ContextRuntime(
            model=model, objective=objective, quality_floor=float(floor),
            max_input_tokens=budget, reserve_output_tokens=reserve,
            safety_margin_tokens=128,
        ).prepare_sync(
            user_input=query, messages=arrays["messages"], documents=arrays["documents"],
            memories=arrays["memories"], tool_results=arrays["tool_results"], tools=arrays["tools"],
        )
    except (TypeError, ValueError) as exc:
        raise _problem(422, "invalid_context", "Context could not be normalized or planned.") from exc
    plan = prepared.plan.to_dict(include_content=True)
    plan["warnings"] = [
        warning for warning in plan["warnings"]
        if not warning.startswith("rejected extractive candidate ")
    ]
    return {
        "plan": plan,
        "quality": prepared.quality.to_dict(),
        "trace": prepared.trace.to_dict(),
        "graph": prepared.graph.to_dict(),
        "envelope": prepared.envelope.to_dict(),
    }


def _allow_request(client: str, now: float) -> bool:
    window = _request_windows[client]
    while window and window[0] <= now - RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    window.append(now)
    return True


class handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Prompt bodies and request paths are never logged."""

    def _respond(self, status: int, payload: Mapping[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self) -> None:  # noqa: N802
        client = self.headers.get("x-forwarded-for", "").split(",")[0].strip() or "anonymous"
        if not _allow_request(client, time.monotonic()):
            self._respond(429, {"error": {"code": "rate_limited", "message": "Please wait before planning again."}})
            return
        try:
            length = int(self.headers.get("content-length", ""))
            if not 0 < length <= MAX_BODY_BYTES:
                raise ValueError
        except ValueError:
            self._respond(413, {"error": {"code": "body_too_large", "message": "Request body exceeds the Studio limit."}})
            return
        try:
            if not self.headers.get("content-type", "").lower().startswith("application/json"):
                raise _problem(415, "json_required", "Use application/json.")
            request = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(request, dict):
                raise _problem(400, "object_required", "A JSON object is required.")
            self._respond(HTTPStatus.OK, {"data": execute_context(request)})
        except RequestProblem as exc:
            self._respond(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._respond(400, {"error": {"code": "invalid_json", "message": "Valid UTF-8 JSON is required."}})
        except Exception:
            self._respond(500, {"error": {"code": "planning_failed", "message": "Planning could not be completed."}})

    def do_GET(self) -> None:  # noqa: N802
        self._respond(200, {"status": "ok", "service": "llmslim-context-inspector"})


if __name__ == "__main__":  # pragma: no cover
    from http.server import HTTPServer

    HTTPServer(("127.0.0.1", 8768), handler).serve_forever()
