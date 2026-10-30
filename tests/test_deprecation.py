"""The deprecation helper: warnings name the replacement and the removal release, and old names keep working."""

from __future__ import annotations

import asyncio
import inspect
import types
import warnings
from dataclasses import dataclass

import pytest

from llmslim._deprecation import (
    Alias,
    deprecated,
    deprecated_attributes,
    deprecation_message,
    renamed_parameter,
    warn_deprecated,
)


def test_message_names_the_release_the_removal_and_the_replacement():
    message = deprecation_message("old", since="1.2", removed_in="2.0", replacement="new")
    assert (
        message
        == "old is deprecated since llmslim 1.2 and will be removed in 2.0; use new instead."
    )
    assert deprecation_message("old", since="1.2.3", removed_in="3.0.0", replacement=None).endswith(
        "will be removed in 3.0.0; it has no replacement."
    )


@pytest.mark.parametrize(
    "since, removed_in",
    [
        ("1.2", "1.4"),  # removal in a minor release
        ("1.2", "2.1"),  # not a major release
        ("1.2", "2.0.1"),
        ("2.1", "2.0"),  # not later than the deprecation
        ("1.2", "1.0"),
        ("one", "2.0"),
        ("1.2", "next"),
    ],
)
def test_versions_that_break_the_policy_are_refused(since, removed_in):
    with pytest.raises(ValueError):
        deprecation_message("old", since=since, removed_in=removed_in, replacement="new")


def test_an_empty_name_is_refused():
    with pytest.raises(ValueError):
        deprecation_message("", since="1.0", removed_in="2.0", replacement="new")


def test_warn_points_at_the_callers_line():
    def old_api():
        warn_deprecated("old_api", since="1.0", removed_in="2.0", replacement="new_api")

    with pytest.warns(DeprecationWarning, match="use new_api instead") as caught:
        old_api()
    assert caught[0].filename == __file__


def test_a_deprecated_function_still_works_and_warns_at_the_call_site():
    @deprecated(since="1.1", removed_in="2.0", replacement="llmslim.add")
    def plus(a: int, b: int = 1) -> int:
        """Add."""
        return a + b

    with pytest.warns(DeprecationWarning, match=r"plus is deprecated since llmslim 1\.1") as caught:
        assert plus(2, b=3) == 5
    assert caught[0].filename == __file__
    assert plus.__name__ == "plus" and plus.__doc__ == "Add."
    assert str(inspect.signature(plus)) == "(a: 'int', b: 'int' = 1) -> 'int'"
    assert "llmslim.add" in plus.__deprecated__


def test_a_deprecated_coroutine_function_stays_a_coroutine_function():
    @deprecated(since="1.1", removed_in="2.0", replacement="fetch")
    async def get(value: int) -> int:
        return value

    assert inspect.iscoroutinefunction(get)
    with pytest.warns(DeprecationWarning):
        assert asyncio.run(get(4)) == 4


def test_a_deprecated_class_warns_on_construction_and_keeps_isinstance():
    @deprecated(since="1.3", removed_in="2.0", replacement="NewPoint")
    @dataclass
    class Point:
        x: int
        y: int = 0

    with pytest.warns(DeprecationWarning, match="use NewPoint instead") as caught:
        point = Point(1, y=2)
    assert caught[0].filename == __file__
    assert isinstance(point, Point) and (point.x, point.y) == (1, 2)
    assert "__deprecated__" in vars(Point)

    class Child(Point):
        pass

    assert "__deprecated__" not in vars(Child)


def test_a_deprecated_method_classmethod_and_staticmethod():
    class Thing:
        @deprecated(since="1.0", removed_in="2.0", replacement="Thing.new_method")
        def method(self) -> str:
            return "m"

        @classmethod
        @deprecated(since="1.0", removed_in="2.0", replacement="Thing.create")
        def make(cls) -> "Thing":
            return cls()

        @staticmethod
        @deprecated(since="1.0", removed_in="2.0", replacement=None)
        def helper() -> int:
            return 7

    with pytest.warns(DeprecationWarning, match="Thing.new_method"):
        assert Thing().method() == "m"
    with pytest.warns(DeprecationWarning, match="Thing.create"):
        assert isinstance(Thing.make(), Thing)
    with pytest.warns(DeprecationWarning, match="no replacement"):
        assert Thing.helper() == 7


def test_deprecated_refuses_what_it_cannot_wrap():
    with pytest.raises(TypeError):
        deprecated(since="1.0", removed_in="2.0", replacement="x")(42)
    with pytest.raises(ValueError):
        deprecated(since="1.0", removed_in="1.5", replacement="x")(lambda: None)


def test_a_renamed_keyword_is_accepted_with_a_warning():
    @renamed_parameter("ratio", "target_ratio", since="1.4", removed_in="2.0")
    def shrink(text: str, target_ratio: float = 0.5) -> str:
        return f"{text}:{target_ratio}"

    with warnings.catch_warnings():
        warnings.simplefilter("error")
        assert shrink("a", target_ratio=0.25) == "a:0.25"
        assert shrink("a", 0.3) == "a:0.3"
    with pytest.warns(DeprecationWarning, match=r"'ratio' argument .* use 'target_ratio' instead"):
        assert shrink("a", ratio=0.2) == "a:0.2"
    with pytest.raises(TypeError, match="both"):
        shrink("a", ratio=0.2, target_ratio=0.1)


def test_a_renamed_keyword_must_name_an_existing_parameter():
    with pytest.raises(TypeError):
        renamed_parameter("old", "missing", since="1.0", removed_in="2.0")(lambda text: text)


def test_module_attributes_resolve_old_names_with_a_warning():
    module = types.ModuleType("llmslim.example")

    class NewName:
        pass

    module.__getattr__ = deprecated_attributes(
        module.__name__,
        {"OldName": Alias(NewName, since="1.2", removed_in="2.0", replacement="NewName")},
    )
    with pytest.warns(DeprecationWarning, match=r"llmslim\.example\.OldName is deprecated"):
        assert module.OldName is NewName
    with pytest.raises(AttributeError, match="Missing"):
        module.Missing  # noqa: B018


def test_module_attribute_versions_are_checked_at_import_time():
    with pytest.raises(ValueError):
        deprecated_attributes(
            "m", {"Old": Alias(object, since="1.0", removed_in="1.1", replacement="New")}
        )
