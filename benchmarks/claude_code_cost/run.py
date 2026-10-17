"""Run Claude Code on a fixture with and without `llmslim wrap claude`, and record what each run was billed.

Claude Code reads ANTHROPIC_API_KEY (and, if your key needs them, ANTHROPIC_CUSTOM_HEADERS) from the environment. Each
run gets a fresh copy of the fixture and its own empty Claude Code config directory, so your settings, CLAUDE.md files
and MCP servers take no part. The two arms alternate (plain first on even runs, llmslim first on odd runs).

Usage: python run.py --task one-bug --runs 6 --out results/one-bug.jsonl
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

HERE = Path(__file__).resolve().parent
MODEL = "claude-haiku-5-5"
# Claude Haiku 5.5 list prices in USD per million tokens, for prompts up to 100K tokens: input $0.10, output $0.50.
# Cache reads cost 0.1x input; cache writes 1.25x (5-minute) or 2x (1-hour).
PRICE_IN, PRICE_OUT = 0.10, 0.50

from tasks import TASKS  # noqa: E402


def digest(folder: Path) -> str:
    h = hashlib.sha256()
    for path in sorted(folder.rglob("*.py")):
        h.update(path.relative_to(folder).as_posix().encode())
        h.update(path.read_bytes())
    return h.hexdigest()


def billed_usd(usage: dict) -> float:
    """List-price cost of one usage record, with cache reads and writes priced separately."""
    creation = usage.get("cache_creation") or {}
    one_hour = creation.get("ephemeral_1h_input_tokens") or 0
    five_minute = (usage.get("cache_creation_input_tokens") or 0) - one_hour
    tokens = (
        (usage.get("input_tokens") or 0) * PRICE_IN
        + five_minute * PRICE_IN * 1.25
        + one_hour * PRICE_IN * 2
        + (usage.get("cache_read_input_tokens") or 0) * PRICE_IN * 0.10
        + (usage.get("output_tokens") or 0) * PRICE_OUT
    )
    return tokens / 1_000_000


def last_json(text: str) -> dict:
    for line in reversed(text.strip().splitlines()):
        line = line.strip()
        if line.startswith("{"):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return {}


def permission_mode(config: Path):
    """The permission mode Claude Code recorded for the session, from its transcript."""
    for path in (config / "projects").rglob("*.jsonl"):
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            if '"permissionMode"' in line:
                try:
                    return json.loads(line).get("permissionMode")
                except json.JSONDecodeError:
                    continue
    return None


def run_once(task: str, arm: str, index: int, args) -> dict:
    root = Path(args.workdir).resolve()
    work = root / f"{task}-{index}-{arm}" / "project"
    config = work.parent / "claude-config"
    shutil.rmtree(work.parent, ignore_errors=True)
    config.mkdir(parents=True)
    spec = TASKS[task]
    spec.write(work)
    tests_before = digest(work / "tests") if (work / "tests").exists() else None

    env = dict(
        os.environ, CLAUDE_CONFIG_DIR=str(config), CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC="1"
    )
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    claude_args = [
        "-p",
        spec.prompt,
        "--model",
        MODEL,
        "--output-format",
        "json",
        "--max-turns",
        str(args.max_turns),
    ]
    if args.permission_mode:
        claude_args += ["--permission-mode", args.permission_mode]
    claude_args += ["--allowedTools", *spec.allowed_tools()]
    db = config / "proxy.db"
    if arm == "llmslim":
        command = [args.llmslim, "wrap", "--db", str(db), "claude", "--", *claude_args]
    else:
        command = [args.claude, *claude_args]

    started = time.time()
    try:
        proc = subprocess.run(
            command,
            cwd=work,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=args.timeout,
            stdin=subprocess.DEVNULL,
        )
        exit_code, stdout = proc.returncode, proc.stdout
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or ""
        exit_code, stdout = (
            "timeout",
            out if isinstance(out, str) else out.decode("utf-8", "replace"),
        )
    seconds = round(time.time() - started, 1)
    result = last_json(stdout)

    try:
        passed = bool(spec.check(work))
    except Exception as exc:  # a crashed check is a failed run
        passed = False
        print(f"check failed with {exc!r}", flush=True)
    record = {
        "task": task,
        "arm": arm,
        "run": index,
        "exit_code": exit_code,
        "seconds": seconds,
        "is_error": result.get("is_error"),
        "subtype": result.get("subtype"),
        "num_turns": result.get("num_turns"),
        "usage": result.get("usage"),
        "model_usage": result.get("modelUsage"),
        "claude_code_cost_usd": result.get("total_cost_usd"),
        "permission_mode": permission_mode(config),
        "billed_usd": None,
        "other_models": [],
        "tests_pass": passed,
        "tests_unchanged": tests_before is None or digest(work / "tests") == tests_before,
        "final_reply": (result.get("result") or "")[:400],
        "proxy_stats": None,
    }
    model_usage = result.get("modelUsage") or {}
    if model_usage:
        record["billed_usd"] = round(
            sum(
                billed_usd(
                    {
                        "input_tokens": u.get("inputTokens"),
                        "output_tokens": u.get("outputTokens"),
                        "cache_read_input_tokens": u.get("cacheReadInputTokens"),
                        "cache_creation_input_tokens": u.get("cacheCreationInputTokens"),
                    }
                )
                for name, u in model_usage.items()
                if name.startswith(MODEL)
            ),
            6,
        )
        record["other_models"] = sorted(name for name in model_usage if not name.startswith(MODEL))
    elif result.get("usage"):
        record["billed_usd"] = round(billed_usd(result["usage"]), 6)
    if arm == "llmslim" and db.exists():
        stats = subprocess.run(
            [args.llmslim, "proxy", "stats", "--db", str(db)], capture_output=True, text=True
        )
        record["proxy_stats"] = stats.stdout.strip()
    return record


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--task", choices=sorted(TASKS), required=True)
    parser.add_argument("--runs", type=int, default=6)
    parser.add_argument("--out", required=True)
    parser.add_argument("--workdir", default=str(HERE / "work"))
    parser.add_argument("--claude", default=shutil.which("claude") or "claude")
    parser.add_argument("--llmslim", default=shutil.which("llmslim") or "llmslim")
    parser.add_argument(
        "--permission-mode",
        help="Pass the same --permission-mode to Claude Code in both arms. Claude Code picks a different default "
        "when ANTHROPIC_BASE_URL points at a local proxy (auto instead of default on our account), which changes what "
        "the agent may run.",
    )
    parser.add_argument("--max-turns", type=int, default=40)
    parser.add_argument("--timeout", type=int, default=900)
    parser.add_argument(
        "--cap-usd",
        type=float,
        default=10.0,
        help="Stop once the runs so far were billed this much.",
    )
    args = parser.parse_args()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("set ANTHROPIC_API_KEY first")

    version = subprocess.run(
        [args.claude, "--version"], capture_output=True, text=True
    ).stdout.strip()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    for index in range(args.runs):
        for arm in ("plain", "llmslim") if index % 2 == 0 else ("llmslim", "plain"):
            record = run_once(args.task, arm, index, args)
            record["claude_code_version"] = version
            spent += record["billed_usd"] or 0
            with out.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(record) + "\n")
            print(
                f"{args.task} run {index} {arm:7} turns={record['num_turns']} billed=${record['billed_usd']} "
                f"pass={record['tests_pass']} tests_unchanged={record['tests_unchanged']} {record['seconds']}s",
                flush=True,
            )
            if spent >= args.cap_usd:
                print(f"stopping: ${spent:.2f} reached the cap", flush=True)
                return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
