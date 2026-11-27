"""Typed public result envelopes and issues."""

from __future__ import annotations

import pytest

from grenslan.contracts.envelope import (
    FAILURE_STATUSES,
    EffectiveMode,
    Issue,
    IssueCode,
    Status,
    accepted,
    completed,
    failed,
    partial,
)
from grenslan.contracts.registry import ToolRegistry

SEARCH_RESULT = {"results": [], "constraints": [], "ranking": "provider_order", "freshness": "default"}


@pytest.fixture(scope="module")
def registry() -> ToolRegistry:
    return ToolRegistry.load()


def test_issue_codes_match_schema_vocabulary(registry: ToolRegistry) -> None:
    schema_codes = registry.output_schema("web_search")["$defs"]["Issue"]["properties"]["code"]["enum"]
    assert sorted(code.value for code in IssueCode) == sorted(schema_codes)


def test_statuses_match_schema_vocabulary(registry: ToolRegistry) -> None:
    schema_statuses = registry.output_schema("web_search")["properties"]["status"]["enum"]
    assert sorted(status.value for status in Status) == sorted(schema_statuses)


def test_issue_wire_form_omits_absent_fields() -> None:
    assert Issue(IssueCode.TIMEOUT, "deadline reached").to_wire() == {"code": "timeout", "message": "deadline reached"}
    assert Issue(IssueCode.RATE_LIMITED, "slow down", retryable=True, provider="p1", retry_after_ms=1000).to_wire() == {
        "code": "rate_limited",
        "message": "slow down",
        "retryable": True,
        "provider": "p1",
        "retry_after_ms": 1000,
    }


def test_issue_requires_nonempty_message() -> None:
    with pytest.raises(ValueError, match="message"):
        Issue(IssueCode.INTERNAL_ERROR, "")


def test_completed_envelope_is_valid(registry: ToolRegistry) -> None:
    envelope = completed("req-1", SEARCH_RESULT)
    assert envelope["status"] == "completed"
    assert envelope["effective_mode"] == "sync"
    assert registry.output_errors("web_search", envelope) == []


def test_partial_requires_an_issue() -> None:
    with pytest.raises(ValueError, match="issue"):
        partial("req-1", SEARCH_RESULT, issues=())


def test_partial_envelope_is_valid(registry: ToolRegistry) -> None:
    envelope = partial("req-1", SEARCH_RESULT, issues=[Issue(IssueCode.PROVIDER_UNAVAILABLE, "one provider failed")])
    assert registry.output_errors("web_search", envelope) == []


def test_failed_requires_an_issue() -> None:
    with pytest.raises(ValueError, match="issue"):
        failed("req-1", issues=())


@pytest.mark.parametrize("status", sorted(FAILURE_STATUSES))
def test_failed_accepts_only_failure_statuses(status: Status) -> None:
    envelope = failed("req-1", issues=[Issue(IssueCode.INTERNAL_ERROR, "x")], status=status)
    assert envelope["status"] == status.value


def test_failed_rejects_success_status() -> None:
    with pytest.raises(ValueError, match="failure status"):
        failed("req-1", issues=[Issue(IssueCode.INTERNAL_ERROR, "x")], status=Status.COMPLETED)


@pytest.mark.parametrize("tool", ToolRegistry.load().tool_names)
def test_failure_envelope_is_valid_for_every_tool(registry: ToolRegistry, tool: str) -> None:
    envelope = failed("req-1", issues=[Issue(IssueCode.UNSUPPORTED_CAPABILITY, "not available")])
    assert registry.output_errors(tool, envelope) == []


def test_accepted_envelope_is_valid(registry: ToolRegistry) -> None:
    envelope = accepted("req-1", {"operation_id": "op-1", "state": "queued", "results_available": False})
    assert envelope["effective_mode"] == EffectiveMode.ASYNC.value
    assert registry.output_errors("web_search", envelope) == []


def test_accepted_requires_initial_state() -> None:
    with pytest.raises(ValueError, match="queued or running"):
        accepted("req-1", {"operation_id": "op-1", "state": "completed", "results_available": True})
