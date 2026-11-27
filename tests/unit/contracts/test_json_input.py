"""Strict decoding of tool-argument JSON bodies."""

from __future__ import annotations

import pytest

from grenslan.contracts.json_input import MalformedInput, decode_arguments

LIMIT = 1024


def test_decodes_object() -> None:
    assert decode_arguments(b'{"query": "fixture", "max_results": 5}', max_bytes=LIMIT) == {
        "query": "fixture",
        "max_results": 5,
    }


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (b'{"query": "a", "query": "b"}', "duplicate"),
        (b'{"a": {"x": 1, "x": 2}}', "duplicate"),
        (b'{"n": NaN}', "non-finite"),
        (b'{"n": Infinity}', "non-finite"),
        (b'{"n": -Infinity}', "non-finite"),
        (b'["query"]', "object"),
        (b'"query"', "object"),
        (b"null", "object"),
        (b'{"query": "a"} trailing', "json"),
        (b'{"query": "a"', "json"),
        (b"", "json"),
        (b'{"q": "\xff"}', "utf-8"),
        (b'\xef\xbb\xbf{"q": "bom"}', "utf-8"),
    ],
)
def test_rejects_malformed_bodies(body: bytes, reason: str) -> None:
    with pytest.raises(MalformedInput) as excinfo:
        decode_arguments(body, max_bytes=LIMIT)
    assert reason in excinfo.value.reason


def test_rejects_oversized_body_before_parsing() -> None:
    body = b'{"q": "' + b"a" * LIMIT + b'"}'
    with pytest.raises(MalformedInput) as excinfo:
        decode_arguments(body, max_bytes=LIMIT)
    assert excinfo.value.too_large is True


def test_rejects_excessive_nesting() -> None:
    body = b'{"a": ' * 200 + b"1" + b"}" * 200
    with pytest.raises(MalformedInput) as excinfo:
        decode_arguments(body, max_bytes=10_000, max_depth=64)
    assert "depth" in excinfo.value.reason


def test_error_does_not_echo_body_content() -> None:
    body = b'{"api_key": "sk-secret-value", "api_key": "x"}'
    with pytest.raises(MalformedInput) as excinfo:
        decode_arguments(body, max_bytes=LIMIT)
    assert "sk-secret-value" not in excinfo.value.reason
    assert "api_key" not in excinfo.value.reason
