"""Host and Origin checks for LLMSlim's own HTTP servers (``llmslim serve`` and ``llmslim proxy``).

A server on the loopback interface is still reachable from any web page the user opens:

- **Cross-site requests.** A page can send a "simple" request (a POST with a ``text/plain`` body, say) to
  ``http://127.0.0.1:<port>``. It cannot read the answer, but the request runs: it can store a memory or start a
  long computation. Browsers name the page in the ``Origin`` header of every such request.
- **DNS rebinding.** A page on a hostname that first resolves to the attacker and then to ``127.0.0.1`` talks to the
  local server as its own origin, so it can read the answers too. Its requests carry that hostname in ``Host``.

So a local server answers only requests whose ``Host`` names this machine (or a host its operator allowed), and
refuses browser requests from any other origin. Non-browser clients send no ``Origin`` and are not affected.
"""

from __future__ import annotations

import ipaddress
from typing import Any, Awaitable, Callable, Iterable, Optional, Tuple
from urllib.parse import urlsplit

ANY_HOST = "*"


def host_name(value: str) -> str:
    """The host in a ``Host`` header value (``name``, ``name:port``, ``[v6]:port``), lower-case, without port."""
    value = value.strip().lower()
    if value.startswith("["):
        return value[1:].split("]", 1)[0]
    if value.count(":") > 1:  # a bare IPv6 address
        return value
    return value.rsplit(":", 1)[0] if ":" in value else value


def is_loopback_host(host: str) -> bool:
    """``localhost``, a ``*.localhost`` name (RFC 6761), 127.0.0.0/8 or ``::1``."""
    host = host.rstrip(".")
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class HostPolicy:
    """Which ``Host`` and ``Origin`` values a local server accepts.

    Args:
        allowed: Host names to accept besides the loopback ones (a port, if given, is ignored). ``"*"`` among them
            accepts any host and any origin, which turns the checks off.
        origins: Whether to refuse browser requests from other origins too. A server that requires an API key can
            skip it: a browser cannot attach the key to a cross-site request without a CORS preflight, which these
            servers never grant.
    """

    def __init__(self, allowed: Iterable[str] = (), *, origins: bool = True) -> None:
        names = {host_name(name) for name in allowed if name.strip()}
        self.any = ANY_HOST in names
        self.allowed = frozenset(names - {ANY_HOST})
        self.origins = origins

    def host_ok(self, host: Optional[str]) -> bool:
        if self.any:
            return True
        if not host:
            return False
        name = host_name(host)
        return is_loopback_host(name) or name in self.allowed

    def origin_ok(self, origin: Optional[str]) -> bool:
        """No ``Origin`` (not a browser) is fine; ``null`` and other sites are not."""
        if self.any or not self.origins or origin is None:
            return True
        try:
            parts = urlsplit(origin.strip())
            host = parts.hostname
        except ValueError:
            return False
        if parts.scheme not in ("http", "https") or not host:
            return False
        return is_loopback_host(host.lower()) or host.lower() in self.allowed


Reject = Callable[[str], Tuple[bytes, str]]


class HostGuard:
    """ASGI middleware: requests with another ``Host`` or a foreign ``Origin`` get a 403 and never reach the app.

    ``reject(message)`` returns the response body and its media type, so each server answers in its own error format.
    Use it with ``starlette.middleware.Middleware(HostGuard, policy=..., reject=...)``.
    """

    def __init__(self, app: Any, *, policy: HostPolicy, reject: Reject) -> None:
        self.app, self.policy, self.reject = app, policy, reject

    async def __call__(
        self,
        scope: Any,
        receive: Callable[[], Awaitable[Any]],
        send: Callable[[Any], Awaitable[None]],
    ) -> None:
        if scope["type"] != "http" or self.policy.any:
            await self.app(scope, receive, send)
            return
        headers: dict = {}
        for name, value in scope.get("headers", ()):
            headers.setdefault(name.decode("latin-1").lower(), value.decode("latin-1"))
        if not self.policy.host_ok(headers.get("host")):
            problem = "this server answers only requests addressed to this machine by name"
        elif not self.policy.origin_ok(headers.get("origin")):
            problem = "requests from other web pages are not allowed"
        else:
            await self.app(scope, receive, send)
            return
        body, media_type = self.reject(problem)
        await send(
            {
                "type": "http.response.start",
                "status": 403,
                "headers": [
                    (b"content-type", media_type.encode("latin-1")),
                    (b"content-length", str(len(body)).encode("latin-1")),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})
