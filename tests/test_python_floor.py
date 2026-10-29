"""The supported Python floor is stated once and every tool agrees with it."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

tomllib = pytest.importorskip("tomllib")  # Python 3.11+; the other CI versions run this
yaml = pytest.importorskip("yaml")

ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
CI = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
FLOOR = (3, 10)


def _version(text: str) -> tuple[int, int]:
    major, minor = text.split(".")[:2]
    return int(major), int(minor)


def test_requires_python_is_the_floor() -> None:
    assert PYPROJECT["project"]["requires-python"] == ">=%d.%d" % FLOOR


def test_classifiers_start_at_the_floor() -> None:
    listed = [
        _version(c.rsplit("::", 1)[1].strip())
        for c in PYPROJECT["project"]["classifiers"]
        if re.fullmatch(r"Programming Language :: Python :: 3\.\d+", c)
    ]
    assert min(listed) == FLOOR


def test_linters_and_type_checker_target_the_floor() -> None:
    tool = PYPROJECT["tool"]
    assert tool["ruff"]["target-version"] == "py%d%d" % FLOOR
    assert tool["black"]["target-version"] == ["py%d%d" % FLOOR]
    assert _version(tool["mypy"]["python_version"]) == FLOOR


def test_no_dependency_is_marked_for_a_python_below_or_at_the_floor() -> None:
    marked = re.compile(r"python_version\s*(<|<=|>=|>|==)\s*['\"](\d+\.\d+)['\"]")
    extras = PYPROJECT["project"]["optional-dependencies"]
    requirements = PYPROJECT["project"]["dependencies"] + [
        r for reqs in extras.values() for r in reqs
    ]
    for requirement in requirements:
        for op, version in marked.findall(requirement):
            # A marker that is always true or always false on supported versions is dead weight.
            assert not (op in (">=", "<") and _version(version) <= FLOOR), requirement


def test_ci_tests_the_floor_and_nothing_older() -> None:
    matrix = CI["jobs"]["test"]["strategy"]["matrix"]
    versions = list(matrix["python-version"]) + [i["python-version"] for i in matrix["include"]]
    assert min(_version(v) for v in versions) == FLOOR
    mypy = next(s for s in CI["jobs"]["test"]["steps"] if s.get("run") == "mypy llmslim")
    assert "'%d.%d'" % FLOOR in mypy["if"]
