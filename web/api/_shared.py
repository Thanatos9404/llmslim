"""Request hygiene shared by the website's Python functions.

Vercel does not turn files in ``api/`` whose names start with an underscore into functions, so this
module is shared code, not a route.

- :func:`decode_json_object` parses a request body without letting hostile input escape as a 500:
  deeply nested arrays (``RecursionError``), integers past Python's digit limit (``ValueError``),
  ``NaN``/``Infinity`` and lone surrogates that would fail later when encoded are all refused with a
  clean 400 or 422.
- :func:`bound_windows` keeps the per-instance rate-limit tables from growing without bound.
"""

from __future__ import annotations

import json
from collections import deque
from collections.abc import MutableMapping
from http import HTTPStatus
from typing import Any

MAX_DEPTH = 32
MAX_TRACKED_CLIENTS = 4_096


class BodyError(ValueError):
    """A request body problem with a fixed, public status, code and message."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code
        self.message = message


def _no_constants(name: str) -> Any:
    raise ValueError(f"{name} is not valid JSON")


def check_value(value: Any, max_depth: int = MAX_DEPTH) -> None:
    """Refuse nesting deeper than ``max_depth`` and strings that cannot be encoded as UTF-8.

    Iterative, so a hostile document cannot exhaust the interpreter stack here.
    """

    stack: list[tuple[Any, int]] = [(value, 0)]
    while stack:
        item, depth = stack.pop()
        if isinstance(item, str):
            try:
                item.encode("utf-8")
            except UnicodeEncodeError:
                raise BodyError(
                    HTTPStatus.UNPROCESSABLE_ENTITY,
                    "invalid_text",
                    "Text must be valid Unicode.",
                ) from None
            continue
        if isinstance(item, (dict, list)):
            if depth >= max_depth:
                raise BodyError(
                    HTTPStatus.BAD_REQUEST, "invalid_json", "The request body is nested too deeply."
                )
            if isinstance(item, dict):
                for key, child in item.items():
                    stack.append((key, depth + 1))
                    stack.append((child, depth + 1))
            else:
                stack.extend((child, depth + 1) for child in item)


def decode_json_object(raw_body: bytes, max_depth: int = MAX_DEPTH) -> dict[str, Any]:
    """Parse UTF-8 JSON into a dict, or raise :class:`BodyError`."""

    try:
        payload = json.loads(raw_body.decode("utf-8"), parse_constant=_no_constants)
    except (ValueError, RecursionError):
        # ValueError covers JSONDecodeError, UnicodeDecodeError, over-long integers and NaN.
        raise BodyError(
            HTTPStatus.BAD_REQUEST, "invalid_json", "The request body is not valid JSON."
        ) from None
    if not isinstance(payload, dict):
        raise BodyError(
            HTTPStatus.BAD_REQUEST, "object_required", "The request body must be a JSON object."
        )
    check_value(payload, max_depth)
    return payload


def bound_windows(
    windows: MutableMapping[str, deque[float]],
    cutoff: float,
    limit: int = MAX_TRACKED_CLIENTS,
) -> None:
    """Drop idle clients, then the oldest ones, once more than ``limit`` are tracked."""

    if len(windows) <= limit:
        return
    for key in [key for key, window in windows.items() if not window or window[-1] <= cutoff]:
        del windows[key]
    while len(windows) > limit:
        del windows[next(iter(windows))]
