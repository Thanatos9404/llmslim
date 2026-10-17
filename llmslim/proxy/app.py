"""The proxy as an ASGI app: Anthropic API requests in, the same requests out, with tool output compressed.

Every request is forwarded to the upstream API with its headers, including the client's own credentials, which
this process never stores or logs. Only ``POST /v1/messages`` and ``POST /v1/messages/count_tokens`` bodies are
rewritten (see :mod:`llmslim.proxy.rewrite`); responses, including streamed ones, pass through untouched. If a
rewrite fails, the original body is forwarded, so the proxy never breaks a request it could not improve.
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Callable, Optional

from .rewrite import Policy, RewriteReport, rewrite_request
from .store import ProxyStore

__all__ = ["DEFAULT_UPSTREAM", "create_proxy_app"]

logger = logging.getLogger("llmslim.proxy")

DEFAULT_UPSTREAM = "https://api.anthropic.com"
REWRITTEN_PATHS = frozenset({"/v1/messages", "/v1/messages/count_tokens"})
# Hop-by-hop headers (RFC 9110) and the ones the proxy recomputes.
_DROP = frozenset(
    {
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "trailers",
        "transfer-encoding",
        "upgrade",
        "host",
        "content-length",
    }
)


def _missing_extra() -> ImportError:
    return ImportError(
        'The LLMSlim proxy needs Starlette, Uvicorn and httpx: pip install "llmslim[proxy]"'
    )


def describe(report: RewriteReport) -> str:
    return (
        f"compressed {report.compressed} new and replayed {report.replayed} tool outputs: "
        f"{report.tokens_before:,} -> {report.tokens_after:,} tokens ({report.saved:,} not sent)"
    )


def create_proxy_app(
    *,
    store: ProxyStore,
    upstream: str = DEFAULT_UPSTREAM,
    policy: Policy = Policy(),
    on_report: Optional[Callable[[RewriteReport], None]] = None,
    transport: Any = None,
) -> Any:
    """A Starlette app that forwards to ``upstream`` and compresses tool output in Messages requests.

    Args:
        store: Where first-sight decisions and savings are kept.
        upstream: The API to forward to, e.g. ``https://api.anthropic.com`` or your own gateway.
        policy: Which tool output to compress, and how far.
        on_report: Called with each request's :class:`RewriteReport` that changed something.
        transport: An ``httpx`` transport, for tests.
    """
    try:
        import httpx
        from starlette.applications import Starlette
        from starlette.background import BackgroundTask
        from starlette.concurrency import run_in_threadpool
        from starlette.requests import Request
        from starlette.responses import StreamingResponse
        from starlette.routing import Route
    except ImportError as error:  # pragma: no cover - exercised only without the extra
        raise _missing_extra() from error

    client = httpx.AsyncClient(
        base_url=upstream.rstrip("/"),
        timeout=httpx.Timeout(connect=15.0, read=None, write=120.0, pool=15.0),
        transport=transport,
        follow_redirects=False,
    )

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncIterator[None]:
        yield
        await client.aclose()

    async def rewritten(path: str, body: bytes) -> bytes:
        try:
            payload = json.loads(body)
        except ValueError:
            return body
        if not isinstance(payload, dict):
            return body
        try:
            new_payload, report = await run_in_threadpool(rewrite_request, payload, store, policy)
        except Exception:  # never break a request the proxy could not improve
            logger.warning(
                "LLMSlim proxy could not rewrite a request; forwarding it unchanged", exc_info=True
            )
            return body
        if not report.changed:
            return body
        if path == "/v1/messages":  # count_tokens previews the same request; count savings once
            await run_in_threadpool(store.record, report)
            logger.info("LLMSlim %s", describe(report))
            if on_report is not None:
                on_report(report)
        return json.dumps(new_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")

    async def forward(request: Request) -> StreamingResponse:
        path = request.url.path
        body = await request.body()
        if request.method == "POST" and path in REWRITTEN_PATHS and body:
            body = await rewritten(path, body)
        headers = [
            (name, value)
            for name, value in request.headers.raw
            if name.decode("latin-1").lower() not in _DROP
        ]
        upstream_request = client.build_request(
            request.method,
            httpx.URL(path=path, query=request.url.query.encode("latin-1")),
            headers=headers,
            content=body,
        )
        try:
            response = await client.send(upstream_request, stream=True)
        except httpx.HTTPError as error:
            logger.warning("LLMSlim proxy could not reach %s: %s", upstream, type(error).__name__)
            message = json.dumps(
                {
                    "type": "error",
                    "error": {
                        "type": "api_error",
                        "message": f"LLMSlim proxy could not reach {upstream}",
                    },
                }
            ).encode("utf-8")
            return StreamingResponse(
                iter([message]), status_code=502, media_type="application/json"
            )
        streamed = StreamingResponse(
            response.aiter_raw(),
            status_code=response.status_code,
            background=BackgroundTask(response.aclose),
        )
        streamed.raw_headers = [
            (name, value)
            for name, value in response.headers.raw
            if name.decode("latin-1").lower() not in _DROP
        ]
        return streamed

    methods = ["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD", "OPTIONS"]
    return Starlette(routes=[Route("/{path:path}", forward, methods=methods)], lifespan=lifespan)
