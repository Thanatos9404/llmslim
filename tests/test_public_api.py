"""The public API matches its snapshot, so no change to it goes unnoticed (see docs/API_STABILITY.md)."""

from __future__ import annotations

import importlib
import json
from typing import Any

import pytest

from scripts import public_api as api

RECORDED = api.load()

HOW_TO_UPDATE = (
    "The public API no longer matches tests/fixtures/public_api.json.\n"
    "If the change is intended:\n"
    "  1. run `python scripts/public_api.py --write` and commit the snapshot;\n"
    "  2. say what changed under [Unreleased] in CHANGELOG.md.\n"
    "A stable name can't be removed or changed incompatibly in a 1.x release: deprecate it first "
    "(llmslim._deprecation, docs/API_STABILITY.md).\n\n"
)


def _assert_matches(recorded: Any, live: Any) -> None:
    found = api.differences(recorded, json.loads(api.dump(live)))
    assert not found, HOW_TO_UPDATE + "\n".join(found)


@pytest.mark.parametrize("module", sorted(api.MODULES))
def test_python_surface_matches_the_snapshot(module):
    try:
        live = api.module_surface(module)
    except ImportError as error:
        pytest.skip(f"{module} needs an optional dependency that is not installed: {error}")
    assert module in RECORDED["python"], f"{module} is not in the snapshot.\n" + HOW_TO_UPDATE
    _assert_matches(RECORDED["python"][module], live)


def test_snapshot_holds_exactly_the_public_modules():
    assert set(RECORDED["python"]) == set(api.MODULES), HOW_TO_UPDATE


def test_every_module_is_public_or_internal():
    modules = api.package_modules()
    unclassified = [
        name for name in modules if name not in api.MODULES and not api.is_internal(name)
    ]
    assert not unclassified, (
        f"New modules {unclassified}: add each to MODULES (public) or INTERNAL in scripts/public_api.py, "
        "and to docs/API_STABILITY.md"
    )
    assert not set(api.MODULES) & api.INTERNAL
    assert api.INTERNAL <= set(modules), sorted(api.INTERNAL - set(modules))


def test_public_names_resolve_and_internal_names_are_not_exported():
    for module in api.MODULES:
        try:
            imported = importlib.import_module(module)
        except ImportError:
            continue
        for name in imported.__all__:
            assert not name.startswith("_") or name == "__version__", f"{module}.{name}"
            assert hasattr(imported, name), f"{module}.__all__ names a missing {name!r}"


def test_cli_matches_the_snapshot():
    _assert_matches(RECORDED["cli"], api.cli_surface())


def test_serve_routes_match_the_snapshot():
    pytest.importorskip("starlette")
    _assert_matches(RECORDED["http"], api.http_surface())


def test_mcp_tools_match_the_snapshot():
    pytest.importorskip("mcp")
    _assert_matches(RECORDED["mcp"], api.mcp_surface())


def test_entry_points_match_the_snapshot():
    pytest.importorskip("tomllib")
    _assert_matches(RECORDED["entry_points"], api.entry_points_surface())


def test_environment_variables_match_the_snapshot():
    _assert_matches(RECORDED["environment"], api.environment_surface())


def test_documented_environment_variables_are_the_ones_read():
    stability = (api.ROOT / "docs" / "API_STABILITY.md").read_text(encoding="utf-8")
    for name in RECORDED["environment"]:
        assert f"`{name}`" in stability, (
            f"{name} is read by the package but not in docs/API_STABILITY.md"
        )


def test_documented_modules_are_the_public_ones():
    stability = (api.ROOT / "docs" / "API_STABILITY.md").read_text(encoding="utf-8")
    for module in api.MODULES:
        assert f"`{module}`" in stability, f"{module} is public but not in docs/API_STABILITY.md"


def test_the_snapshot_file_is_what_the_script_writes():
    text = api.SNAPSHOT.read_text(encoding="utf-8").replace("\r\n", "\n")
    assert text == api.dump(RECORDED), (
        "edit the snapshot with scripts/public_api.py --write, not by hand"
    )


# --------------------------------------------------------------------------- the snapshot machinery itself


def test_differences_name_what_was_added_removed_and_changed():
    recorded = {"a": {"kind": "function", "signature": "(x)"}, "b": 1}
    live = {"a": {"kind": "function", "signature": "(x, y)"}, "c": 2}
    found = api.differences(recorded, live)
    assert found[0].startswith("changed: a.signature")
    assert "was: '(x)'" in found[0] and "now: '(x, y)'" in found[0]
    assert found[1:] == ["removed: b", "added:   c"]
    assert api.differences(live, live) == []


def test_signatures_are_the_same_on_every_machine():
    import enum
    from dataclasses import dataclass, field
    from pathlib import Path

    class Colour(str, enum.Enum):
        RED = "red"

    @dataclass
    class Settings:
        path: Path = Path.home() / "x.db"
        colour: Colour = Colour.RED
        tags: list = field(default_factory=list)
        pair: tuple = ("a",)
        flags: frozenset = frozenset({"b", "a"})

    described = api.describe(Settings)
    assert described["signature"] == (
        "(path: Path = <path>, colour: Colour = Colour.RED, tags: list = <factory>, pair: tuple = ('a',), "
        "flags: frozenset = frozenset({'a', 'b'})) -> None"
    )
    assert api.describe(Colour)["values"] == {"RED": "'red'"}


def test_a_deprecated_name_is_recorded_as_deprecated():
    from llmslim._deprecation import deprecated

    @deprecated(since="1.1", removed_in="2.0", replacement="new")
    def old() -> None:
        pass

    assert "use new instead" in api.describe(old)["deprecated"]
    assert "deprecated" not in api.describe(api.describe)
