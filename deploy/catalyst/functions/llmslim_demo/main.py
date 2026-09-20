"""Zoho Catalyst Advanced I/O deployment template for LLMSlim Studio.

Offline planning stays local to the function. Hosted Sarvam inference reuses
LLMSlim's fail-closed MongoDB-backed quota, spend, concurrency, and telemetry
layer; no provider credential is ever returned to the browser.
"""

from __future__ import annotations

import os
from http import HTTPStatus
from typing import Any, Dict, Mapping, Optional

from flask import Request, jsonify, make_response

from llmslim import plan_context
from llmslim.hosted import (
    HostedQuotaStoreError,
    HostedSarvamConfig,
    HostedSarvamError,
    HostedSarvamService,
    MongoDBHostedQuotaStore,
    RequestIdentity,
    build_request_identity,
)

SESSION_COOKIE = "llmslim_hosted_session"
MAX_OFFLINE_BODY_BYTES = 96_000
_store: Optional[MongoDBHostedQuotaStore] = None


def _json_response(
    payload: Mapping[str, Any],
    status: int = 200,
    *,
    identity: Optional[RequestIdentity] = None,
    retry_after: Optional[int] = None,
):
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "no-store, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Content-Security-Policy"] = "default-src 'none'"
    if retry_after is not None:
        response.headers["Retry-After"] = str(max(1, retry_after))
    if identity is not None and identity.is_new_session:
        response.set_cookie(
            SESSION_COOKIE,
            identity.session_id,
            max_age=86_400,
            secure=True,
            httponly=True,
            samesite="Lax",
        )
    return response


def _origin_allowed(request: Request) -> bool:
    allowed = {
        value.strip()
        for value in os.getenv("LLMSLIM_ALLOWED_ORIGINS", "").split(",")
        if value.strip()
    }
    origin = request.headers.get("Origin")
    return origin is None or origin in allowed


def _payload(request: Request, maximum: int) -> Dict[str, Any]:
    if request.content_length is None or not 0 < request.content_length <= maximum:
        raise HostedSarvamError(413, "body_too_large", "Request body exceeds the service limit.")
    value = request.get_json(silent=True)
    if not isinstance(value, dict):
        raise HostedSarvamError(400, "invalid_json", "A JSON object is required.")
    return value


def _plan(payload: Mapping[str, Any]):
    allowed = {
        "messages",
        "documents",
        "memories",
        "tools",
        "query",
        "model",
        "max_input_tokens",
        "reserve_output_tokens",
        "policy",
    }
    if set(payload).difference(allowed):
        raise HostedSarvamError(400, "unsupported_field", "Request includes an unsupported field.")
    plan = plan_context(
        messages=payload.get("messages", ()),
        documents=payload.get("documents", ()),
        memories=payload.get("memories", ()),
        tools=payload.get("tools", ()),
        query=str(payload.get("query", "")),
        model=str(payload.get("model", "sarvam-105b")),
        max_input_tokens=int(payload.get("max_input_tokens", 8192)),
        reserve_output_tokens=int(payload.get("reserve_output_tokens", 1024)),
        safety_margin_tokens=128,
        policy=str(payload.get("policy", "balanced")),
    )
    return _json_response({"data": plan.to_dict(include_content=True)})


def _hosted_ready(config: HostedSarvamConfig) -> bool:
    return bool(
        config.enabled
        and os.environ.get("SARVAM_API_KEY")
        and os.environ.get("MONGODB_URI")
        and len(os.environ.get("LLMSLIM_RATE_LIMIT_HMAC_SECRET", "")) >= 32
    )


def _quota_store(config: HostedSarvamConfig) -> MongoDBHostedQuotaStore:
    global _store
    if _store is None:
        _store = MongoDBHostedQuotaStore.from_env(config)
    return _store


def _identity(request: Request) -> RequestIdentity:
    return build_request_identity(
        forwarded_for=request.headers.get("X-Forwarded-For", "unknown"),
        session_id=request.cookies.get(SESSION_COOKIE),
        hmac_secret=os.environ.get("LLMSLIM_RATE_LIMIT_HMAC_SECRET", ""),
    )


def _sarvam(request: Request):
    config = HostedSarvamConfig.from_env()
    if not _hosted_ready(config):
        raise HostedSarvamError(
            503,
            "hosted_disabled",
            "Hosted Sarvam inference is temporarily unavailable. Offline planning remains available.",
        )
    identity = _identity(request)
    service = HostedSarvamService(config, _quota_store(config))
    service.check_initial_limits(identity)
    payload = _payload(request, config.max_body_bytes)
    return _json_response({"data": service.execute(payload, identity)}, identity=identity)


def handler(request: Request):
    """Catalyst entry point; deliberately never logs request or prompt content."""

    if request.path == "/health" and request.method == "GET":
        try:
            enabled = _hosted_ready(HostedSarvamConfig.from_env())
        except HostedSarvamError:
            enabled = False
        return _json_response({"status": "ok", "hosted_enabled": enabled})
    if request.method != "POST" or request.path not in {"/plan", "/sarvam"}:
        return _json_response({"error": {"code": "not_found", "message": "Route not found."}}, 404)
    if not _origin_allowed(request):
        return _json_response(
            {"error": {"code": "origin_denied", "message": "Origin not allowed."}}, 403
        )
    try:
        if request.path == "/sarvam":
            return _sarvam(request)
        return _plan(_payload(request, MAX_OFFLINE_BODY_BYTES))
    except HostedSarvamError as exc:
        return _json_response(
            {"error": {"code": exc.code, "message": exc.public_message}},
            exc.status,
            retry_after=exc.retry_after,
        )
    except HostedQuotaStoreError:
        return _json_response(
            {
                "error": {
                    "code": "quota_store_unavailable",
                    "message": "Hosted inference is temporarily unavailable. Offline planning remains available.",
                }
            },
            HTTPStatus.SERVICE_UNAVAILABLE,
        )
    except Exception:
        return _json_response(
            {
                "error": {
                    "code": "request_failed",
                    "message": "The request could not be completed.",
                }
            },
            HTTPStatus.BAD_GATEWAY,
        )
