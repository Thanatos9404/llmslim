"""Tasks for the Claude Code cost benchmark: a fixture writer, a prompt and a pass/fail check for each.

Every fixture is deterministic. Tool output is kept under the roughly 30 KB at which Claude Code saves output to a file
instead of showing it to the model. Checks run after the agent finishes and never trust what the agent says.
"""

from __future__ import annotations

import json
import random
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List

import make_fixture

BASE_TOOLS = ["Read", "Edit", "Write", "Grep", "Glob", "Bash(ls:*)", "Bash(cat:*)"]


@dataclass
class Task:
    name: str
    prompt: str
    write: Callable[[Path], None]
    check: Callable[[Path], bool]
    commands: List[str] = field(
        default_factory=list
    )  # extra Bash/PowerShell prefixes the agent may run

    def allowed_tools(self) -> List[str]:
        rules = list(BASE_TOOLS)
        for command in self.commands:
            rules += [f"Bash({command}:*)", f"PowerShell({command}:*)"]
        return rules


def _run(dest: Path, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, *args], cwd=dest, capture_output=True, text=True, timeout=300
    )


def _tests_pass(dest: Path) -> bool:
    return _run(dest, "-m", "pytest", "-q", "-p", "no:cacheprovider").returncode == 0


def _write_files(dest: Path, files: Dict[str, str]) -> None:
    for name, text in files.items():
        path = dest / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8", newline="\n")


# --- pytest tasks ----------------------------------------------------------------------------------------------------

DISCOUNT_BUGGY = '''def discount_cents(total_cents: int, percent: int) -> int:
    """Discount on a total, in cents, for a whole-number percent; never more than the total."""
    return total_cents * percent // 10
'''
DISCOUNT_TEST = """from billing.discount import discount_cents


def test_ten_percent():
    assert discount_cents(2_000, 10) == 200


def test_capped_at_total():
    assert discount_cents(500, 150) == 500
"""
LATE_FEE_BUGGY = '''def late_fee_cents(balance_cents: int, days_late: int) -> int:
    """1% of the balance per full week late, from the first full week."""
    weeks = days_late // 7
    return balance_cents * weeks // 10
'''
LATE_FEE_TEST = """from billing.late_fee import late_fee_cents


def test_under_a_week_is_free():
    assert late_fee_cents(10_000, 6) == 0


def test_two_weeks():
    assert late_fee_cents(10_000, 14) == 200
"""


def write_five_bugs(dest: Path) -> None:
    make_fixture.write(dest, "three-bugs")
    _write_files(
        dest,
        {
            "billing/discount.py": DISCOUNT_BUGGY,
            "tests/test_discount.py": DISCOUNT_TEST,
            "billing/late_fee.py": LATE_FEE_BUGGY,
            "tests/test_late_fee.py": LATE_FEE_TEST,
        },
    )


# --- CI log ------------------------------------------------------------------------------------------------------------

CI_SCRIPT = '''"""Simulated CI: install, lint, migrations check, tests, packaging. Exits 1 if any step fails."""
import json
import sys
from pathlib import Path

rng_state = 7


def noise(step, count):
    global rng_state
    for i in range(count):
        rng_state = (rng_state * 1103515245 + 12345) % 2**31
        print(f"[{step}] {i:04d} ok   module_{rng_state % 997:03d}.py  ({rng_state % 83} ms)")


def check_migrations():
    graph = json.loads(Path("migrations/graph.json").read_text())
    names = [m["name"] for m in graph]
    for position, migration in enumerate(graph):
        for dependency in migration.get("depends_on", []):
            if dependency not in names[:position]:
                return f"migration {migration['name']} depends on {dependency}, which is not applied before it"
    return None


print("== install")
noise("install", 70)
print("== lint")
noise("lint", 70)
print("== migrations")
problem = check_migrations()
if problem:
    print(f"[migrations] ERROR {problem}")
else:
    print("[migrations] all migrations in order")
print("== tests")
noise("tests", 90)
print("== package")
noise("package", 60)
print("== summary")
for step in ("install", "lint", "migrations", "tests", "package"):
    status = "FAILED" if step == "migrations" and problem else "passed"
    print(f"  {step:<12} {status}")
sys.exit(1 if problem else 0)
'''

CI_GRAPH = [
    {"name": "0001_initial"},
    {"name": "0002_customers", "depends_on": ["0001_initial"]},
    {"name": "0003_invoices", "depends_on": ["0002_customers"]},
    {"name": "0004_refunds", "depends_on": ["0003_invoices"]},
    {"name": "0005_refund_reason", "depends_on": ["0006_reason_codes"]},
    {"name": "0006_reason_codes", "depends_on": ["0004_refunds"]},
    {"name": "0007_indexes", "depends_on": ["0005_refund_reason"]},
]


def write_ci_log(dest: Path) -> None:
    make_fixture.write(dest, "one-bug")
    (dest / "billing/money.py").write_text(
        make_fixture.MONEY.replace("ROUND_HALF_UP", "ROUND_HALF_EVEN"),
        encoding="utf-8",
        newline="\n",
    )
    _write_files(
        dest, {"ci.py": CI_SCRIPT, "migrations/graph.json": json.dumps(CI_GRAPH, indent=2) + "\n"}
    )


def check_ci_log(dest: Path) -> bool:
    graph = json.loads((dest / "migrations/graph.json").read_text(encoding="utf-8"))
    names = sorted(m["name"] for m in graph)
    return _run(dest, "ci.py").returncode == 0 and names == sorted(m["name"] for m in CI_GRAPH)


# --- JSON issue list ---------------------------------------------------------------------------------------------------

ISSUES_CLI = '''"""A local stand-in for an issue tracker CLI."""
import json
import sys
from pathlib import Path

issues = json.loads(Path("data/issues.json").read_text(encoding="utf-8"))
if sys.argv[1:2] != ["list"]:
    sys.exit("usage: python issues.py list [--state open|closed|all] [--json]")
state = "open"
if "--state" in sys.argv:
    state = sys.argv[sys.argv.index("--state") + 1]
rows = [i for i in issues if state == "all" or i["state"] == state]
if "--json" in sys.argv:
    print(json.dumps(rows, indent=1))
else:
    for i in rows:
        print(f"#{i['id']:<5} {i['state']:<7} {','.join(i['labels']):<22} {i['title']}")
'''

TOPICS = [
    ("Dashboard loads slowly for large accounts", ["performance"]),
    ("CSV export drops the last column", ["export"]),
    ("Invoice PDF shows the wrong logo", ["invoices"]),
    ("Webhook retries are not logged", ["webhooks"]),
    ("Customer search ignores accents", ["search"]),
    ("Tax report rounds totals twice", ["billing", "tax"]),
    ("Subscription renewal email has a broken link", ["email"]),
    ("Card update form rejects valid postcodes", ["billing", "payments"]),
    ("Usage chart is empty on the first day of the month", ["analytics"]),
    ("API key list does not paginate", ["api"]),
]
REFUND_BODIES = [
    "When a customer cancels mid-cycle the refund is computed on the full month instead of the days left.",
    "Partial refunds issued from the admin panel are not reflected in the customer's balance until the next sync.",
    "A refund for a disputed charge was sent twice; the second one should have been blocked.",
]


def _issues() -> List[dict]:
    rng = random.Random(11)
    issues = []
    for n in range(1, 91):
        title, labels = TOPICS[rng.randrange(len(TOPICS))]
        body = (
            f"Reported by a customer on plan {rng.choice(['starter', 'team', 'scale'])}. Steps: open the page, wait, "
            f"and compare with the expected result. Seen on {rng.choice(['Chrome', 'Firefox', 'Safari'])}. "
            f"Priority {rng.choice(['low', 'medium', 'high'])}."
        )
        issues.append(
            {
                "id": 4100 + n,
                "state": "open" if rng.random() < 0.8 else "closed",
                "title": f"{title} ({n})",
                "labels": list(labels),
                "author": rng.choice(["asha", "ben", "chen", "dara", "eli"]),
                "created_at": f"2026-09-{1 + n % 28:02d}T{n % 24:02d}:15:00Z",
                "comments": rng.randrange(0, 9),
                "body": body,
            }
        )
    # Refund reports: only the body says "refund", and only some are open and labelled billing.
    for n, (issue_id, state, labels) in enumerate(
        [
            (4117, "open", ["billing"]),
            (4142, "open", ["billing", "payments"]),
            (4163, "closed", ["billing"]),
            (4178, "open", ["support"]),
            (4186, "open", ["billing"]),
        ]
    ):
        issue = next(i for i in issues if i["id"] == issue_id)
        issue.update(
            state=state,
            labels=labels,
            title=f"Customer balance looks wrong ({issue_id})",
            body=REFUND_BODIES[n % 3] + " " + issue["body"],
        )
    return issues


ISSUES_EXPECTED = ["4117", "4142", "4186"]


def write_json_issues(dest: Path) -> None:
    _write_files(
        dest, {"issues.py": ISSUES_CLI, "data/issues.json": json.dumps(_issues(), indent=1) + "\n"}
    )


def check_json_issues(dest: Path) -> bool:
    path = dest / "triage.txt"
    if not path.exists():
        return False
    return path.read_text(encoding="utf-8").split() == ISSUES_EXPECTED


# --- Lint output -------------------------------------------------------------------------------------------------------

LINT_SCRIPT = '''"""A small linter: W lines are style warnings, E lines are errors. Exits 1 if there are errors."""
import ast
import builtins
import sys
from pathlib import Path

errors = warnings = 0
for path in sorted(Path("app").rglob("*.py")):
    source = path.read_text(encoding="utf-8")
    for number, line in enumerate(source.splitlines(), 1):
        if len(line) > 60:
            warnings += 1
            print(f"{path.as_posix()}:{number}: W501 line longer than 60 characters ({len(line)})")
    tree = ast.parse(source)
    defined = set(dir(builtins))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            defined.add(node.name)
            defined.update(a.arg for a in node.args.args) if isinstance(node, ast.FunctionDef) else None
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            defined.update((a.asname or a.name).split(".")[0] for a in node.names)
        elif isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            defined.add(node.id)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load) and node.id not in defined:
            errors += 1
            print(f"{path.as_posix()}:{node.lineno}: E821 undefined name {node.id!r}")
print(f"{errors} errors, {warnings} warnings")
sys.exit(1 if errors else 0)
'''


def write_lint_fix(dest: Path) -> None:
    files = {"lint.py": LINT_SCRIPT}
    for n in range(24):
        lines = [f"def handler_{n}(request, settings):"]
        for k in range(10):
            lines.append(
                f"    value_{k} = request.get('field_{k}', settings.get('default_{k}', None))  # keep"
            )
        lines.append("    return value_0")
        files[f"app/handlers_{n:02d}.py"] = "\n".join(lines) + "\n"
    files["app/handlers_07.py"] = files["app/handlers_07.py"].replace(
        "return value_0", "return valeu_0"
    )
    files["app/handlers_15.py"] = files["app/handlers_15.py"].replace(
        "return value_0", "return request_id"
    )
    files["app/handlers_21.py"] = files["app/handlers_21.py"].replace(
        "    return value_0", "    total = value_0 + offest\n    return total"
    )
    _write_files(dest, files)


def check_lint_fix(dest: Path) -> bool:
    result = _run(dest, "lint.py")
    match = re.search(r"(\d+) errors, (\d+) warnings", result.stdout)
    return result.returncode == 0 and bool(match) and int(match.group(2)) >= 240


# --- Rename across files -----------------------------------------------------------------------------------------------


def write_rename(dest: Path) -> None:
    files = {
        "pytest.ini": "[pytest]\npythonpath = .\ntestpaths = tests\n",
        "shop/__init__.py": "",
        "shop/totals.py": "def calc_total(prices):\n    return sum(prices)\n",
    }
    for n in range(18):
        files[f"shop/report_{n:02d}.py"] = (
            "from shop.totals import calc_total\n\n\n"
            f"def report_{n}(orders):\n"
            "    lines = [calc_total(order) for order in orders]\n"
            f"    return {{'count': len(lines), 'sum': calc_total(lines)}}\n"
        )
    files["tests/test_totals.py"] = (
        "from shop.totals import calc_total\n\n\ndef test_calc_total():\n    assert calc_total([1, 2, 3]) == 6\n"
    )
    files["tests/test_reports.py"] = (
        "".join(f"from shop.report_{n:02d} import report_{n}\n" for n in range(18))
        + "\n\ndef test_reports():\n"
        + "".join(
            f"    assert report_{n}([[1, 2], [3]]) == {{'count': 2, 'sum': 6}}\n" for n in range(18)
        )
    )
    _write_files(dest, files)


def check_rename(dest: Path) -> bool:
    sources = [p.read_text(encoding="utf-8") for p in dest.rglob("*.py")]
    return (
        not any("calc_total" in s for s in sources)
        and any("def compute_total" in s for s in sources)
        and _tests_pass(dest)
    )


# --- Explore (mostly file reads, which are never compressed) -----------------------------------------------------------


def write_explore(dest: Path) -> None:
    make_fixture.write(dest, "one-bug")


def check_explore(dest: Path) -> bool:
    path = dest / "NOTES.md"
    if not path.exists():
        return False
    text = path.read_text(encoding="utf-8").lower()
    return all(
        name in text for name in ("money", "refund", "invoice", "tax", "periods", "currency")
    )


TASKS: Dict[str, Task] = {
    "one-bug": Task(
        "one-bug",
        "The test suite is failing. Run `pytest -v` to see the failures, fix the bug in the source code (don't change "
        "the tests), then run `pytest -v` again to confirm everything passes. Reply with one sentence on what you "
        "changed.",
        lambda d: make_fixture.write(d, "one-bug"),
        _tests_pass,
        ["pytest", "python -m pytest"],
    ),
    "three-bugs": Task(
        "three-bugs",
        "Some tests are failing. Run `pytest -v`, then fix the failures one at a time by changing the source code, not "
        "the tests. Run `pytest -v` after each fix. Reply with one line per fix.",
        lambda d: make_fixture.write(d, "three-bugs"),
        _tests_pass,
        ["pytest", "python -m pytest"],
    ),
    "five-bugs": Task(
        "five-bugs",
        "Some tests are failing. Run `pytest -v`, then fix the failures one at a time by changing the source code, not "
        "the tests. Run `pytest -v` after each fix. Reply with one line per fix.",
        write_five_bugs,
        _tests_pass,
        ["pytest", "python -m pytest"],
    ),
    "ci-log": Task(
        "ci-log",
        "CI is failing. Run `python ci.py` to reproduce it, find the cause and fix it without deleting any migration, "
        "then run `python ci.py` again to confirm it passes. Reply with one sentence on the cause.",
        write_ci_log,
        check_ci_log,
        ["python ci.py"],
    ),
    "json-issues": Task(
        "json-issues",
        "Run `python issues.py list --json` to get the open issues. Find every open issue labelled `billing` whose "
        "title or body mentions a refund, and write their ids to triage.txt, one per line, in ascending order. "
        "Reply with the ids.",
        write_json_issues,
        check_json_issues,
        ["python issues.py"],
    ),
    "lint-fix": Task(
        "lint-fix",
        "Run `python lint.py`. Fix every error (the E lines) and ignore the warnings (the W lines); don't reformat "
        "anything else. Run `python lint.py` again until it reports 0 errors. Reply with one line per fix.",
        write_lint_fix,
        check_lint_fix,
        ["python lint.py"],
    ),
    "rename": Task(
        "rename",
        "Rename the function `calc_total` to `compute_total` everywhere: the definition, every import and call, and "
        "the tests. Then run `pytest -q` to confirm the tests pass. Reply with how many files you changed.",
        write_rename,
        check_rename,
        ["pytest", "python -m pytest"],
    ),
    "explore": Task(
        "explore",
        "Read the billing package and write NOTES.md with one line per module saying what it does. Don't change any "
        "other file.",
        write_explore,
        check_explore,
        [],
    ),
}
