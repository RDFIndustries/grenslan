"""Strict decoding of tool-argument JSON request bodies.

Standard ``json.loads`` silently keeps the last of duplicated keys and accepts
``NaN`` and ``Infinity``. A request whose meaning depends on which duplicate a
component honours is ambiguous, so both are rejected here, along with
non-object bodies, invalid UTF-8, a byte-order mark, trailing data, oversized
bodies and excessive nesting. Error reasons never quote the body.
"""

from __future__ import annotations

import json
from typing import Any

DEFAULT_MAX_DEPTH = 64


class MalformedInput(ValueError):
    """The body is not a single acceptable JSON object."""

    def __init__(self, reason: str, *, too_large: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.too_large = too_large


class _DuplicateKey(Exception):
    pass


class _NonFinite(Exception):
    pass


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise _DuplicateKey
        result[key] = value
    return result


def _reject_constant(_name: str) -> Any:
    raise _NonFinite


def _nesting_depth(text: str, limit: int) -> bool:
    """Return True if container nesting stays within ``limit``; strings are skipped."""
    depth = 0
    in_string = False
    escaped = False
    for char in text:
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
        elif char == '"':
            in_string = True
        elif char in "[{":
            depth += 1
            if depth > limit:
                return False
        elif char in "]}":
            depth -= 1
    return True


def decode_arguments(body: bytes, *, max_bytes: int, max_depth: int = DEFAULT_MAX_DEPTH) -> dict[str, Any]:
    """Decode ``body`` as one JSON object or raise :class:`MalformedInput`."""
    if len(body) > max_bytes:
        raise MalformedInput("request body exceeds the configured size limit", too_large=True)
    if body.startswith(b"\xef\xbb\xbf"):
        raise MalformedInput("request body must be utf-8 without a byte-order mark")
    try:
        text = body.decode("utf-8")
    except UnicodeDecodeError:
        raise MalformedInput("request body is not valid utf-8") from None
    if not _nesting_depth(text, max_depth):
        raise MalformedInput("request body exceeds the maximum nesting depth")
    try:
        value = json.loads(text, object_pairs_hook=_object_pairs, parse_constant=_reject_constant)
    except _DuplicateKey:
        raise MalformedInput("request body contains a duplicate object key") from None
    except _NonFinite:
        raise MalformedInput("request body contains a non-finite number") from None
    except json.JSONDecodeError:
        raise MalformedInput("request body is not a single valid json document") from None
    if not isinstance(value, dict):
        raise MalformedInput("request body must be a json object")
    return value
