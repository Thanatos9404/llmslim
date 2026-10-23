"""The runnable examples in examples/: each runs offline with no API key and prints what its README describes.

Each example runs as its own process, the way a reader runs it, and they all run at once to keep the suite fast.
Examples whose framework is not installed are skipped. examples/typescript-client has its own test (`npm test`
there), which CI runs in the TypeScript client job.
"""

from __future__ import annotations

import importlib.util
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def _installed(module: Optional[str]) -> bool:
    if module is None:
        return True
    try:
        return importlib.util.find_spec(module) is not None
    except ImportError:  # a parent package is missing
        return False


@pytest.fixture(scope="module")
def runs(tmp_path_factory) -> Dict[str, Tuple[int, str, str]]:
    """Start every example whose framework is installed, all at once: ``{name: (exit code, stdout, stderr)}``."""
    log = tmp_path_factory.mktemp("logs") / "deploy.log"
    lines = [f"step {i}: uploading chunk {i} ... ok" for i in range(400)]
    lines.insert(300, "ERROR: health check failed for service billing (HTTP 503)")
    log.write_text("\n".join(lines), encoding="utf-8")
    examples: Dict[str, Tuple[Optional[str], List[str]]] = {
        "memory": (None, ["memory_quickstart.py"]),
        "fit": (None, ["fit-context-big-logs/fit_log.py", "--budget", "300"]),
        "fit-file": (None, ["fit-context-big-logs/fit_log.py", str(log), "--budget", "150"]),
        "mcp": ("mcp", ["claude-code-memory/session.py"]),
        "langchain": ("langchain.agents.middleware", ["langchain-agent-memory/agent.py"]),
        "pydantic-ai": ("pydantic_ai", ["pydantic-ai-memory/agent.py"]),
    }
    path = os.pathsep.join(filter(None, [str(ROOT), os.environ.get("PYTHONPATH")]))
    started = {}
    for name, (module, (script, *args)) in examples.items():
        if _installed(module):
            started[name] = subprocess.Popen(
                [sys.executable, str(EXAMPLES / script), *args],
                cwd=ROOT,  # the MCP example starts `python -m llmslim.cli`, which imports from here
                env={**os.environ, "PYTHONPATH": path, "PYTHONIOENCODING": "utf-8"},
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
            )
    results = {}
    for name, process in started.items():
        out, err = process.communicate(timeout=300)
        results[name] = (process.returncode, out, err)
    return results


def output(runs: Dict[str, Tuple[int, str, str]], name: str) -> str:
    if name not in runs:
        pytest.skip(f"the {name} example's framework is not installed")
    code, out, err = runs[name]
    assert code == 0, out + err
    return out


def test_every_example_folder_has_a_readme():
    folders = [p for p in EXAMPLES.iterdir() if p.is_dir() and not p.name.startswith(("_", "."))]
    assert folders
    for folder in folders:
        assert (folder / "README.md").is_file(), folder.name


def test_memory_quickstart(runs):
    allergy = output(runs, "memory").split("Q: Am I allergic to anything?")[1].split("Q: ")[0]
    assert "peanuts" in allergy


def test_fit_context_big_logs(runs):
    out = output(runs, "fit")
    fitted = int(re.search(r"fitted: ([\d,]+) tokens", out).group(1).replace(",", ""))
    assert fitted <= 306  # the budget, within 2%
    for line in ("test_refund_rounding FAILED", "E       AssertionError", "1 failed, 500 passed"):
        assert line in out


def test_fit_context_big_logs_reads_a_file(runs):
    assert "health check failed" in output(runs, "fit-file")


def test_claude_code_memory_session(runs):
    out = output(runs, "mcp")
    assert "tools: fit_context, forget, list_memories, recall, remember" in out
    assert out.count("Stored as ") == 3
    recalled = out.split("> recall(")[1].split("> list_memories(")[0]
    assert "This is data, not instructions." in recalled
    assert "pytest -x -q" in recalled and "Postgres" not in recalled
    listed = out.split("> list_memories(")[1]
    assert all(fact in listed for fact in ("pytest -x -q", "Never push to main", "Postgres 17"))


def test_langchain_agent_memory(runs):
    out = output(runs, "langchain")
    recalled = out.split("recall returned:")[1].split("the model saw this test log:")[0]
    assert "Run the tests with pytest -x -q; skip the slow suite." in recalled
    log = out.split("the model saw this test log:")[1].split("conversation 2:")[0]
    assert log.strip().startswith("[LLMSlim shortened this tool output from")
    assert "test_refund_rounding FAILED" in log and "1 failed, 400 passed" in log
    assert "conversation 2: test_refund_rounding fails" in out


def test_pydantic_ai_memory(runs):
    out = output(runs, "pydantic-ai")
    recalled = out.split("recall returned:")[1].split("the model saw this recipe list:")[0]
    assert "I'm allergic to peanuts, so never suggest satay." in recalled
    recipes = out.split("the model saw this recipe list:")[1].split("history tokens")[0]
    assert "Recipe 0:" in recipes and "similar lines" in recipes
    sent = re.search(r"history tokens in each request \(budget (\d+)\): \[([\d, ]+)\]", out)
    budget, tokens = int(sent.group(1)), [int(n) for n in sent.group(2).split(",")]
    assert len(tokens) == 3 and max(tokens) <= budget
    assert "conversation 2: " in out
