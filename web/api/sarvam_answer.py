"""Studio "Answer with Sarvam": the compressed context and the question, answered by sarvam-105b.

After the Studio compresses a text around a question, the visitor can send that compressed context
and the question to Sarvam. This is the only Studio step that calls a model provider, and it runs
only when the visitor asks for it.

The step is paid, server-side and off by default. It is ready only when all of these hold:

- ``LLMSLIM_HOSTED_SARVAM_ENABLED`` is true (the kill switch),
- ``SARVAM_API_KEY`` and ``MONGODB_URI`` are set,
- ``LLMSLIM_RATE_LIMIT_HMAC_SECRET`` is at least 32 characters,
- ``LLMSLIM_ALLOWED_ORIGINS`` lists the exact origins allowed to call it, and
- the ``sarvamai`` and ``pymongo`` packages are installed.

``GET`` reports readiness so the page can hide the step. ``POST`` checks the origin, then
pseudonymous (HMAC) network and session rate limits, the body, and finally hands a bounded request
to :class:`llmslim.hosted.HostedSarvamService`, which plans the context, reserves spend in the
MongoDB ledger (per-request, daily and monthly INR caps, token quotas, concurrency leases), calls
Sarvam and settles provider-reported usage. The browser never sees the provider key. Request
contents are never stored or logged, and errors are returned as fixed codes and messages.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from collections.abc import Mapping
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Optional


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

from llmslim.hosted import (  # noqa: E402  (path is established above)
    HostedQuotaStoreError,
    HostedSarvamConfig,
    HostedSarvamError,
    HostedSarvamService,
    MongoDBHostedQuotaStore,
    RequestIdentity,
    build_request_identity,
)
from llmslim.tokens import count_tokens  # noqa: E402

# api/_sentry.py is shared code: Vercel does not route files whose names start with an underscore.
_API_DIR = str(Path(__file__).resolve().parent)
if _API_DIR not in sys.path:
    sys.path.append(_API_DIR)

import _sentry  # noqa: E402

_sentry.init()

SERVICE = "llmslim-studio-sarvam-answer"
SESSION_COOKIE = "llmslim_hosted_session"
COOKIE_PATH = "/api/sarvam_answer"
MAX_QUESTION_CHARS = 500
ANSWER_MAX_OUTPUT_TOKENS = 256
SAFETY_MARGIN_TOKENS = 128
# Room for the question, the system prompt and the planner's framing around the context.
PROMPT_HEADROOM_TOKENS = 512
ALLOWED_FIELDS = frozenset({"context", "question"})
# The largest body read only to be dropped (the highest LLMSLIM_SARVAM_MAX_BODY_BYTES allowed).
DISCARD_LIMIT_BYTES = 1_000_000
# Rejections recorded as aggregate "invalid_request" or "oversized_request" telemetry.
VALIDATION_CODES = frozenset(
    {
        "body_too_large",
        "json_required",
        "body_required",
        "invalid_json",
        "object_required",
        "unsupported_field",
        "invalid_context",
        "invalid_question",
        "context_too_large",
        "input_too_large",
        "too_many_items",
        "invalid_documents",
        "invalid_query",
        "invalid_model",
        "invalid_policy",
        "invalid_max_input_tokens",
        "invalid_max_output_tokens",
    }
)
UNAVAILABLE = "Sarvam answers are unavailable right now. Compression still works."

_store: Optional[MongoDBHostedQuotaStore] = None


def allowed_origins(environ: Optional[Mapping[str, str]] = None) -> frozenset[str]:
    env = os.environ if environ is None else environ
    return frozenset(
        value.strip().rstrip("/")
        for value in env.get("LLMSLIM_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    )


def _dependencies_available() -> bool:
    return all(importlib.util.find_spec(name) is not None for name in ("sarvamai", "pymongo"))


def hosted_ready(config: HostedSarvamConfig, environ: Optional[Mapping[str, str]] = None) -> bool:
    """Every server secret, the kill switch, the origin allow-list and the client packages."""

    env = os.environ if environ is None else environ
    return bool(
        config.enabled
        and env.get("SARVAM_API_KEY")
        and env.get("MONGODB_URI")
        and len(env.get("LLMSLIM_RATE_LIMIT_HMAC_SECRET", "")) >= 32
        and allowed_origins(env)
        and _dependencies_available()
    )


def output_tokens(config: HostedSarvamConfig) -> int:
    return min(ANSWER_MAX_OUTPUT_TOKENS, config.max_output_tokens)


def max_context_tokens(config: HostedSarvamConfig) -> int:
    """The largest compressed context accepted, so the model sees what the Studio showed."""

    return max(
        0,
        config.max_input_tokens
        - output_tokens(config)
        - SAFETY_MARGIN_TOKENS
        - PROMPT_HEADROOM_TOKENS,
    )


def _get_store(config: HostedSarvamConfig) -> MongoDBHostedQuotaStore:
    global _store
    if _store is None:
        _store = MongoDBHostedQuotaStore.from_env(config)
    return _store


def make_service(config: HostedSarvamConfig) -> HostedSarvamService:
    """The production service. Tests replace this with fakes; nothing here calls Sarvam."""

    return HostedSarvamService(config, _get_store(config))


def _session_from_cookie(header: Optional[str]) -> Optional[str]:
    if not header:
        return None
    try:
        cookie = SimpleCookie()
        cookie.load(header)
        morsel = cookie.get(SESSION_COOKIE)
        return morsel.value if morsel is not None else None
    except Exception:
        return None


def _forwarded_ip(headers: Mapping[str, str]) -> str:
    return headers.get("x-vercel-forwarded-for") or headers.get("x-forwarded-for") or "unknown"


def identity_for(headers: Mapping[str, str]) -> RequestIdentity:
    """HMAC-pseudonymised network and session identity; raw values are not kept."""

    return build_request_identity(
        forwarded_for=_forwarded_ip(headers),
        session_id=_session_from_cookie(headers.get("cookie")),
        hmac_secret=os.environ.get("LLMSLIM_RATE_LIMIT_HMAC_SECRET", ""),
    )


def origin_allowed(origin: Optional[str], environ: Optional[Mapping[str, str]] = None) -> bool:
    """Exact match against ``LLMSLIM_ALLOWED_ORIGINS``. Browsers send Origin on every POST, so a
    missing Origin is refused too."""

    return bool(origin) and str(origin).rstrip("/") in allowed_origins(environ)


def parse_json_body(raw_body: bytes, content_type: Optional[str]) -> Mapping[str, Any]:
    if not content_type or not content_type.lower().startswith("application/json"):
        raise HostedSarvamError(
            HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "json_required", "Use application/json."
        )
    if not raw_body:
        raise HostedSarvamError(
            HTTPStatus.BAD_REQUEST, "body_required", "A JSON request body is required."
        )
    try:
        payload = json.loads(raw_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise HostedSarvamError(
            HTTPStatus.BAD_REQUEST, "invalid_json", "Request body must be valid UTF-8 JSON."
        ) from None
    if not isinstance(payload, dict):
        raise HostedSarvamError(
            HTTPStatus.BAD_REQUEST, "object_required", "Request body must be a JSON object."
        )
    return payload


def build_request(
    payload: Mapping[str, Any], config: HostedSarvamConfig
) -> tuple[dict[str, Any], int]:
    """Turn ``{"context", "question"}`` into the hosted service's request, with the context's
    token count. Everything else in the request is fixed by the server."""

    if set(payload).difference(ALLOWED_FIELDS):
        raise HostedSarvamError(
            HTTPStatus.BAD_REQUEST, "unsupported_field", "Send only the context and the question."
        )
    context = payload.get("context")
    if not isinstance(context, str) or not context.strip():
        raise HostedSarvamError(
            HTTPStatus.UNPROCESSABLE_ENTITY, "invalid_context", "Compress some text first."
        )
    question = payload.get("question")
    if not isinstance(question, str) or not question.strip() or len(question) > MAX_QUESTION_CHARS:
        raise HostedSarvamError(
            HTTPStatus.UNPROCESSABLE_ENTITY,
            "invalid_question",
            f"Ask a question of 1 to {MAX_QUESTION_CHARS} characters.",
        )
    if len(context) > config.max_total_chars:
        raise HostedSarvamError(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "input_too_large",
            "The compressed context is too long to answer here.",
        )
    limit = max_context_tokens(config)
    tokens = count_tokens(context)
    if tokens > limit:
        raise HostedSarvamError(
            HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
            "context_too_large",
            f"Keep less: Sarvam answers here use at most {limit:,} context tokens.",
        )
    request = {
        "documents": [context],
        "query": question.strip(),
        "model": config.model,
        "max_input_tokens": config.max_input_tokens,
        "max_output_tokens": output_tokens(config),
        "policy": "balanced",
    }
    return request, tokens


def public_result(result: Mapping[str, Any], submitted_tokens: int, model: str) -> dict[str, Any]:
    """What the page needs: the answer, token counts and usage. Not the planned context."""

    plan = result.get("plan")
    metrics = plan.get("metrics") if isinstance(plan, Mapping) else None
    if not isinstance(metrics, Mapping):
        metrics = {}
    by_kind = metrics.get("tokens_by_kind")
    # Tokens of the Studio context that reached Sarvam, after the planner fitted it to the budget.
    sent = by_kind.get("rag_document") if isinstance(by_kind, Mapping) else None
    if not isinstance(sent, int):
        planned = metrics.get("planned_tokens")
        sent = planned if isinstance(planned, int) else None
    return {
        "answer": str(result.get("answer", "")),
        "model": model,
        "request_id": result.get("request_id"),
        "context": {
            "submitted_tokens": submitted_tokens,
            "sent_tokens": sent,
            "further_compressed": bool(metrics.get("items_compressed")),
        },
        "usage": result.get("usage"),
    }


def _record_validation_rejection(
    service: Optional[HostedSarvamService], error: HostedSarvamError
) -> None:
    if service is None or error.code not in VALIDATION_CODES:
        return
    event = (
        "oversized_request"
        if error.status == HTTPStatus.REQUEST_ENTITY_TOO_LARGE
        else "invalid_request"
    )
    try:
        service.quota_store.record_event(event, now=service.clock())
    except HostedQuotaStoreError:
        pass


class handler(BaseHTTPRequestHandler):
    """Vercel's standard-library Python Function entry point."""

    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Never log: request lines and errors could carry prompt text or credentials."""

    def _respond(
        self,
        status: int,
        payload: Mapping[str, Any],
        *,
        identity: Optional[RequestIdentity] = None,
        retry_after: Optional[int] = None,
        body_read: bool = True,
    ) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        if retry_after is not None:
            self.send_header("Retry-After", str(max(1, retry_after)))
        if identity is not None and identity.is_new_session:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={identity.session_id}; Path={COOKIE_PATH}; Max-Age=86400; "
                "HttpOnly; Secure; SameSite=Strict",
            )
        if not body_read and not self._discard_body():
            # An unread body would corrupt the next request on a kept-alive connection.
            self.send_header("Connection", "close")
            self.close_connection = True
        self.end_headers()
        self.wfile.write(encoded)

    def _discard_body(self) -> bool:
        """Read and drop a bounded body the request was refused before reading, so the reply
        is not cut off by a reset when the connection closes with unread data."""

        try:
            length = int(self.headers.get("content-length", ""))
        except ValueError:
            return False
        if not 0 <= length <= DISCARD_LIMIT_BYTES:
            return False
        if length:
            self.rfile.read(length)
        return True

    def _fail(
        self,
        error: HostedSarvamError,
        identity: Optional[RequestIdentity],
        *,
        body_read: bool,
    ) -> None:
        self._respond(
            error.status,
            {"error": {"code": error.code, "message": error.public_message}},
            identity=identity,
            retry_after=error.retry_after,
            body_read=body_read,
        )

    def do_GET(self) -> None:  # noqa: N802
        try:
            config = HostedSarvamConfig.from_env()
            ready = hosted_ready(config)
        except HostedSarvamError:
            config, ready = None, False
        payload: dict[str, Any] = {"status": "ok", "service": SERVICE, "ready": ready}
        if ready and config is not None:
            payload.update(
                {
                    "model": config.model,
                    "max_context_tokens": max_context_tokens(config),
                    "max_question_chars": MAX_QUESTION_CHARS,
                }
            )
        self._respond(HTTPStatus.OK, payload)

    def do_POST(self) -> None:  # noqa: N802
        identity: Optional[RequestIdentity] = None
        service: Optional[HostedSarvamService] = None
        body_read = False
        try:
            config = HostedSarvamConfig.from_env()
            if not hosted_ready(config):
                raise HostedSarvamError(
                    HTTPStatus.SERVICE_UNAVAILABLE, "hosted_disabled", UNAVAILABLE
                )
            if not origin_allowed(self.headers.get("origin")):
                raise HostedSarvamError(
                    HTTPStatus.FORBIDDEN,
                    "origin_not_allowed",
                    "This origin cannot use Sarvam answers.",
                )
            identity = identity_for({key.lower(): value for key, value in self.headers.items()})
            service = make_service(config)
            service.check_initial_limits(identity)
            try:
                content_length = int(self.headers.get("content-length", ""))
            except ValueError:
                content_length = -1
            if not 0 < content_length <= config.max_body_bytes:
                raise HostedSarvamError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "body_too_large",
                    "The request is larger than Sarvam answers allow.",
                )
            raw = self.rfile.read(content_length)
            body_read = True
            payload = parse_json_body(raw, self.headers.get("content-type"))
            request, submitted_tokens = build_request(payload, config)
            result = service.execute(request, identity)
            self._respond(
                HTTPStatus.OK,
                {"data": public_result(result, submitted_tokens, str(request["model"]))},
                identity=identity,
            )
        except HostedSarvamError as error:
            _record_validation_rejection(service, error)
            self._fail(error, identity, body_read=body_read)
        except HostedQuotaStoreError as error:
            _sentry.capture(error, function="sarvam_answer")
            self._fail(
                HostedSarvamError(
                    HTTPStatus.SERVICE_UNAVAILABLE, "quota_store_unavailable", UNAVAILABLE
                ),
                identity,
                body_read=body_read,
            )
        except Exception as error:
            _sentry.capture(error, function="sarvam_answer")
            self._fail(
                HostedSarvamError(
                    HTTPStatus.INTERNAL_SERVER_ERROR,
                    "answer_failed",
                    "Sarvam could not answer this time. Please retry later.",
                ),
                identity,
                body_read=body_read,
            )


if __name__ == "__main__":  # pragma: no cover - local browser QA helper.
    from http.server import ThreadingHTTPServer

    ThreadingHTTPServer(("127.0.0.1", 8769), handler).serve_forever()
