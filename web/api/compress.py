"""Same-origin Vercel Function for the live LLMSlim Studio.

The function deliberately imports the repository's ``llmslim`` package rather
than maintaining a second compression implementation.  When this Next.js app
is deployed with ``web`` as Vercel's Root Directory, enable *Include source
files outside of the Root Directory in the Build Step* so the sibling package
is present in the function bundle.  See ``web/VERCEL_STUDIO_DEPLOYMENT.md``.
"""

from __future__ import annotations

import json
import sys
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def _add_repository_package_to_path() -> None:
    """Make the repository's LLMSlim package importable in local/Vercel runs."""

    # Production installs the exact repository revision through requirements.txt.
    # Keep the path lookup for local development, where the sibling source tree is
    # preferred and no package installation is necessary.
    candidates = (
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    )
    for candidate in candidates:
        if (candidate / "llmslim" / "__init__.py").is_file():
            package_root = str(candidate)
            if package_root not in sys.path:
                sys.path.insert(0, package_root)
            return
    import importlib.util

    if importlib.util.find_spec("llmslim") is None:
        raise RuntimeError("LLMSlim is not available to this function.")


_add_repository_package_to_path()

from llmslim import ContextRole, compress  # noqa: E402  (path is established above)
from llmslim.tokens import count_tokens  # noqa: E402

MAX_BODY_BYTES = 80_000
MAX_INPUT_CHARS = 48_000
MAX_INPUT_TOKENS = 12_000
MIN_TARGET_RATIO = 0.10
MAX_TARGET_RATIO = 0.90
MIN_MAX_CHUNK_TOKENS = 32
MAX_MAX_CHUNK_TOKENS = 4_000
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30
ALLOWED_CONTEXT_ROLES = frozenset(role.value for role in ContextRole)
ALLOWED_STRATEGIES = frozenset({"extractive"})
_request_windows: defaultdict[str, deque[float]] = defaultdict(deque)


class RequestProblem(ValueError):
    """A client-safe validation failure."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _problem(status: int, code: str, message: str) -> RequestProblem:
    return RequestProblem(status, code, message)


def parse_json_body(raw_body: bytes, content_type: str | None) -> dict[str, Any]:
    """Parse one bounded JSON body without surfacing parser internals."""

    if not content_type or not content_type.lower().startswith("application/json"):
        raise _problem(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "json_required", "Use application/json.")
    if not raw_body:
        raise _problem(HTTPStatus.BAD_REQUEST, "body_required", "A JSON request body is required.")
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _problem(
            HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be valid UTF-8 JSON."
        ) from error
    if not isinstance(payload, dict):
        raise _problem(
            HTTPStatus.BAD_REQUEST, "object_required", "Request body must be a JSON object."
        )
    return payload


def _required_string(payload: Mapping[str, Any], name: str) -> str:
    value = payload.get(name)
    if not isinstance(value, str):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY, f"invalid_{name}", f"{name} must be a string."
        )
    return value


def _optional_integer(payload: Mapping[str, Any], name: str) -> int | None:
    value = payload.get(name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            f"invalid_{name}",
            f"{name} must be an integer or null.",
        )
    return value


def _target_ratio(payload: Mapping[str, Any]) -> float:
    value = payload.get("target_ratio")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_target_ratio",
            "target_ratio must be a number.",
        )
    ratio = float(value)
    if not MIN_TARGET_RATIO <= ratio <= MAX_TARGET_RATIO:
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_target_ratio",
            "target_ratio must be between 0.10 and 0.90.",
        )
    return ratio


def execute_compression(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Validate a Studio request and serialize genuine ``CompressionResult`` data."""

    allowed_fields = {"text", "strategy", "target_ratio", "context_role", "max_chunk_tokens"}
    unexpected_fields = set(payload).difference(allowed_fields)
    if unexpected_fields:
        raise _problem(
            HTTPStatus.BAD_REQUEST, "unsupported_field", "Request includes an unsupported field."
        )

    text = _required_string(payload, "text")
    if not text.strip():
        raise _problem(HTTPStatus.UNPROCESSABLE_ENTITY, "empty_text", "text must not be empty.")
    if len(text) > MAX_INPUT_CHARS:
        raise _problem(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "input_too_large",
            "text exceeds the Studio character limit.",
        )

    input_tokens = count_tokens(text)
    if input_tokens > MAX_INPUT_TOKENS:
        raise _problem(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "input_too_large",
            "text exceeds the Studio token limit.",
        )

    strategy = _required_string(payload, "strategy")
    if strategy not in ALLOWED_STRATEGIES:
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "strategy_not_available",
            "Only extractive compression is available in the public Studio. Rewrite and hybrid require a caller-supplied provider.",
        )

    context_role = _required_string(payload, "context_role")
    if context_role not in ALLOWED_CONTEXT_ROLES:
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_context_role",
            "context_role is not supported.",
        )

    target_ratio = _target_ratio(payload)
    max_chunk_tokens = _optional_integer(payload, "max_chunk_tokens")
    if (
        max_chunk_tokens is not None
        and not MIN_MAX_CHUNK_TOKENS <= max_chunk_tokens <= MAX_MAX_CHUNK_TOKENS
    ):
        raise _problem(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_max_chunk_tokens",
            "max_chunk_tokens must be between 32 and 4000 when provided.",
        )

    started = time.perf_counter()
    options: dict[str, Any] = {
        "target_ratio": target_ratio,
        "strategy": strategy,
        "context_role": ContextRole(context_role),
    }
    if max_chunk_tokens is not None:
        options["max_chunk_tokens"] = max_chunk_tokens
    result = compress(text, **options)
    elapsed_ms = result.elapsed_ms
    if elapsed_ms is None:
        elapsed_ms = round((time.perf_counter() - started) * 1000, 3)

    # Every value below is supplied by CompressionResult, except context_role
    # (the validated invocation argument) and max_chunk_tokens (the validated
    # option).  No text selection or token arithmetic is duplicated here.
    return {
        "output": result.compressed_text,
        "original_tokens": result.original_tokens,
        "compressed_tokens": result.compressed_tokens,
        "tokens_saved": result.tokens_saved,
        "reduction_percent": result.reduction_percent,
        "target_ratio": result.target_ratio,
        "actual_ratio": result.actual_ratio,
        "strategy": strategy,
        "context_role": context_role,
        "token_counter_used": result.token_counter_used,
        "elapsed_ms": elapsed_ms,
        "sentences_total": result.sentences_total,
        "sentences_kept": result.sentences_kept,
        "num_chunks": result.num_chunks,
        "backend": result.backend,
        "max_chunk_tokens": max_chunk_tokens,
    }


def allow_request(client_key: str, now: float | None = None) -> bool:
    """Best-effort per-instance abuse guard; platform rate limiting remains advisable."""

    moment = time.monotonic() if now is None else now
    window = _request_windows[client_key]
    threshold = moment - RATE_LIMIT_WINDOW_SECONDS
    while window and window[0] <= threshold:
        window.popleft()
    if len(window) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    window.append(moment)
    return True


class handler(BaseHTTPRequestHandler):
    """Vercel's standard-library Python Function entry point."""

    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Avoid logging user-supplied payload fragments through the default logger."""

    def _respond(self, status: int, payload: Mapping[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def _client_key(self) -> str:
        # Vercel forwards the client chain. The conservative fallback limits
        # anonymous traffic even when a platform does not provide this header.
        forwarded = self.headers.get("x-forwarded-for", "")
        return forwarded.split(",")[0].strip() or "anonymous"

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Allow", "POST, OPTIONS")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        if not allow_request(self._client_key()):
            self._respond(
                HTTPStatus.TOO_MANY_REQUESTS,
                {
                    "error": {
                        "code": "rate_limited",
                        "message": "Please wait before running Studio again.",
                    }
                },
            )
            return

        try:
            content_length = int(self.headers.get("content-length", ""))
        except ValueError:
            self._respond(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": {
                        "code": "invalid_content_length",
                        "message": "Content-Length must be valid.",
                    }
                },
            )
            return
        if content_length < 0:
            self._respond(
                HTTPStatus.BAD_REQUEST,
                {
                    "error": {
                        "code": "invalid_content_length",
                        "message": "Content-Length must be valid.",
                    }
                },
            )
            return
        if content_length > MAX_BODY_BYTES:
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
            payload = parse_json_body(
                self.rfile.read(content_length), self.headers.get("content-type")
            )
            self._respond(HTTPStatus.OK, {"data": execute_compression(payload)})
        except RequestProblem as error:
            self._respond(error.status, {"error": {"code": error.code, "message": error.message}})
        except Exception:
            self._respond(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": {
                        "code": "compression_failed",
                        "message": "Live compression could not be completed. Please retry.",
                    }
                },
            )

    def do_GET(self) -> None:  # noqa: N802
        self._respond(
            HTTPStatus.METHOD_NOT_ALLOWED,
            {"error": {"code": "method_not_allowed", "message": "Use POST for live compression."}},
        )
