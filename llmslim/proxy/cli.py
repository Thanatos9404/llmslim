"""``llmslim proxy`` and ``llmslim wrap``: run the tool-output proxy, or run a coding agent through it."""

from __future__ import annotations

import argparse
import json
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
# With a custom base URL, Claude Code stops deferring tools behind tool search and sends every tool definition on every
# request: about 7,100 more tokens per request on Claude Code 2.1.296. The proxy forwards tool_reference blocks
# unchanged, so keep tool search on unless the user chose otherwise.
AGENT_ENV = {"claude": {"ENABLE_TOOL_SEARCH": "true"}}
# Through a proxy, Claude Code can't fetch its feature flags, and `claude -p` then starts in auto permission mode
# instead of default: commands outside --allowedTools go to a classifier instead of being refused. Print-mode runs keep
# the default mode unless the user chose one, on the command line or in a settings file.
_MODE_CHOICES = (
    "--permission-mode",
    "--dangerously-skip-permissions",
    "--allow-dangerously-skip-permissions",
    "--settings",
)
_PROJECT_IGNORED_MODES = {
    "auto",
    "bypassPermissions",
}  # Claude Code ignores these in project and local settings
_MANAGED_SETTINGS = (
    Path("C:/Program Files/ClaudeCode/managed-settings.json"),
    Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
    Path("/etc/claude-code/managed-settings.json"),
)


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
    parser.add_argument(
        "--json",
        action="store_true",
        help="Also compress JSON output (off by default: agents given shortened JSON spent extra turns fetching "
        "the fields that were cut).",
    )


def _policy(args: argparse.Namespace) -> Policy:
    return Policy(
        min_tokens=args.min_tokens,
        keep_ratio=args.keep_ratio,
        min_keep=args.min_keep,
        tools=COMPRESSIBLE_TOOLS | frozenset(args.tool),
        mcp=args.mcp,
        never=frozenset(args.never),
        compress_json=args.json,
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
    parser.add_argument(
        "--allowed-host",
        action="append",
        default=[],
        metavar="HOST",
        help="A host name clients reach the proxy by, besides localhost, 127.0.0.1 and ::1 (repeatable). Requests "
        "to other names are refused, so a web page can't reach the proxy through DNS rebinding. With --allow-remote "
        "on another interface, every name is accepted unless you set this.",
    )
    _policy_arguments(parser)
    return parser


def build_stats_parser() -> argparse.ArgumentParser:
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
    return parser


def _stats(argv: Sequence[str]) -> int:
    args = build_stats_parser().parse_args(list(argv))
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
    allowed = args.allowed_host or ([] if _loopback(args.host) else ["*"])
    app = create_proxy_app(
        store=store, upstream=upstream, policy=_policy(args), allowed_hosts=allowed
    )
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


def _default_mode(path: Path) -> Optional[str]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    permissions = data.get("permissions") if isinstance(data, dict) else None
    mode = permissions.get("defaultMode") if isinstance(permissions, dict) else None
    return mode if isinstance(mode, str) and mode else None


def _mode_configured(cwd: Path, config_dir: Path) -> bool:
    """Whether a settings file Claude Code reads sets ``permissions.defaultMode``."""
    if any(_default_mode(path) for path in (*_MANAGED_SETTINGS, config_dir / "settings.json")):
        return True
    for name in ("settings.json", "settings.local.json"):
        mode = _default_mode(cwd / ".claude" / name)
        if mode and mode not in _PROJECT_IGNORED_MODES:
            return True
    return False


def claude_arguments(
    rest: Sequence[str], cwd: Optional[Path] = None, config_dir: Optional[Path] = None
) -> List[str]:
    """The arguments to start Claude Code with: ``rest``, plus ``--permission-mode default`` for a print-mode run whose
    user chose no mode, so the proxy doesn't move it from default to auto."""
    arguments = list(rest)
    options = arguments[: arguments.index("--")] if "--" in arguments else arguments
    if "-p" not in options and "--print" not in options:
        return arguments
    if any(a == flag or a.startswith(flag + "=") for a in options for flag in _MODE_CHOICES):
        return arguments
    cwd = cwd or Path.cwd()
    config_dir = config_dir or Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude")
    if _mode_configured(cwd, config_dir):
        return arguments
    return ["--permission-mode", "default", *arguments]


def build_wrap_parser() -> argparse.ArgumentParser:
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
    return parser


def wrap(argv: Optional[Sequence[str]] = None, *, runner: Any = subprocess.call) -> int:
    """``llmslim wrap claude [claude arguments...]``: run the agent with its API traffic through the proxy."""
    arguments = list(sys.argv[1:] if argv is None else argv)
    args, rest = build_wrap_parser().parse_known_args(arguments)
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
        for name, value in AGENT_ENV.get(args.agent, {}).items():
            env.setdefault(name, value)
        env[AGENTS[args.agent]] = f"http://127.0.0.1:{proxy.port}"
        if args.agent == "claude":
            rest = claude_arguments(rest)
        code = int(runner([executable, *rest], env=env))
    stats = store.stats(started)
    store.close()
    if stats["requests_changed"]:
        print("\nLLMSlim this session:\n" + _summary(stats), file=sys.stderr)
    return code


__all__: List[str] = ["build_parser", "build_stats_parser", "build_wrap_parser", "main", "wrap"]
