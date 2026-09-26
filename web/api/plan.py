"""Same-origin, offline Adaptive Context Planner function for LLMSlim Studio."""

from __future__ import annotations

import importlib.util
import json
import sys
from collections import defaultdict, deque
from collections.abc import Mapping, Sequence
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def _add_repository_package_to_path() -> None:
    for candidate in (
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    ):
        if (candidate / "llmslim" / "__init__.py").is_file():
            sys.path.insert(0, str(candidate))
            return
    if importlib.util.find_spec("llmslim") is None:
        raise RuntimeError("LLMSlim is not available to this function.")


_add_repository_package_to_path()

from llmslim import plan_context  # noqa: E402

MAX_BODY_BYTES = 160_000
MAX_TOTAL_CHARS = 96_000
MAX_ITEMS_PER_KIND = 100
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 20
ALLOWED_MODELS = frozenset({"generic-128k", "sarvam-105b", "sarvam-105b-conversations"})
ALLOWED_POLICIES = frozenset({"balanced", "quality_first", "cost_first", "latency_first"})
ALLOWED_FIELDS = frozenset(
    {
        "messages",
        "documents",
        "memories",
        "tools",
        "query",
        "model",
        "max_input_tokens",
        "reserve_output_tokens",
        "safety_margin_tokens",
        "policy",
    }
)
_request_windows: defaultdict[str, deque[float]] = defaultdict(deque)
_EXPECTED_CANDIDATE_REJECTION_PREFIX = "rejected extractive candidate "


class RequestProblem(ValueError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _problem(status: int, code: str, message: str) -> RequestProblem:
    return RequestProblem(status, code, message)


def parse_json_body(raw_body: bytes, content_type: str | None) -> dict[str, Any]:
    if not content_type or not content_type.lower().startswith("application/json"):
        raise _problem(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "json_required", "Use application/json.")
    if not raw_body:
        raise _problem(HTTPStatus.BAD_REQUEST, "body_required", "A JSON request body is required.")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise _problem(
            HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be valid UTF-8 JSON."
        ) from exc
    if not isinstance(payload, dict):
        raise _problem(
            HTTPStatus.BAD_REQUEST, "object_required", "Request body must be a JSON object."
        )
    return payload


def _string(payload: Mapping[str, Any], name: str, default: str = "") -> str:
    value = payload.get(name, default)
    if not isinstance(value, str):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY, f"invalid_{name}", f"{name} must be a string."
        )
    return value


def _integer(
    payload: Mapping[str, Any], name: str, default: int, minimum: int, maximum: int
) -> int:
    value = payload.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"invalid_{name}",
            f"{name} must be an integer from {minimum} to {maximum}.",
        )
    return value


def _sequence(payload: Mapping[str, Any], name: str) -> list[Any]:
    value = payload.get(name, [])
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY, f"invalid_{name}", f"{name} must be an array."
        )
    values = list(value)
    if len(values) > MAX_ITEMS_PER_KIND:
        raise _problem(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "too_many_items",
            "A context category exceeds 100 items.",
        )
    return values


def execute_plan(payload: Mapping[str, Any]) -> dict[str, Any]:
    if set(payload).difference(ALLOWED_FIELDS):
        raise _problem(
            HTTPStatus.BAD_REQUEST, "unsupported_field", "Request includes an unsupported field."
        )
    messages = _sequence(payload, "messages")
    documents = _sequence(payload, "documents")
    memories = _sequence(payload, "memories")
    tools = _sequence(payload, "tools")
    for message in messages:
        if (
            not isinstance(message, Mapping)
            or not isinstance(message.get("role"), str)
            or not isinstance(message.get("content"), str)
        ):
            raise _problem(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                "invalid_messages",
                "Each message needs string role and content fields.",
            )
    for name, values in (("documents", documents), ("memories", memories)):
        if not all(isinstance(value, (str, Mapping)) for value in values):
            raise _problem(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                f"invalid_{name}",
                f"{name} entries must be strings or objects.",
            )
    if not all(isinstance(value, Mapping) for value in tools):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_tools", "tools entries must be objects."
        )
    total_chars = len(
        json.dumps(
            {"messages": messages, "documents": documents, "memories": memories, "tools": tools},
            ensure_ascii=False,
        )
    )
    if total_chars > MAX_TOTAL_CHARS:
        raise _problem(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "input_too_large",
            "Context exceeds the Studio limit.",
        )
    query = _string(payload, "query")
    model = _string(payload, "model", "sarvam-105b")
    policy = _string(payload, "policy", "balanced")
    if model not in ALLOWED_MODELS:
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_model", "model is not available in Studio."
        )
    if policy not in ALLOWED_POLICIES:
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_policy", "policy is not available in Studio."
        )
    plan = plan_context(
        messages=messages,
        documents=documents,
        memories=memories,
        tools=tools,
        query=query,
        model=model,
        max_input_tokens=_integer(payload, "max_input_tokens", 8192, 256, 131072),
        reserve_output_tokens=_integer(payload, "reserve_output_tokens", 1024, 0, 32768),
        safety_margin_tokens=_integer(payload, "safety_margin_tokens", 128, 0, 8192),
        policy=policy,
    )
    result = plan.to_dict(include_content=True)
    # Candidate generation deliberately tests multiple safe representations.
    # A rejected alternative is normal pruning, not a failure of the selected
    # plan, so keep public diagnostics focused on actionable plan-level issues.
    result["warnings"] = [
        warning
        for warning in result.get("warnings", [])
        if not str(warning).startswith(_EXPECTED_CANDIDATE_REJECTION_PREFIX)
    ]
    for decision in result.get("decisions", []):
        if isinstance(decision, dict):
            decision["warnings"] = [
                warning
                for warning in decision.get("warnings", [])
                if not str(warning).startswith(_EXPECTED_CANDIDATE_REJECTION_PREFIX)
            ]
    return result


def allow_request(client_key: str, now: float) -> bool:
    window = _request_windows[client_key]
    threshold = now - RATE_LIMIT_WINDOW_SECONDS
    while window and window[0] <= threshold:
        window.popleft()
    if len(window) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    window.append(now)
    return True


class handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Disable default request logging so prompt content is never emitted."""

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
        import time

        client_key = self.headers.get("x-forwarded-for", "").split(",")[0].strip() or "anonymous"
        if not allow_request(client_key, time.monotonic()):
            self._respond(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Please wait before planning again.",
                    }
                },
            )
            return
        try:
            content_length = int(self.headers.get("content-length", ""))
            if not 0 <= content_length <= MAX_BODY_BYTES:
                raise ValueError
        except ValueError:
            self._respond(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                {
                    "error": {
                        "code": "body_too_large",
                        "message": "Request body exceeds the Studio limit.",
                    }
                },
            )
            return
        try:
            request = parse_json_body(
                self.rfile.read(content_length), self.headers.get("content-type")
            )
            self._respond(HTTPStatus.OK, {"data": execute_plan(request)})
        except RequestProblem as exc:
            self._respond(exc.status, {"error": {"code": exc.code, "message": exc.message}})
        except Exception:
            self._respond(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": {
                        "code": "planning_failed",
                        "message": "Planning could not be completed. Please retry.",
                    }
                },
            )

    def do_GET(self) -> None:  # noqa: N802
        self._respond(HTTPStatus.OK, {"status": "ok", "service": "llmslim-offline-planner"})


if __name__ == "__main__":  # pragma: no cover - local browser QA helper.
    from http.server import HTTPServer

    HTTPServer(("127.0.0.1", 8765), handler).serve_forever()
