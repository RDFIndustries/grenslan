"""Typed public request records for the foundation tools (TC-047, TC-049)."""

from __future__ import annotations

import dataclasses
import typing
from typing import Any

import pytest

from grenslan.contracts import requests
from grenslan.contracts.registry import ToolRegistry

TYPED: dict[str, type[requests.RequestRecord]] = {
    "web_search": requests.WebSearchRequest,
    "image_search": requests.ImageSearchRequest,
    "capabilities_get": requests.CapabilitiesGetRequest,
    "operation_status": requests.OperationStatusRequest,
    "operation_results": requests.OperationResultsRequest,
    "operation_cancel": requests.OperationCancelRequest,
}


@pytest.fixture(scope="module")
def registry() -> ToolRegistry:
    return ToolRegistry.load()


def _check_record_against_schema(record: type, schema: dict[str, Any]) -> None:
    fields = {f.name: f for f in dataclasses.fields(record)}
    assert set(fields) == set(schema["properties"])
    for name, field in fields.items():
        has_default = field.default is not dataclasses.MISSING
        if name in schema.get("required", []):
            assert not has_default, f"{record.__name__}.{name} is required"
        else:
            assert field.default == schema["properties"][name].get("default"), f"{record.__name__}.{name}"
    hints = typing.get_type_hints(record)
    for name, prop in schema["properties"].items():
        if "enum" in prop:
            literals = [arg for arg in typing.get_args(hints[name]) if typing.get_origin(arg) is typing.Literal]
            if typing.get_origin(hints[name]) is typing.Literal:
                literals = [hints[name]]
            assert len(literals) == 1, f"{record.__name__}.{name} is not a Literal"
            assert list(typing.get_args(literals[0])) == prop["enum"], f"{record.__name__}.{name}"


@pytest.mark.parametrize("tool", sorted(TYPED))
def test_record_matches_input_schema(registry: ToolRegistry, tool: str) -> None:
    _check_record_against_schema(TYPED[tool], registry.input_schema(tool))


def test_nested_records_match_schema(registry: ToolRegistry) -> None:
    schema = registry.input_schema("web_search")
    _check_record_against_schema(requests.Execution, schema["$defs"]["Execution"])
    _check_record_against_schema(requests.RetrieveOption, schema["properties"]["retrieve"])


def test_minimal_web_search_applies_only_schema_defaults() -> None:
    request = requests.WebSearchRequest.from_arguments({"query": "fixture"})
    assert request.query == "fixture"
    assert request.category == "general"
    assert request.freshness == "default"
    assert request.max_results is None
    assert request.execution is None
    assert request.include_domains is None


def test_web_search_converts_nested_values() -> None:
    request = requests.WebSearchRequest.from_arguments(
        {
            "query": "fixture",
            "include_domains": ["example.org"],
            "retrieve": {"max_sources": 2},
            "execution": {"timeout_ms": 5000},
        }
    )
    assert request.include_domains == ("example.org",)
    assert request.retrieve == requests.RetrieveOption(max_sources=2)
    assert request.execution == requests.Execution(timeout_ms=5000)
    assert request.execution.mode == "sync"


def test_records_are_immutable() -> None:
    request = requests.WebSearchRequest.from_arguments({"query": "fixture"})
    with pytest.raises(dataclasses.FrozenInstanceError):
        request.query = "changed"  # type: ignore[misc]


def test_parse_accepts_frozen_mapping_views() -> None:
    from types import MappingProxyType

    arguments = MappingProxyType({"query": "fixture", "include_domains": ("example.org",)})
    assert requests.WebSearchRequest.from_arguments(arguments).include_domains == ("example.org",)


@pytest.mark.parametrize("tool", sorted(TYPED))
def test_minimal_requests_parse(tool: str) -> None:
    from minimal_requests import MINIMAL_REQUESTS

    TYPED[tool].from_arguments(MINIMAL_REQUESTS[tool])


@pytest.mark.parametrize(
    ("arguments", "fragment"),
    [
        ({"date_from": "2026-02-01", "date_to": "2026-01-01"}, "date_from"),
        ({"include_domains": ["example.org"], "exclude_domains": ["EXAMPLE.org"]}, "both included and excluded"),
        ({"max_results": 2, "retrieve": {"max_sources": 3}}, "max_sources"),
    ],
)
def test_web_search_semantic_issues(arguments: dict[str, Any], fragment: str) -> None:
    request = requests.WebSearchRequest.from_arguments({"query": "fixture", **arguments})
    issues = request.semantic_issues()
    assert [issue.code.value for issue in issues] == ["invalid_request"]
    assert fragment in issues[0].message


def test_web_search_consistent_request_has_no_semantic_issues() -> None:
    request = requests.WebSearchRequest.from_arguments(
        {
            "query": "fixture",
            "date_from": "2026-01-01",
            "date_to": "2026-01-01",
            "include_domains": ["example.org"],
            "exclude_domains": ["example.net"],
            "max_results": 3,
            "retrieve": {"max_sources": 3},
        }
    )
    assert request.semantic_issues() == []


def test_image_search_domain_conflict_is_reported() -> None:
    request = requests.ImageSearchRequest.from_arguments(
        {"query": "fixture", "include_domains": ["example.org"], "exclude_domains": ["example.org"]}
    )
    assert request.semantic_issues()
