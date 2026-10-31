"""``llmslim serve``: LLMSlim memory and context over HTTP, for apps in any language.

``pip install "llmslim[server]"`` and run ``llmslim serve``. One process and one SQLite file, no model calls. The
JSON API mirrors :class:`llmslim.memory.Memory`:

====================================  =====================================================================
``POST   /v1/memories``               store messages verbatim (``messages``, ``user_id``/``agent_id``/``run_id``)
``GET    /v1/memories``               list a scope's messages, oldest first (``?user_id=...&limit=&offset=``)
``GET    /v1/memories/{id}``          one message
``PATCH  /v1/memories/{id}``          correct its ``content`` or ``metadata``
``DELETE /v1/memories/{id}``          delete one message
``DELETE /v1/memories?user_id=...``   delete a whole scope
``POST   /v1/memories/search``        the messages that answer ``query`` within ``budget`` tokens (``explain`` says why)
``POST   /v1/context/fit``            shrink ``text`` to ``budget`` tokens around an optional ``query``
``GET    /healthz``                   liveness, without authentication
====================================  =====================================================================

Every ``/v1`` route needs ``Authorization: Bearer <key>`` when API keys are configured (``--api-key`` or
``LLMSLIM_API_KEYS``). Without keys the server only binds to the loopback interface. Keys give full access to every
scope, so call the server from your backend, never from a browser.
"""

from __future__ import annotations

import argparse
import hmac
import ipaddress
import json
import logging
import os
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Mapping, Optional, Sequence, TypedDict

from ._fit import fit_text
from .memory import Memory
from .memory._core import storage_target
from .tokens import count_tokens

logger = logging.getLogger("llmslim.server")

DEFAULT_DB = Path.home() / ".llmslim" / "memory.db"
DEFAULT_PORT = 8080
MAX_BODY_BYTES = 1_000_000
MAX_BUDGET = 100_000
MAX_LIST = 1_000
MIN_KEY_LENGTH = 16
_SCOPE_KEYS = ("user_id", "agent_id", "run_id")
_RELEVANCE = ("lexical", "semantic")


class _HTTPError(Exception):
    def __init__(self, status: int, kind: str, message: str) -> None:
        super().__init__(message)
        self.status, self.kind, self.message = status, kind, message


def _missing_server_extra() -> ImportError:
    return ImportError(
        'The LLMSlim server needs Starlette and Uvicorn: pip install "llmslim[server]"'
    )


def create_app(
    memory: Memory,
    *,
    api_keys: Sequence[str] = (),
    max_body_bytes: int = MAX_BODY_BYTES,
    max_budget: int = MAX_BUDGET,
) -> Any:
    """A Starlette app that serves ``memory`` over the JSON API above.

    Args:
        memory: The memory to serve, e.g. ``Memory("memory.db")``.
        api_keys: Bearer keys that may call ``/v1``. Empty means no authentication: only for loopback use.
        max_body_bytes: Largest request body accepted (413 above it).
        max_budget: Largest token budget a request may ask for.
    """
    try:
        from starlette.applications import Starlette
        from starlette.concurrency import run_in_threadpool
        from starlette.requests import Request
        from starlette.responses import JSONResponse
        from starlette.routing import Route
    except ImportError as error:  # pragma: no cover - exercised only without the extra
        raise _missing_server_extra() from error

    from . import __version__

    keys = [key.encode("utf-8") for key in api_keys]

    def authorized(request: Request) -> bool:
        if not keys:
            return True
        scheme, _, token = request.headers.get("authorization", "").partition(" ")
        presented = token.strip().encode("utf-8")
        # Compare against every key, so the time taken doesn't reveal which one nearly matched.
        matches = [hmac.compare_digest(presented, key) for key in keys]
        return scheme.lower() == "bearer" and any(matches)

    async def body(request: Request) -> Dict[str, Any]:
        declared = request.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_body_bytes:
            raise _HTTPError(
                413, "payload_too_large", f"request body is over {max_body_bytes} bytes"
            )
        raw = b""
        async for chunk in request.stream():
            raw += chunk
            if len(raw) > max_body_bytes:
                raise _HTTPError(
                    413, "payload_too_large", f"request body is over {max_body_bytes} bytes"
                )
        try:
            payload = json.loads(raw or b"{}")
        except ValueError as error:
            raise _HTTPError(
                400, "invalid_json", f"request body is not valid JSON: {error}"
            ) from error
        if not isinstance(payload, dict):
            raise _HTTPError(400, "invalid_request", "request body must be a JSON object")
        return payload

    def budget_of(value: Any, default: int) -> int:
        if value is None:
            return default
        if isinstance(value, bool) or not isinstance(value, int) or not 1 <= value <= max_budget:
            raise _HTTPError(
                400, "invalid_request", f"budget must be a whole number from 1 to {max_budget}"
            )
        return value

    def endpoint(
        handler: Callable[[Request], Awaitable[Any]], status: int = 200
    ) -> Callable[[Request], Awaitable[JSONResponse]]:
        async def run(request: Request) -> JSONResponse:
            if not authorized(request):
                return JSONResponse(
                    {"error": {"type": "unauthorized", "message": "missing or invalid API key"}},
                    status_code=401,
                    headers={"WWW-Authenticate": "Bearer"},
                )
            try:
                return JSONResponse(await handler(request), status_code=status)
            except _HTTPError as error:
                return JSONResponse(
                    {"error": {"type": error.kind, "message": error.message}}, error.status
                )
            except ImportError as error:
                return JSONResponse({"error": {"type": "unavailable", "message": str(error)}}, 501)
            except ValueError as error:
                return JSONResponse(
                    {"error": {"type": "invalid_request", "message": str(error)}}, 400
                )

        return run

    async def add(request: Request) -> Dict[str, Any]:
        payload = await body(request)
        if "messages" not in payload:
            raise _HTTPError(400, "invalid_request", "messages is required")
        metadata = payload.get("metadata")
        if metadata is not None and not isinstance(metadata, dict):
            raise _HTTPError(400, "invalid_request", "metadata must be an object")
        items = await run_in_threadpool(
            memory.add,
            payload["messages"],
            timestamp=payload.get("timestamp"),
            metadata=metadata,
            **_scope(payload),
        )
        return {"items": [item.to_dict() for item in items]}

    async def list_items(request: Request) -> Dict[str, Any]:
        query = request.query_params
        limit = _bounded(query.get("limit"), "limit", 100, 1, MAX_LIST)
        offset = _bounded(query.get("offset"), "offset", 0, 0, 10**9)
        items = await run_in_threadpool(
            memory.get_all, since=query.get("since"), until=query.get("until"), **_scope(query)
        )
        page = items[offset : offset + limit]
        return {
            "items": [item.to_dict() for item in page],
            "total": len(items),
            "offset": offset,
            "limit": limit,
        }

    async def get_item(request: Request) -> Dict[str, Any]:
        item = await run_in_threadpool(memory.get, request.path_params["memory_id"])
        if item is None:
            raise _HTTPError(404, "not_found", "no stored message has that id")
        return item.to_dict()

    async def update_item(request: Request) -> Dict[str, Any]:
        payload = await body(request)
        content, metadata = payload.get("content"), payload.get("metadata")
        if content is None and metadata is None:
            raise _HTTPError(400, "invalid_request", "send content, metadata or both")
        if content is not None and not isinstance(content, str):
            raise _HTTPError(400, "invalid_request", "content must be text")
        if metadata is not None and not isinstance(metadata, dict):
            raise _HTTPError(400, "invalid_request", "metadata must be an object")
        item = await run_in_threadpool(
            memory.update, request.path_params["memory_id"], content, metadata=metadata
        )
        if item is None:
            raise _HTTPError(404, "not_found", "no stored message has that id")
        return item.to_dict()

    async def delete_item(request: Request) -> Dict[str, Any]:
        if not await run_in_threadpool(memory.delete, request.path_params["memory_id"]):
            raise _HTTPError(404, "not_found", "no stored message has that id")
        return {"deleted": 1}

    async def delete_scope(request: Request) -> Dict[str, Any]:
        scope = _scope(request.query_params)
        if not scope:
            raise _HTTPError(
                400, "invalid_request", "name the scope to delete: user_id, agent_id or run_id"
            )
        return {"deleted": await run_in_threadpool(memory.delete_all, **scope)}

    async def search(request: Request) -> Dict[str, Any]:
        payload = await body(request)
        relevance = payload.get("relevance")
        if relevance is not None and relevance not in _RELEVANCE:
            raise _HTTPError(
                400, "invalid_request", f"relevance must be one of {', '.join(_RELEVANCE)}"
            )
        explain = payload.get("explain")
        if explain is not None and not isinstance(explain, bool):
            raise _HTTPError(400, "invalid_request", "explain must be true or false")
        context = await run_in_threadpool(
            lambda: memory.search(
                payload.get("query", ""),
                budget=budget_of(payload.get("budget"), memory.budget),
                relevance=relevance,
                since=payload.get("since"),
                until=payload.get("until"),
                explain=bool(explain),
                **_scope(payload),
            )
        )
        return context.to_dict()

    async def fit(request: Request) -> Dict[str, Any]:
        payload = await body(request)
        text, query = payload.get("text"), payload.get("query")
        if not isinstance(text, str):
            raise _HTTPError(400, "invalid_request", "text must be a string")
        if query is not None and not isinstance(query, str):
            raise _HTTPError(400, "invalid_request", "query must be a string")
        budget = budget_of(payload.get("budget"), 2000)
        fitted = await run_in_threadpool(fit_text, text, budget, query)
        return {
            "text": fitted,
            "tokens": count_tokens(fitted),
            "original_tokens": count_tokens(text),
        }

    async def info(request: Request) -> Dict[str, Any]:
        return {
            "name": "llmslim",
            "version": __version__,
            "budget": memory.budget,
            "max_budget": max_budget,
        }

    async def health(request: Request) -> JSONResponse:
        return JSONResponse({"status": "ok"})

    async def memories(request: Request) -> JSONResponse:
        if request.method == "POST":
            return await endpoint(add, 201)(request)
        if request.method == "DELETE":
            return await endpoint(delete_scope)(request)
        return await endpoint(list_items)(request)

    async def memory_item(request: Request) -> JSONResponse:
        handler = {"GET": get_item, "PATCH": update_item, "DELETE": delete_item}[request.method]
        return await endpoint(handler)(request)

    routes = [
        Route("/healthz", health, methods=["GET"]),
        Route("/v1/info", endpoint(info), methods=["GET"]),
        Route("/v1/memories", memories, methods=["GET", "POST", "DELETE"]),
        Route("/v1/memories/search", endpoint(search), methods=["POST"]),
        Route("/v1/memories/{memory_id}", memory_item, methods=["GET", "PATCH", "DELETE"]),
        Route("/v1/context/fit", endpoint(fit), methods=["POST"]),
    ]
    return Starlette(routes=routes)


class _Scope(TypedDict, total=False):
    user_id: str
    agent_id: str
    run_id: str


def _scope(source: Mapping[str, Any]) -> _Scope:
    scope: _Scope = {}
    for key in _SCOPE_KEYS:
        value = source.get(key)
        if value is None or value == "":
            continue
        if not isinstance(value, str):
            raise _HTTPError(400, "invalid_request", f"{key} must be a string")
        scope[key] = value  # type: ignore[literal-required]
    return scope


def _bounded(value: Optional[str], name: str, default: int, low: int, high: int) -> int:
    if value is None:
        return default
    if not value.isdigit() or not low <= int(value) <= high:
        raise _HTTPError(
            400, "invalid_request", f"{name} must be a whole number from {low} to {high}"
        )
    return int(value)


def is_loopback(host: str) -> bool:
    """True for hosts only this machine can reach: localhost, 127.0.0.0/8 and ::1."""
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host.strip("[]")).is_loopback
    except ValueError:
        return False


def api_keys_from(values: Sequence[str], environ: Mapping[str, str] = os.environ) -> List[str]:
    """API keys from ``--api-key`` flags, else from ``LLMSLIM_API_KEYS`` (comma-separated)."""
    raw = list(values) or environ.get("LLMSLIM_API_KEYS", "").split(",")
    keys = [key.strip() for key in raw if key.strip()]
    short = [key for key in keys if len(key) < MIN_KEY_LENGTH]
    if short:
        raise ValueError(
            f"API keys must be at least {MIN_KEY_LENGTH} characters; generate one with: llmslim serve --new-key"
        )
    return keys


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmslim serve", description="Serve LLMSlim memory and context over HTTP."
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("LLMSLIM_HOST", "127.0.0.1"),
        help="Interface to bind (default 127.0.0.1).",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("LLMSLIM_PORT", DEFAULT_PORT)),
        help=f"Port (default {DEFAULT_PORT}).",
    )
    parser.add_argument(
        "--db",
        default=os.environ.get("LLMSLIM_MEMORY_DB") or str(DEFAULT_DB),
        help=f"SQLite file or postgresql:// URL for the memory (env LLMSLIM_MEMORY_DB; default {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--api-key",
        action="append",
        default=[],
        help="A bearer key clients must send; repeat for several (env LLMSLIM_API_KEYS, comma-separated).",
    )
    parser.add_argument(
        "--budget", type=int, default=2000, help="Default token budget for search (default 2000)."
    )
    parser.add_argument(
        "--new-key", action="store_true", help="Print a new random API key and exit."
    )
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(list(argv) if argv is not None else None)
    if args.new_key:
        import secrets

        print(secrets.token_urlsafe(32))
        return 0
    if args.budget <= 0:
        raise SystemExit("--budget must be a positive number of tokens")
    try:
        keys = api_keys_from(args.api_key)
    except ValueError as error:
        raise SystemExit(str(error)) from error
    if not keys and not is_loopback(args.host):
        raise SystemExit(
            f"refusing to serve on {args.host} without an API key: set LLMSLIM_API_KEYS or pass --api-key "
            "(make one with: llmslim serve --new-key)"
        )
    try:
        import uvicorn
    except ImportError as error:  # pragma: no cover - exercised only without the extra
        raise _missing_server_extra() from error
    app = create_app(Memory(storage_target(args.db), budget=args.budget), api_keys=keys)
    if not keys:
        logger.warning("no API key set: serving %s:%s without authentication", args.host, args.port)
    uvicorn.run(app, host=args.host, port=args.port)
    return 0


__all__ = ["create_app", "main"]

if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
