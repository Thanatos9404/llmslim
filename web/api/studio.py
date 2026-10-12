"""Same-origin Vercel Function for the Studio.

It compresses the submitted text around a question with the repository's
``llmslim`` package and, for comparison, cuts the same text to the same token
count without looking at it. The response lists which parts of the original
were kept so the page can show them in place. Nothing is stored or logged.
"""

from __future__ import annotations

import json
import re
import sys
import time
from collections import defaultdict, deque
from collections.abc import Mapping
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any


def _add_repository_package_to_path() -> None:
    """Prefer the sibling source tree in local runs; production installs the package."""

    for candidate in (
        Path.cwd(),
        Path(__file__).resolve().parents[1],
        Path(__file__).resolve().parents[2],
    ):
        if (candidate / "llmslim" / "__init__.py").is_file():
            root = str(candidate)
            if root not in sys.path:
                sys.path.insert(0, root)
            return


_add_repository_package_to_path()

import llmslim  # noqa: E402  (path is established above)
from llmslim import compress  # noqa: E402
from llmslim.tokens import count_tokens  # noqa: E402

# api/_sentry.py is shared code: Vercel does not route files whose names start with an underscore.
_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR not in sys.path:
    sys.path.append(_API_DIR)

import _sentry  # noqa: E402
import _shared  # noqa: E402

_sentry.init()

MAX_BODY_BYTES = 120_000
MAX_INPUT_CHARS = 60_000
MAX_INPUT_TOKENS = 16_000
MAX_QUESTION_CHARS = 500
MIN_KEEP = 0.10
MAX_KEEP = 0.60
BASELINES = frozenset({"head", "tail"})
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_REQUESTS = 30

_request_windows: dict[str, deque[float]] = defaultdict(deque)
# Load the tokenizer and sentence data once per instance, so the time shown is the compression itself.
compress("Warm the tokenizer once. Then measure only the work.", target_ratio=0.5, query="warm")
# Split after sentence ends that are followed by whitespace, and after every newline. Lossless:
# joining the pieces gives back the original text exactly.
_BOUNDARY = re.compile(r"(?<=[.!?])(?=\s)|(?<=\n)")
_SPACE = re.compile(r"\s+")


class RequestProblem(ValueError):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def _bad(code: str, message: str) -> RequestProblem:
    return RequestProblem(HTTPStatus.BAD_REQUEST, code, message)


def parse_json_body(raw_body: bytes, content_type: str | None) -> dict[str, Any]:
    if not content_type or "application/json" not in content_type.lower():
        raise RequestProblem(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "unsupported_media_type", "Send JSON."
        )
    try:
        return _shared.decode_json_object(raw_body)
    except _shared.BodyError as error:
        # This function has always answered a non-object body with invalid_json.
        code = "invalid_json" if error.code == "object_required" else error.code
        raise RequestProblem(error.status, code, error.message) from None


def _normal(text: str) -> str:
    return _SPACE.sub(" ", text).strip()


def segments(original: str, compressed: str) -> list[list[Any]]:
    """The original as ``[piece, kept]`` pairs. Whitespace-only pieces count as kept."""

    sent = _normal(compressed)
    pieces = [piece for piece in _BOUNDARY.split(original) if piece]
    return [[piece, not piece.strip() or _normal(piece) in sent] for piece in pieces]


def cut_to(text: str, tokens: int, keep: str) -> str:
    """The longest head (or tail) of ``text`` that fits in ``tokens``, on a whitespace boundary."""

    if count_tokens(text) <= tokens:
        return text
    low, high = 0, len(text)
    while low < high:
        middle = (low + high + 1) // 2
        piece = text[:middle] if keep == "head" else text[len(text) - middle :]
        if count_tokens(piece) <= tokens:
            low = middle
        else:
            high = middle - 1
    piece = text[:low] if keep == "head" else text[len(text) - low :]
    if keep == "head":
        edge = piece.rfind(" ")
        return piece[:edge] if edge > len(piece) * 0.8 else piece
    edge = piece.find(" ")
    return piece[edge + 1 :] if 0 <= edge < len(piece) * 0.2 else piece


def run(payload: Mapping[str, Any]) -> dict[str, Any]:
    unknown = set(payload) - {"text", "question", "keep", "baseline"}
    if unknown:
        raise _bad("unknown_fields", f"Unknown fields: {', '.join(sorted(unknown))}.")
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise _bad("missing_text", "Paste some text to compress.")
    if len(text) > MAX_INPUT_CHARS:
        raise _bad("text_too_long", "The text is longer than the Studio allows.")
    question = payload.get("question", "")
    if not isinstance(question, str) or len(question) > MAX_QUESTION_CHARS:
        raise _bad("invalid_question", "The question must be text of at most 500 characters.")
    keep = payload.get("keep", 0.25)
    if (
        isinstance(keep, bool)
        or not isinstance(keep, (int, float))
        or not MIN_KEEP <= float(keep) <= MAX_KEEP
    ):
        raise _bad("invalid_keep", "keep must be between 0.10 and 0.60.")
    baseline = payload.get("baseline", "head")
    if baseline not in BASELINES:
        raise _bad("invalid_baseline", "baseline must be head or tail.")
    original_tokens = count_tokens(text)
    if original_tokens > MAX_INPUT_TOKENS:
        raise _bad("text_too_long", "The text is longer than the Studio allows.")

    started = time.perf_counter()
    result = compress(text, target_ratio=float(keep), query=question.strip() or None)
    elapsed_ms = (time.perf_counter() - started) * 1000
    kept_tokens = result.compressed_tokens
    truncated = cut_to(text, kept_tokens, baseline)
    return {
        "version": getattr(llmslim, "__version__", "unknown"),
        "selection": getattr(result, "selection", None),
        "original_tokens": original_tokens,
        "kept_tokens": kept_tokens,
        "elapsed_ms": round(elapsed_ms, 1),
        "compressed_text": result.compressed_text,
        "segments": segments(text, result.compressed_text),
        "baseline": {"keep": baseline, "text": truncated, "tokens": count_tokens(truncated)},
    }


def allow_request(client_key: str, now: float | None = None) -> bool:
    """Best-effort per-instance abuse guard; platform rate limiting remains advisable."""

    moment = time.monotonic() if now is None else now
    _shared.bound_windows(_request_windows, moment - RATE_LIMIT_WINDOW_SECONDS)
    window = _request_windows[client_key]
    while window and window[0] <= moment - RATE_LIMIT_WINDOW_SECONDS:
        window.popleft()
    if len(window) >= RATE_LIMIT_MAX_REQUESTS:
        return False
    window.append(moment)
    return True


class handler(BaseHTTPRequestHandler):
    """Vercel's standard-library Python Function entry point."""

    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Never log request contents."""

    def _respond(self, status: int, payload: Mapping[str, Any]) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(encoded)

    def _error(self, status: int, code: str, message: str) -> None:
        self._respond(status, {"error": {"code": code, "message": message}})

    def do_POST(self) -> None:  # noqa: N802
        forwarded = self.headers.get("x-forwarded-for", "")
        if not allow_request(forwarded.split(",")[0].strip() or "anonymous"):
            self._error(
                HTTPStatus.TOO_MANY_REQUESTS,
                "rate_limited",
                "Please wait a moment before running the Studio again.",
            )
            return
        try:
            length = int(self.headers.get("content-length", ""))
        except ValueError:
            length = -1
        if length < 0:
            self._error(
                HTTPStatus.BAD_REQUEST, "invalid_content_length", "Content-Length must be valid."
            )
            return
        if length > MAX_BODY_BYTES:
            self._error(
                HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                "body_too_large",
                "The text is longer than the Studio allows.",
            )
            return
        try:
            payload = parse_json_body(self.rfile.read(length), self.headers.get("content-type"))
            self._respond(HTTPStatus.OK, {"data": run(payload)})
        except RequestProblem as problem:
            self._error(problem.status, problem.code, problem.message)
        except Exception as error:
            _sentry.capture(error, function="studio")
            self._error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                "compression_failed",
                "Compression could not be completed. Please retry.",
            )

    def do_GET(self) -> None:  # noqa: N802
        self._error(HTTPStatus.METHOD_NOT_ALLOWED, "method_not_allowed", "Use POST.")
