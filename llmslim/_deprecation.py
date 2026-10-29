"""Deprecations, as ``docs/API_STABILITY.md`` describes them.

A stable name is deprecated in a minor release and removed only in a major one. Until then it keeps working and
warns with a :class:`DeprecationWarning` that names its replacement and the release that removes it::

    @deprecated(since="1.2", removed_in="2.0", replacement="llmslim.fit")
    def squeeze(text: str) -> str: ...

    @renamed_parameter("ratio", "target_ratio", since="1.2", removed_in="2.0")
    def compress(text: str, target_ratio: float = 0.5) -> str: ...

    # In a module whose name moved: a module-level __getattr__ serves the old name.
    __getattr__ = deprecated_attributes(
        __name__, {"OldName": Alias(NewName, since="1.2", removed_in="2.0", replacement="NewName")}
    )

Every deprecated object carries the message as ``__deprecated__`` (the attribute PEP 702 uses), and the public API
snapshot records it.
"""

from __future__ import annotations

import functools
import inspect
import re
import warnings
from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, TypeVar

__all__ = [
    "Alias",
    "deprecated",
    "deprecated_attributes",
    "deprecation_message",
    "renamed_parameter",
    "warn_deprecated",
]

T = TypeVar("T")

_VERSION = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


def _parse(version: str, what: str) -> Tuple[int, int, int]:
    match = _VERSION.fullmatch(version)
    if match is None:
        raise ValueError(f"{what} must be a release like '1.2' or '1.2.0', got {version!r}")
    major, minor, patch = match.groups()
    return int(major), int(minor), int(patch or 0)


def deprecation_message(
    name: str, *, since: str, removed_in: str, replacement: Optional[str]
) -> str:
    """The warning text for ``name``, after checking the versions follow the deprecation policy.

    ``removed_in`` must be a major release (``2.0``) later than the major release of ``since``: a deprecated name
    is removed only in a major release. ``replacement`` is required by name; pass ``None`` only when nothing
    replaces the deprecated name.
    """

    if not name:
        raise ValueError("name must not be empty")
    deprecated_in = _parse(since, "since")
    removed = _parse(removed_in, "removed_in")
    if removed[1:] != (0, 0) or removed[0] <= deprecated_in[0]:
        raise ValueError(
            f"removed_in must be a later major release than since ({since}), like "
            f"'{deprecated_in[0] + 1}.0'; got {removed_in!r}"
        )
    advice = f"use {replacement} instead" if replacement else "it has no replacement"
    return (
        f"{name} is deprecated since llmslim {since} and will be removed in {removed_in}; {advice}."
    )


def warn_deprecated(
    name: str,
    *,
    since: str,
    removed_in: str,
    replacement: Optional[str],
    stacklevel: int = 2,
) -> None:
    """Warn that ``name`` is deprecated. ``stacklevel=2`` points at the caller of the function calling this."""

    message = deprecation_message(name, since=since, removed_in=removed_in, replacement=replacement)
    warnings.warn(message, DeprecationWarning, stacklevel=stacklevel + 1)


def _qualified(obj: Any) -> str:
    module = getattr(obj, "__module__", "") or ""
    name = str(getattr(obj, "__qualname__", None) or getattr(obj, "__name__", repr(obj)))
    return f"{module}.{name}" if module else name


def deprecated(*, since: str, removed_in: str, replacement: Optional[str]) -> Callable[[T], T]:
    """Mark a function, method or class deprecated: calling it (or creating an instance) warns.

    Put it above ``@dataclass`` on a class, and below ``@classmethod`` or ``@staticmethod`` on a method.
    """

    def decorate(obj: T) -> T:
        message = deprecation_message(
            _qualified(obj), since=since, removed_in=removed_in, replacement=replacement
        )
        if inspect.isclass(obj):
            original_init = obj.__init__

            @functools.wraps(original_init)
            def __init__(self: Any, *args: Any, **kwargs: Any) -> None:
                warnings.warn(message, DeprecationWarning, stacklevel=2)
                original_init(self, *args, **kwargs)

            obj.__init__ = __init__  # type: ignore[method-assign]
            obj.__deprecated__ = message  # type: ignore[attr-defined]
            return obj
        if not callable(obj):
            raise TypeError("@deprecated applies to functions, methods and classes")
        function: Callable[..., Any] = obj

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                warnings.warn(message, DeprecationWarning, stacklevel=2)
                return await function(*args, **kwargs)

            async_wrapper.__deprecated__ = message  # type: ignore[attr-defined]
            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(message, DeprecationWarning, stacklevel=2)
            return function(*args, **kwargs)

        wrapper.__deprecated__ = message  # type: ignore[attr-defined]
        return wrapper  # type: ignore[return-value]

    return decorate


def renamed_parameter(
    old: str, new: str, *, since: str, removed_in: str
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Accept keyword ``old`` as ``new``, with a warning. Passing both is a ``TypeError``."""

    def decorate(function: Callable[..., Any]) -> Callable[..., Any]:
        if new not in inspect.signature(function).parameters:
            raise TypeError(f"{_qualified(function)} has no parameter {new!r}")
        message = deprecation_message(
            f"The {old!r} argument of {_qualified(function)}",
            since=since,
            removed_in=removed_in,
            replacement=repr(new),
        )

        @functools.wraps(function)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if old in kwargs:
                if new in kwargs:
                    raise TypeError(
                        f"{function.__name__}() got both {old!r} and its replacement {new!r}"
                    )
                warnings.warn(message, DeprecationWarning, stacklevel=2)
                kwargs[new] = kwargs.pop(old)
            return function(*args, **kwargs)

        return wrapper

    return decorate


@dataclass(frozen=True)
class Alias:
    """An old module attribute name that still resolves to ``target``, with a warning."""

    target: Any
    since: str
    removed_in: str
    replacement: Optional[str]


def deprecated_attributes(module: str, aliases: Mapping[str, Alias]) -> Callable[[str], Any]:
    """A module-level ``__getattr__`` that serves each old name in ``aliases`` with a warning.

    The messages are built (and the versions checked) when the module is imported, not on first use.
    """

    messages: Dict[str, str] = {
        name: deprecation_message(
            f"{module}.{name}",
            since=alias.since,
            removed_in=alias.removed_in,
            replacement=alias.replacement,
        )
        for name, alias in aliases.items()
    }

    def __getattr__(name: str) -> Any:
        if name not in aliases:
            raise AttributeError(f"module {module!r} has no attribute {name!r}")
        warnings.warn(messages[name], DeprecationWarning, stacklevel=2)
        return aliases[name].target

    return __getattr__
