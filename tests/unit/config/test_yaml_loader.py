"""Strict, data-only YAML loading for operator configuration (PC-059, F-G15)."""

from __future__ import annotations

import pytest

from grenslan.config.yaml_loader import ConfigSyntaxError, load_config_text

LIMIT = 64 * 1024


def test_loads_plain_mapping() -> None:
    text = (
        "config_version: '1.0'\nlimits:\n  max_timeout_ms: 30000\n  ratio: 0.5\n"
        "enabled: true\nnone: null\nitems: [a, b]\n"
    )
    assert load_config_text(text, max_bytes=LIMIT) == {
        "config_version": "1.0",
        "limits": {"max_timeout_ms": 30000, "ratio": 0.5},
        "enabled": True,
        "none": None,
        "items": ["a", "b"],
    }


@pytest.mark.parametrize(
    ("text", "line", "reason"),
    [
        ("a: 1\na: 2\n", 2, "duplicate key"),
        ("outer:\n  x: 1\n  x: 2\n", 3, "duplicate key"),
        ("a: !!python/object/apply:os.system ['true']\n", 1, "tag"),
        ("a: !!python/name:os.system\n", 1, "tag"),
        ("a: !custom value\n", 1, "tag"),
        ("a: !!binary aGVsbG8=\n", 1, "tag"),
        ("a: !!set {x: null}\n", 1, "tag"),
        ("a: !!str 5\n", 1, "tag"),
        ("base: &b {x: 1}\nother: *b\n", 1, "anchor"),
        ("base: {x: 1}\nother:\n  <<: {x: 2}\n", 3, "merge"),
        ("a: 2026-01-01\n", 1, "quote"),
        ("a: .inf\n", 1, "non-finite"),
        ("a: .nan\n", 1, "non-finite"),
        ("1: x\n", 1, "string"),
        ("true: x\n", 1, "string"),
        ("? [a, b]\n: x\n", 1, "string"),
        ("- a\n- b\n", 1, "mapping"),
        ("just a scalar\n", 1, "mapping"),
        ("a: 1\n---\nb: 2\n", 2, "single document"),
        ("a: [1, 2\n", 2, "syntax"),
        ("a:\tb: c\n", 1, "syntax"),
    ],
)
def test_rejects_unsafe_or_ambiguous_yaml(text: str, line: int, reason: str) -> None:
    with pytest.raises(ConfigSyntaxError) as excinfo:
        load_config_text(text, max_bytes=LIMIT)
    assert reason in excinfo.value.reason
    assert excinfo.value.line == line


def test_empty_document_is_rejected() -> None:
    with pytest.raises(ConfigSyntaxError, match="mapping"):
        load_config_text("", max_bytes=LIMIT)


def test_oversized_text_is_rejected_before_parsing() -> None:
    with pytest.raises(ConfigSyntaxError, match="size"):
        load_config_text("a: " + "x" * LIMIT + "\n", max_bytes=LIMIT)


def test_excessive_nesting_is_rejected_without_recursion_error() -> None:
    text = "a: " + "[" * 5000 + "]" * 5000 + "\n"
    with pytest.raises(ConfigSyntaxError, match="depth"):
        load_config_text(text, max_bytes=LIMIT, max_depth=32)


def test_errors_do_not_echo_values() -> None:
    text = "credential: sk-live-secret-value\ncredential: other\n"
    with pytest.raises(ConfigSyntaxError) as excinfo:
        load_config_text(text, max_bytes=LIMIT)
    assert "sk-live-secret-value" not in str(excinfo.value)


def test_syntax_error_does_not_echo_source_snippet() -> None:
    text = 'token: "sk-live-secret-value\n'
    with pytest.raises(ConfigSyntaxError) as excinfo:
        load_config_text(text, max_bytes=LIMIT)
    assert "sk-live-secret-value" not in str(excinfo.value)
