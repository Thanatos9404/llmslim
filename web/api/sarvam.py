"""Protected server-side Sarvam execution for LLMSlim Studio.

The browser never receives or supplies a provider credential.  Paid mode is
disabled by default and fails closed unless durable MongoDB quota accounting,
an identity HMAC secret, and ``SARVAM_API_KEY`` are configured server-side.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from typing import Any, Mapping, Optional


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

from llmslim.hosted import (  # noqa: E402
    HostedQuotaStoreError,
    HostedSarvamConfig,
    HostedSarvamError,
    HostedSarvamService,
    MongoDBHostedQuotaStore,
    RequestIdentity,
    build_request_identity,
)

SESSION_COOKIE = "llmslim_hosted_session"
_store: Optional[MongoDBHostedQuotaStore] = None


def _hosted_ready(config: HostedSarvamConfig) -> bool:
    return bool(
        config.enabled
        and os.environ.get("SARVAM_API_KEY")
        and os.environ.get("MONGODB_URI")
        and len(os.environ.get("LLMSLIM_RATE_LIMIT_HMAC_SECRET", "")) >= 32
    )


def _get_store(config: HostedSarvamConfig) -> MongoDBHostedQuotaStore:
    global _store
    if _store is None:
        _store = MongoDBHostedQuotaStore.from_env(config)
    return _store


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


def _identity(headers: Mapping[str, str]) -> RequestIdentity:
    secret = os.environ.get("LLMSLIM_RATE_LIMIT_HMAC_SECRET", "")
    return build_request_identity(
        forwarded_for=_forwarded_ip(headers),
        session_id=_session_from_cookie(headers.get("cookie")),
        hmac_secret=secret,
    )


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


def _record_validation_rejection(
    service: Optional[HostedSarvamService], error: HostedSarvamError
) -> None:
    if service is None:
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
    protocol_version = "HTTP/1.1"

    def log_message(self, _format: str, *_args: object) -> None:
        """Disable BaseHTTPRequestHandler logging so prompt data cannot leak."""

    def _respond(
        self,
        status: int,
        payload: Mapping[str, Any],
        *,
        identity: Optional[RequestIdentity] = None,
        retry_after: Optional[int] = None,
    ) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store, private")
        self.send_header("Pragma", "no-cache")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        if retry_after is not None:
            self.send_header("Retry-After", str(max(1, retry_after)))
        if identity is not None and identity.is_new_session:
            self.send_header(
                "Set-Cookie",
                f"{SESSION_COOKIE}={identity.session_id}; Path=/; Max-Age=86400; "
                "HttpOnly; Secure; SameSite=Lax",
            )
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self) -> None:  # noqa: N802
        try:
            config = HostedSarvamConfig.from_env()
            enabled = _hosted_ready(config)
        except HostedSarvamError:
            enabled = False
        self._respond(
            HTTPStatus.OK,
            {
                "status": "ok",
                "service": "llmslim-hosted-sarvam",
                "hosted_enabled": enabled,
            },
        )

    def do_POST(self) -> None:  # noqa: N802
        identity: Optional[RequestIdentity] = None
        service: Optional[HostedSarvamService] = None
        try:
            config = HostedSarvamConfig.from_env()
            if not _hosted_ready(config):
                raise HostedSarvamError(
                    HTTPStatus.SERVICE_UNAVAILABLE,
                    "hosted_disabled",
                    "Hosted Sarvam inference is temporarily unavailable. Offline planning remains available.",
                )
            identity = _identity({key.lower(): value for key, value in self.headers.items()})
            service = HostedSarvamService(config, _get_store(config))
            service.check_initial_limits(identity)
            try:
                content_length = int(self.headers.get("content-length", ""))
            except ValueError:
                content_length = -1
            if not 0 < content_length <= config.max_body_bytes:
                raise HostedSarvamError(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    "body_too_large",
                    "Request body exceeds the hosted-demo limit.",
                )
            payload = parse_json_body(
                self.rfile.read(content_length), self.headers.get("content-type")
            )
            self._respond(
                HTTPStatus.OK,
                {"data": service.execute(payload, identity)},
                identity=identity,
            )
        except HostedSarvamError as exc:
            if exc.code in {
                "body_too_large",
                "json_required",
                "body_required",
                "invalid_json",
                "object_required",
                "unsupported_field",
                "too_many_items",
                "invalid_messages",
                "invalid_documents",
                "invalid_memories",
                "invalid_tools",
                "tool_payload_too_large",
                "invalid_query",
                "invalid_model",
                "invalid_policy",
                "invalid_max_input_tokens",
                "invalid_max_output_tokens",
                "input_too_large",
            }:
                _record_validation_rejection(service, exc)
            self._respond(
                exc.status,
                {"error": {"code": exc.code, "message": exc.public_message}},
                identity=identity,
                retry_after=exc.retry_after,
            )
        except HostedQuotaStoreError:
            self._respond(
                HTTPStatus.SERVICE_UNAVAILABLE,
                {
                    "error": {
                        "code": "quota_store_unavailable",
                        "message": "Hosted inference is temporarily unavailable. Offline planning remains available.",
                    }
                },
                identity=identity,
            )
        except Exception:
            self._respond(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                {
                    "error": {
                        "code": "hosted_request_failed",
                        "message": "Hosted inference could not be completed. Offline planning remains available.",
                    }
                },
                identity=identity,
            )


if __name__ == "__main__":  # pragma: no cover - local browser QA helper.
    from http.server import HTTPServer

    HTTPServer(("127.0.0.1", 8766), handler).serve_forever()
