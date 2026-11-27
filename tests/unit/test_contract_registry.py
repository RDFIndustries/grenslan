"""Integrity checks on the adopted public contract files in docs/contracts/.

These tests exercise the canonical registry as committed. They do not test
service behaviour.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

CONTRACTS = Path(__file__).resolve().parents[2] / "docs" / "contracts"
REGISTRY: dict[str, Any] = json.loads((CONTRACTS / "TOOL_SCHEMAS.json").read_text(encoding="utf-8"))
TOOL_NAMES = sorted(REGISTRY["tools"])


def _references(node: Any) -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref":
                yield value
            else:
                yield from _references(value)
    elif isinstance(node, list):
        for value in node:
            yield from _references(value)


def _project(reference: str) -> dict[str, Any]:
    """Return the referenced definition with every reachable local definition."""
    definitions: dict[str, Any] = REGISTRY["$defs"]
    root = dict(definitions[reference.removeprefix("#/$defs/")])
    reachable: dict[str, Any] = {}
    pending = list(_references(root))
    while pending:
        ref = pending.pop()
        assert ref.startswith("#/$defs/"), f"non-local reference {ref!r}"
        name = ref.removeprefix("#/$defs/")
        if name not in reachable:
            reachable[name] = definitions[name]
            pending.extend(_references(definitions[name]))
    return {"$schema": REGISTRY["$schema"], "$defs": reachable, **root}


def test_registry_declares_draft_2020_12() -> None:
    assert REGISTRY["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_registry_lists_32_tools() -> None:
    assert len(TOOL_NAMES) == 32


@pytest.mark.parametrize("tool", TOOL_NAMES)
@pytest.mark.parametrize("direction", ["inputSchema", "outputSchema"])
def test_tool_schema_projects_to_valid_object_schema(tool: str, direction: str) -> None:
    schema = _project(REGISTRY["tools"][tool][direction]["$ref"])
    assert schema["type"] == "object"
    Draft202012Validator.check_schema(schema)


def test_web_search_rejects_caller_supplied_identity() -> None:
    validator = Draft202012Validator(
        _project(REGISTRY["tools"]["web_search"]["inputSchema"]["$ref"]), format_checker=FormatChecker()
    )
    assert validator.is_valid({"query": "fixture"})
    assert not validator.is_valid({"query": "fixture", "application_id": "forged"})


def test_format_checker_has_uri_support_without_gpl_extra() -> None:
    # The format-nongpl extra provides "uri" checking through rfc3986-validator.
    assert "uri" in FormatChecker.checkers
    assert not FormatChecker().conforms("not a uri", "uri")


def test_provider_config_schema_is_valid_draft_2020_12() -> None:
    config = json.loads((CONTRACTS / "PROVIDER_CONFIG_SCHEMA.json").read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(config)
