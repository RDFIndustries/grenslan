"""Runtime tool registry: packaged canonical schemas, projection and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from grenslan.contracts import registry as registry_module
from grenslan.contracts.registry import ToolRegistry, UnknownToolError

from minimal_requests import MINIMAL_REQUESTS

DOCS_REGISTRY = Path(__file__).resolve().parents[3] / "docs" / "contracts" / "TOOL_SCHEMAS.json"
FORGED_CONTEXT_FIELDS = ["application_id", "user_id", "agent_id", "instance_id", "permissions", "request_id"]


@pytest.fixture(scope="module")
def registry() -> ToolRegistry:
    return ToolRegistry.load()


def _refs(node: Any) -> list[str]:
    found: list[str] = []
    if isinstance(node, dict):
        for key, value in node.items():
            found.extend([value] if key == "$ref" else _refs(value))
    elif isinstance(node, list):
        for value in node:
            found.extend(_refs(value))
    return found


def test_packaged_registry_is_byte_identical_to_adopted_contract() -> None:
    assert registry_module.PACKAGED_REGISTRY.read_bytes() == DOCS_REGISTRY.read_bytes()


def test_registry_reports_contract_version(registry: ToolRegistry) -> None:
    assert registry.contract_version == "1.0"


def test_registry_has_the_32_adopted_tools(registry: ToolRegistry) -> None:
    adopted = set(json.loads(DOCS_REGISTRY.read_text(encoding="utf-8"))["tools"])
    assert set(registry.tool_names) == adopted
    assert len(registry.tool_names) == 32


def test_unknown_tool_raises(registry: ToolRegistry) -> None:
    with pytest.raises(UnknownToolError):
        registry.input_schema("no_such_tool")


@pytest.mark.parametrize("tool", sorted(json.loads(DOCS_REGISTRY.read_text(encoding="utf-8"))["tools"]))
def test_projected_schemas_are_self_contained(registry: ToolRegistry, tool: str) -> None:
    for schema in (registry.input_schema(tool), registry.output_schema(tool)):
        assert schema["type"] == "object"
        defined = set(schema.get("$defs", {}))
        for ref in _refs(schema):
            assert ref.startswith("#/$defs/")
            assert ref.removeprefix("#/$defs/") in defined


def test_projected_schema_is_a_copy(registry: ToolRegistry) -> None:
    schema = registry.input_schema("web_search")
    schema["properties"] = {}
    assert registry.input_schema("web_search")["properties"] != {}


def test_async_support_follows_registry(registry: ToolRegistry) -> None:
    assert registry.async_supported("web_search") is True
    assert registry.async_supported("capabilities_get") is False


def test_valid_input_has_no_errors(registry: ToolRegistry) -> None:
    assert registry.input_errors("web_search", {"query": "fixture"}) == []


@pytest.mark.parametrize("tool", sorted(MINIMAL_REQUESTS))
def test_minimal_request_is_valid(registry: ToolRegistry, tool: str) -> None:
    assert registry.input_errors(tool, MINIMAL_REQUESTS[tool]) == []


def test_minimal_requests_cover_every_tool(registry: ToolRegistry) -> None:
    assert set(MINIMAL_REQUESTS) == set(registry.tool_names)


@pytest.mark.parametrize("tool", sorted(MINIMAL_REQUESTS))
@pytest.mark.parametrize("field", FORGED_CONTEXT_FIELDS)
def test_caller_supplied_context_is_rejected_for_every_tool(registry: ToolRegistry, tool: str, field: str) -> None:
    errors = registry.input_errors(tool, {**MINIMAL_REQUESTS[tool], field: "forged"})
    assert [e.message for e in errors] == ["unknown property not permitted by the schema"]


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        ("web_open", {"url": "https://example.org/", "urls": ["https://example.org/"]}),
        ("document_open", {"url": "https://example.org/a.pdf", "artifact_uri": "grenslan://artifacts/a"}),
        ("citation_get", {"citation_id": "c1", "artifact_uri": "grenslan://artifacts/a"}),
    ],
)
def test_conflicting_selectors_are_rejected(registry: ToolRegistry, tool: str, arguments: dict[str, Any]) -> None:
    assert registry.input_errors(tool, arguments)


def test_input_errors_report_location_without_echoing_values(registry: ToolRegistry) -> None:
    sentinel = "sk-should-not-appear"
    errors = registry.input_errors("web_search", {"query": "x", "api_key": sentinel})
    assert errors
    assert all(sentinel not in error.message for error in errors)
    assert all(sentinel not in error.location for error in errors)


def test_format_validation_is_enforced(registry: ToolRegistry) -> None:
    assert registry.input_errors("web_open", {"url": "file:///etc/passwd"})


def test_output_validation_accepts_canonical_completed_envelope(registry: ToolRegistry) -> None:
    envelope = {
        "schema_version": "1.0",
        "request_id": "r",
        "status": "completed",
        "effective_mode": "sync",
        "issues": [],
        "result": {"results": [], "constraints": [], "ranking": "provider_order", "freshness": "default"},
    }
    assert registry.output_errors("web_search", envelope) == []


def test_output_validation_rejects_completed_without_result(registry: ToolRegistry) -> None:
    envelope = {
        "schema_version": "1.0",
        "request_id": "r",
        "status": "completed",
        "effective_mode": "sync",
        "issues": [],
    }
    assert registry.output_errors("web_search", envelope)


def test_upload_result_schema_is_available(registry: ToolRegistry) -> None:
    schema = registry.upload_result_schema()
    assert schema["properties"]["schema_version"] == {"const": "1.0"}
