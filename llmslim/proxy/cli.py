"""``llmslim proxy`` and ``llmslim wrap``: run the tool-output proxy, or run a coding agent through it."""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, List, Optional, Sequence

from .app import DEFAULT_UPSTREAM, create_proxy_app
from .rewrite import COMPRESSIBLE_TOOLS, Policy
from .store import ProxyStore

DEFAULT_DB = Path.home() / ".llmslim" / "proxy.db"
DEFAULT_PORT = 8787
AGENTS = {"claude": "ANTHROPIC_BASE_URL"}


def _policy_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--db",
        default=os.environ.get("LLMSLIM_PROXY_DB") or str(DEFAULT_DB),
        help=f"Where first-sight decisions and savings are kept (default {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--min-tokens",
        type=int,
        default=1500,
        help="Leave tool output at or below this many tokens alone (default 1500).",
    )
    parser.add_argument(
        "--keep-ratio",
        type=float,
        default=0.35,
        help="Fraction of a long output to keep (default 0.35).",
    )
    parser.add_argument(
        "--min-keep",
        type=int,
        default=1000,
        help="Never shrink output below this many tokens (default 1000).",
    )
    parser.add_argument(
        "--tool",
        action="append",
        default=[],
        metavar="TOOL",
        help="Also compress this tool's output (repeatable).",
    )
    parser.add_argument(
        "--never",
        action="append",
        default=[],
        metavar="TOOL",
        help="Never compress this tool's output (repeatable).",
    )
    parser.add_argument(
        "--mcp",
        action="store_true",
        help="Also compress every MCP tool's output (off by default; or add data tools one by one with --tool).",
    )


def _policy(args: argparse.Namespace) -> Policy:
    return Policy(
        min_tokens=args.min_tokens,
        keep_ratio=args.keep_ratio,
        min_keep=args.min_keep,
        tools=COMPRESSIBLE_TOOLS | frozenset(args.tool),
        mcp=args.mcp,
        never=frozenset(args.never),
    )


def _upstream(explicit: Optional[str]) -> str:
    return (
        explicit
        or os.environ.get("LLMSLIM_PROXY_UPSTREAM")
        or os.environ.get("ANTHROPIC_BASE_URL")
        or DEFAULT_UPSTREAM
    )


def _points_at(upstream: str, host: str, port: int) -> bool:
    """Whether ``upstream`` is this proxy's own address (which would forward requests to itself forever)."""
    from urllib.parse import urlsplit

    parts = urlsplit(upstream)
    same_host = (
        parts.hostname in {host, "127.0.0.1", "localhost", "::1"}
        if _loopback(host)
        else parts.hostname == host
    )
    return bool(same_host and (parts.port or (443 if parts.scheme == "https" else 80)) == port)


def _loopback(host: str) -> bool:
    return host in ("127.0.0.1", "localhost", "::1")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="llmslim proxy",
        description="Forward Anthropic API requests and compress long tool output once, replaying the same bytes "
        "afterwards so prompt caching and thinking keep working. Subcommand: stats.",
    )
    parser.add_argument(
        "--host", default="127.0.0.1", help="Interface to bind (default 127.0.0.1)."
    )
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help=f"Port (default {DEFAULT_PORT})."
    )
    parser.add_argument(
        "--upstream", help=f"API to forward to (default $ANTHROPIC_BASE_URL or {DEFAULT_UPSTREAM})."
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow binding an interface other than loopback.",
    )
    _policy_arguments(parser)
    return parser


def _stats(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="llmslim proxy stats", description="Tokens the proxy kept out of requests."
    )
    parser.add_argument("--db", default=os.environ.get("LLMSLIM_PROXY_DB") or str(DEFAULT_DB))
    parser.add_argument("--days", type=float, help="Only the last N days.")
    parser.add_argument(
        "--price-per-mtok",
        type=float,
        help="Your input price in dollars per million tokens, to estimate dollars saved.",
    )
    args = parser.parse_args(list(argv))
    store = ProxyStore(args.db)
    since = datetime.now(timezone.utc).timestamp() - args.days * 86400 if args.days else None
    stats = store.stats(datetime.fromtimestamp(since, timezone.utc) if since else None)
    store.close()
    print(_summary(stats, args.price_per_mtok))
    return 0


def _summary(stats: dict, price_per_mtok: Optional[float] = None) -> str:
    lines = [
        f"Requests changed:   {stats['requests_changed']:,}",
        f"Outputs compressed: {stats['outputs_compressed']:,} (replayed {stats['outputs_replayed']:,} times)",
        f"Input tokens:       {stats['tokens_before']:,} -> {stats['tokens_after']:,}",
        f"Tokens not sent:    {stats['tokens_saved']:,}",
    ]
    if price_per_mtok is not None:
        dollars = stats["tokens_saved"] / 1_000_000 * price_per_mtok
        lines.append(
            f"At ${price_per_mtok:g}/MTok:     about ${dollars:,.2f} (before any prompt-caching discount)"
        )
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if arguments[:1] == ["stats"]:
        return _stats(arguments[1:])
    args = build_parser().parse_args(arguments)
    if not _loopback(args.host) and not args.allow_remote:
        raise SystemExit("refusing to bind beyond loopback without --allow-remote")
    try:
        import uvicorn
    except ImportError as error:  # pragma: no cover - exercised only without the extra
        raise SystemExit('The LLMSlim proxy needs: pip install "llmslim[proxy]"') from error
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    upstream = _upstream(args.upstream)
    if _points_at(upstream, args.host, args.port):
        raise SystemExit(
            f"the upstream {upstream} is this proxy itself; unset ANTHROPIC_BASE_URL or pass --upstream"
        )
    store = ProxyStore(args.db)
    app = create_proxy_app(store=store, upstream=upstream, policy=_policy(args))
    print(f"LLMSlim proxy on http://{args.host}:{args.port} -> {upstream}", file=sys.stderr)
    print(
        f"Point your agent at it: ANTHROPIC_BASE_URL=http://{args.host}:{args.port}",
        file=sys.stderr,
    )
    uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
    return 0


# ---------------------------------------------------------------------- wrap


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


class _BackgroundProxy:
    """The proxy on a free loopback port, in a thread of this process."""

    def __init__(self, app: Any) -> None:
        import uvicorn

        self.port = _free_port()
        self.server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning")
        )
        self.thread = threading.Thread(target=self.server.run, name="llmslim-proxy", daemon=True)

    def __enter__(self) -> "_BackgroundProxy":
        self.thread.start()
        deadline = time.monotonic() + 15
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise SystemExit("the LLMSlim proxy did not start")
            time.sleep(0.05)
        return self

    def __exit__(self, *exc: object) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=10)


def wrap(argv: Optional[Sequence[str]] = None, *, runner: Any = subprocess.call) -> int:
    """``llmslim wrap claude [claude arguments...]``: run the agent with its API traffic through the proxy."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    parser = argparse.ArgumentParser(
        prog="llmslim wrap",
        description="Run a coding agent with its API traffic through the LLMSlim proxy. "
        "Example: llmslim wrap claude -- --continue",
    )
    parser.add_argument("agent", choices=sorted(AGENTS), help="The agent to run.")
    parser.add_argument(
        "--upstream", help=f"API to forward to (default $ANTHROPIC_BASE_URL or {DEFAULT_UPSTREAM})."
    )
    _policy_arguments(parser)
    args, rest = parser.parse_known_args(arguments)
    if rest[:1] == ["--"]:
        rest = rest[1:]
    executable = shutil.which(args.agent)
    if executable is None:
        raise SystemExit(f"{args.agent} was not found on PATH")
    store = ProxyStore(args.db)
    started = datetime.now(timezone.utc)
    app = create_proxy_app(store=store, upstream=_upstream(args.upstream), policy=_policy(args))
    with _BackgroundProxy(app) as proxy:
        env = dict(os.environ)
        env[AGENTS[args.agent]] = f"http://127.0.0.1:{proxy.port}"
        code = int(runner([executable, *rest], env=env))
    stats = store.stats(started)
    store.close()
    if stats["requests_changed"]:
        print("\nLLMSlim this session:\n" + _summary(stats), file=sys.stderr)
    return code


__all__: List[str] = ["build_parser", "main", "wrap"]
