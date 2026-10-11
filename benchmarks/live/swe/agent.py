"""A minimal SWE-bench agent (mini-swe-agent style): Claude Haiku 5.5 with one bash tool in the official
per-task SWE-bench image. The two arms differ only in how a long command output is shortened before it
enters the history:

- ``baseline``: mini-swe-agent's head/tail cut of outputs over 10,000 characters.
- ``llmslim``:  LLMSlim compresses outputs over OBS_MIN_TOKENS, guided by the issue and the command.

The history is append-only (each output is filtered once, before it is added), so replayed thinking and
the prompt cache stay valid in both arms.
"""

from __future__ import annotations

import json
import subprocess
import time
import uuid
from pathlib import Path

import haiku_client as hc

MAX_STEPS = 60
TASK_CAP_USD = 0.40
CMD_TIMEOUT = 120
HEAD_TAIL_CHARS = 10_000
OBS_MIN_TOKENS = 800  # llmslim arm: outputs shorter than this pass through untouched
EAGER_MIN_TOKENS = (
    300  # llmslim_eager arm: a stress test, most file views and test runs get compressed
)
OBS_MAX_TOKENS = (
    2_500  # llmslim arm: never keep more than this (about the baseline's 10k characters)
)

SYSTEM = """You are an expert software engineer. A Python repository is checked out at /testbed.
Resolve the GitHub issue the user gives you by editing the repository's source code.

How to work:
- Use the bash tool to explore the code, reproduce the problem, edit files, and check your fix.
- Every command runs in a fresh shell in /testbed: `cd` and environment variables do not persist.
- Edit files with `sed -i`, a short Python script, or `cat <<'EOF' > file`. Never open an interactive editor or pager.
- Keep the change minimal and focused on non-test source files. Do not edit existing tests.
- Long outputs may be shortened. When you need exact lines, print a narrow range (`sed -n '120,160p' path`) or use `grep -n`.
- When the fix is complete, call the `submit` tool. Do not stop without calling it."""

TOOLS = [
    {
        "name": "bash",
        "description": "Run one bash command in /testbed and return its output and exit code.",
        "input_schema": {
            "type": "object",
            "properties": {"command": {"type": "string", "description": "The command to run."}},
            "required": ["command"],
        },
    },
    {
        "name": "submit",
        "description": "Finish: your current changes to the repository are the final answer.",
        "input_schema": {"type": "object", "properties": {}},
    },
]


def image_for(instance_id: str) -> str:
    return (
        f"docker.io/swebench/sweb.eval.x86_64.{instance_id.replace('__', '_1776_')}:latest".lower()
    )


class Container:
    def __init__(self, instance_id: str):
        self.name = f"llmslim-swe-{uuid.uuid4().hex[:10]}"
        subprocess.run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                self.name,
                "-w",
                "/testbed",
                image_for(instance_id),
                "sleep",
                "7200",
            ],
            check=True,
            capture_output=True,
            timeout=900,
        )

    def run(self, command: str, timeout: int = CMD_TIMEOUT) -> tuple[str, int]:
        script = f"source /opt/miniconda3/bin/activate testbed >/dev/null 2>&1; cd /testbed; export PAGER=cat GIT_PAGER=cat TQDM_DISABLE=1; {command}"
        try:
            done = subprocess.run(
                ["docker", "exec", self.name, "timeout", str(timeout), "bash", "-c", script],
                capture_output=True,
                timeout=timeout + 30,
            )
            output = (done.stdout + done.stderr).decode("utf-8", errors="replace")
            return output, done.returncode
        except subprocess.TimeoutExpired:
            return f"The command timed out after {timeout} seconds.", 124

    def close(self) -> None:
        subprocess.run(["docker", "rm", "-f", self.name], capture_output=True, timeout=120)


# ------------------------------------------------------------------ observation filters


def head_tail(text: str) -> tuple[str, dict]:
    if len(text) <= HEAD_TAIL_CHARS:
        return text, {}
    half = HEAD_TAIL_CHARS // 2
    note = f"\n\n[output too long: {len(text):,} characters; showing the first and last {half:,}. Use head, tail, sed -n or grep for the rest]\n\n"
    return text[:half] + note + text[-half:], {"cut": True}


def llmslim_filter(text: str, query: str, floor: int = OBS_MIN_TOKENS) -> tuple[str, dict]:
    from llmslim import compress
    from llmslim.tokens import count_tokens

    tokens = count_tokens(text)
    if tokens <= floor:
        return text, {}
    budget = min(OBS_MAX_TOKENS, max(floor, int(tokens * 0.3)))
    started = time.perf_counter()
    result = compress(text, target_ratio=budget / tokens, query=query)
    ms = (time.perf_counter() - started) * 1000
    note = f"\n\n[output compressed by LLMSlim from {tokens:,} to about {result.compressed_tokens:,} tokens. Use sed -n or grep -n for exact lines]\n"
    return result.compressed_text + note, {
        "compressed": True,
        "from": tokens,
        "to": result.compressed_tokens,
        "ms": round(ms),
    }


# ------------------------------------------------------------------ the loop


def solve(instance: dict, arm: str, api, log_dir: Path) -> dict:
    issue = instance["problem_statement"]
    first = {
        "role": "user",
        "content": [
            {
                "type": "text",
                "text": f"<issue>\n{issue}\n</issue>\n\nResolve this issue in /testbed.",
            }
        ],
    }
    messages = [first]
    stats = {
        "instance_id": instance["instance_id"],
        "arm": arm,
        "steps": 0,
        "usd": 0.0,
        "input": 0,
        "cache_write": 0,
        "cache_read": 0,
        "output": 0,
        "max_prompt": 0,
        "obs_events": [],
        "exit": "step_limit",
        "error": None,
    }
    container = Container(instance["instance_id"])
    try:
        for step in range(MAX_STEPS):
            # Cache the whole prefix: one breakpoint on the newest block (moving it keeps thinking valid).
            last = messages[-1]["content"][-1]
            last["cache_control"] = {"type": "ephemeral"}
            response, _, usd = hc.call(
                api,
                max_tokens=8192,
                output_config={"effort": "medium"},
                system=SYSTEM,
                tools=TOOLS,
                messages=messages,
            )
            del last["cache_control"]
            u = response.usage
            stats["steps"] += 1
            stats["usd"] += usd
            stats["input"] += u.input_tokens
            stats["output"] += u.output_tokens
            stats["cache_write"] += u.cache_creation_input_tokens or 0
            stats["cache_read"] += u.cache_read_input_tokens or 0
            stats["max_prompt"] = max(stats["max_prompt"], hc.prompt_tokens(u))
            messages.append(
                {
                    "role": "assistant",
                    "content": [block.model_dump(exclude_none=True) for block in response.content],
                }
            )
            if response.stop_reason == "refusal":
                stats["exit"] = "refusal"
                break
            calls = [b for b in response.content if b.type == "tool_use"]
            if not calls:
                messages.append(
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": "Continue with the bash tool, or call submit when the fix is complete.",
                            }
                        ],
                    }
                )
                continue
            results, submitted = [], False
            thought = " ".join(b.text for b in response.content if b.type == "text")[-600:]
            for call in calls:
                if call.name == "submit":
                    submitted = True
                    results.append(
                        {"type": "tool_result", "tool_use_id": call.id, "content": "Submitted."}
                    )
                    continue
                command = str(call.input.get("command", ""))
                output, code = container.run(command)
                raw = f"{output}\n[exit code {code}]"
                if arm in ("llmslim", "llmslim_eager"):
                    floor = OBS_MIN_TOKENS if arm == "llmslim" else EAGER_MIN_TOKENS
                    shown, event = llmslim_filter(
                        raw, query=f"{issue[:1500]}\n{thought}\n$ {command}", floor=floor
                    )
                else:
                    shown, event = head_tail(raw)
                if event:
                    stats["obs_events"].append({"step": step, "chars": len(raw), **event})
                results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": call.id,
                        "content": shown or "(no output)",
                    }
                )
            messages.append({"role": "user", "content": results})
            if submitted:
                stats["exit"] = "submitted"
                break
            if stats["usd"] >= TASK_CAP_USD:
                stats["exit"] = "cost_limit"
                break
        patch, _ = container.run("git add -A >/dev/null 2>&1; git diff --cached --text", timeout=60)
    except hc.BudgetExceeded:
        raise
    except Exception as error:  # noqa: BLE001 - one task failing must not stop the run
        stats["error"] = f"{type(error).__name__}: {error}"[:500]
        patch = ""
    finally:
        container.close()
    stats["usd"] = round(stats["usd"], 5)
    stats["patch_lines"] = patch.count("\n")
    (log_dir / f"{instance['instance_id']}.{arm}.json").write_text(
        json.dumps({"stats": stats, "messages": messages}, default=str)
    )
    return {
        "instance_id": instance["instance_id"],
        "model_name_or_path": f"haiku-5.5+{arm}",
        "model_patch": patch,
        "stats": stats,
    }
