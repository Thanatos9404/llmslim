"""Optional server-side error reporting for the website's Python functions.

Vercel does not turn files in ``api/`` that start with an underscore into functions, so this module
is shared code, not a route. Each function loads it by path and calls :func:`init` once.

Nothing happens unless ``SENTRY_DSN`` is set. When it is, ``sentry_sdk`` reports errors only: no
tracing, no default or auto-enabled integrations, no breadcrumbs, no local variables, no request
bodies and no personal data. :func:`scrub_event` runs on every event before it leaves the process
and removes request bodies, cookies, query strings and headers (credentials included), user data,
extra data and frame variables. It redacts quoted text, URLs and long token-like strings from
messages, because exception messages can echo submitted text, and replaces the value of every
secret-looking environment variable (``*_KEY``, ``*_SECRET``, ``*_TOKEN``, ``*_PASSWORD``, ``*_URI``,
``*_DSN``) wherever it appears in the event.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping, MutableMapping
from typing import Any
from urllib.parse import urlsplit, urlunsplit

# Headers kept on an event. Everything else is dropped, including Authorization, Cookie,
# X-Sarvam-API-Key and the forwarded-for headers.
SAFE_HEADERS = frozenset({"content-type", "content-length"})
_QUOTED = re.compile(r"([\"'`])(?:(?!\1).){1,400}\1", re.S)
_URL = re.compile(r"\b[a-z][a-z0-9+.-]*://\S+", re.I)
# API keys, tokens and hashes: long unbroken runs of letters, digits, "_" and "-".
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,}")
_SECRET_NAME = re.compile(r"(KEY|SECRET|TOKEN|PASSWORD|URI|DSN)$", re.I)
_MAX_MESSAGE = 200

_state: dict[str, Any] = {"sdk": None, "initialized": False}


def scrub_text(value: Any) -> Any:
    """Redact quoted fragments and URLs (credentials can sit in either) and cap the length."""

    if not isinstance(value, str):
        return value
    text = _URL.sub("[url]", _QUOTED.sub(r"\1[redacted]\1", value))
    return _TOKEN.sub("[redacted]", text)[:_MAX_MESSAGE]


def _secret_values(environ: Mapping[str, str]) -> list[str]:
    values = {
        value
        for name, value in environ.items()
        if _SECRET_NAME.search(name) and isinstance(value, str) and len(value) >= 8
    }
    return sorted(values, key=len, reverse=True)


def _redact(value: Any, secrets: list[str]) -> Any:
    if isinstance(value, str):
        for secret in secrets:
            if secret in value:
                value = value.replace(secret, "[redacted]")
        return value
    if isinstance(value, MutableMapping):
        for key in list(value):
            value[key] = _redact(value[key], secrets)
        return value
    if isinstance(value, list):
        return [_redact(item, secrets) for item in value]
    return value


def _bare_url(value: Any) -> Any:
    if not isinstance(value, str):
        return None
    try:
        parts = urlsplit(value)
    except ValueError:
        return None
    return urlunsplit((parts.scheme, parts.hostname or "", parts.path, "", ""))


def scrub_event(
    event: MutableMapping[str, Any],
    _hint: Any = None,
    *,
    environ: Mapping[str, str] | None = None,
) -> MutableMapping[str, Any]:
    """``before_send`` hook: keep the error type, stack and function tag; drop everything else."""

    for key in ("user", "extra", "breadcrumbs", "server_name"):
        event.pop(key, None)
    request = event.get("request")
    if isinstance(request, Mapping):
        headers = request.get("headers")
        safe: dict[str, Any] = {}
        if isinstance(headers, Mapping):
            safe = {
                str(name): value
                for name, value in headers.items()
                if str(name).lower() in SAFE_HEADERS
            }
        cleaned: dict[str, Any] = {}
        if isinstance(request.get("method"), str):
            cleaned["method"] = request["method"]
        url = _bare_url(request.get("url"))
        if url:
            cleaned["url"] = url
        if safe:
            cleaned["headers"] = safe
        event["request"] = cleaned
    if "message" in event:
        event["message"] = scrub_text(event["message"])
    logentry = event.get("logentry")
    if isinstance(logentry, MutableMapping):
        logentry.pop("params", None)
        for key in ("message", "formatted"):
            if key in logentry:
                logentry[key] = scrub_text(logentry[key])
    exception = event.get("exception")
    values = exception.get("values") if isinstance(exception, Mapping) else None
    for entry in values if isinstance(values, list) else ():
        if not isinstance(entry, MutableMapping):
            continue
        if "value" in entry:
            entry["value"] = scrub_text(entry["value"])
        stacktrace = entry.get("stacktrace")
        frames = stacktrace.get("frames") if isinstance(stacktrace, Mapping) else None
        for frame in frames if isinstance(frames, list) else ():
            if isinstance(frame, MutableMapping):
                frame.pop("vars", None)
    secrets = _secret_values(os.environ if environ is None else environ)
    return _redact(event, secrets) if secrets else event


def _drop_breadcrumb(_crumb: Any, _hint: Any = None) -> None:
    return None


def options(dsn: str, environ: Mapping[str, str]) -> dict[str, Any]:
    """The exact ``sentry_sdk.init`` arguments, kept separate so tests can assert them."""

    return {
        "dsn": dsn,
        "environment": environ.get("VERCEL_ENV") or "development",
        "release": environ.get("VERCEL_GIT_COMMIT_SHA") or None,
        "traces_sample_rate": 0.0,
        "send_default_pii": False,
        "include_local_variables": False,
        "max_request_body_size": "never",
        "max_breadcrumbs": 0,
        "default_integrations": False,
        "auto_enabling_integrations": False,
        "integrations": [],
        "before_send": scrub_event,
        "before_breadcrumb": _drop_breadcrumb,
    }


def init(environ: Mapping[str, str] | None = None) -> bool:
    """Initialise ``sentry_sdk`` once per process when ``SENTRY_DSN`` is set. Never raises."""

    if _state["initialized"]:
        return _state["sdk"] is not None
    env = os.environ if environ is None else environ
    dsn = (env.get("SENTRY_DSN") or "").strip()
    _state["initialized"] = True
    if not dsn:
        return False
    try:
        import sentry_sdk

        sentry_sdk.init(**options(dsn, env))
    except Exception:
        # Error reporting must never take a function down.
        return False
    _state["sdk"] = sentry_sdk
    return True


def capture(error: BaseException, *, function: str) -> None:
    """Report one unexpected error, tagged with the function name, and flush before the instance
    can be frozen. A no-op when Sentry is not configured. Never raises."""

    sdk = _state["sdk"]
    if sdk is None:
        return
    try:
        sdk.capture_exception(error, tags={"function": function})
        sdk.flush(timeout=2.0)
    except Exception:
        pass


def reset_for_tests() -> None:
    _state["sdk"] = None
    _state["initialized"] = False
