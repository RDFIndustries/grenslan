"""The common authorized invocation boundary shared by MCP and REST."""

from __future__ import annotations

import asyncio
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import pytest

from grenslan.contracts.envelope import Issue, IssueCode, Status
from grenslan.contracts.registry import ToolRegistry
from grenslan.service.context import InvocationContext
from grenslan.service.dispatch import ArgumentLimits, DispatchKind, Invocation, ToolDispatcher, ToolOutcome
from grenslan.service.profiles import profile_tools

from minimal_requests import MINIMAL_REQUESTS

SEARCH_RESULT = {"results": [], "constraints": [], "ranking": "provider_order", "freshness": "default"}
CONTEXT = InvocationContext(application_id="app-a", user_id="user-1", agent_id="agent-1", instance_id=None)


@pytest.fixture(scope="module")
def registry() -> ToolRegistry:
    return ToolRegistry.load()


@dataclass
class RecordingHandler:
    """Test-only handler returning a configured outcome and recording invocations."""

    outcome: ToolOutcome | None = None
    error: BaseException | None = None
    semantic: Sequence[Issue] = ()
    calls: list[Invocation] = field(default_factory=list)

    def semantic_issues(self, arguments: Mapping[str, Any]) -> Sequence[Issue]:
        return self.semantic

    async def __call__(self, invocation: Invocation) -> ToolOutcome:
        self.calls.append(invocation)
        if self.error is not None:
            raise self.error
        assert self.outcome is not None
        return self.outcome


class AllowAll:
    def permits(self, context: InvocationContext, tool: str) -> bool:
        return True


@dataclass
class AllowOnly:
    tools: frozenset[str]

    def permits(self, context: InvocationContext, tool: str) -> bool:
        return tool in self.tools


def completed_search() -> RecordingHandler:
    return RecordingHandler(outcome=ToolOutcome(status=Status.COMPLETED, result=SEARCH_RESULT))


def make(
    registry: ToolRegistry,
    handlers: Mapping[str, RecordingHandler],
    *,
    policy: Any = None,
    profile: frozenset[str] | None = None,
    argument_limits: ArgumentLimits | None = None,
) -> ToolDispatcher:
    return ToolDispatcher(
        registry,
        handlers=handlers,
        policy=policy or AllowAll(),
        profile=profile if profile is not None else profile_tools("full"),
        max_request_bytes=64 * 1024,
        argument_limits=argument_limits or ArgumentLimits(max_string_chars=4096, max_array_items=100, max_depth=16),
    )


async def test_unknown_tool_has_no_envelope(registry: ToolRegistry) -> None:
    outcome = await make(registry, {}).invoke("shell_exec", {}, CONTEXT)
    assert outcome.kind is DispatchKind.UNKNOWN_TOOL
    assert outcome.envelope is None


async def test_unpermitted_tool_is_forbidden_and_not_executed(registry: ToolRegistry) -> None:
    handler = completed_search()
    dispatcher = make(registry, {"web_search": handler}, policy=AllowOnly(frozenset()))
    outcome = await dispatcher.invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.kind is DispatchKind.FORBIDDEN
    assert outcome.envelope is not None
    assert outcome.envelope["issues"][0]["code"] == IssueCode.UNAUTHORIZED.value
    assert registry.output_errors("web_search", outcome.envelope) == []
    assert handler.calls == []


async def test_tool_outside_profile_is_not_executed(registry: ToolRegistry) -> None:
    handler = completed_search()
    dispatcher = make(registry, {"web_search": handler}, profile=profile_tools("custom", custom={"web_open"}))
    outcome = await dispatcher.invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.kind is DispatchKind.OUTCOME
    assert outcome.envelope is not None
    assert outcome.envelope["status"] == "failed"
    assert outcome.envelope["issues"][0]["code"] == IssueCode.UNSUPPORTED_CAPABILITY.value
    assert handler.calls == []


@pytest.mark.parametrize("tool", sorted(MINIMAL_REQUESTS))
async def test_unimplemented_tool_reports_unsupported_capability(registry: ToolRegistry, tool: str) -> None:
    outcome = await make(registry, {}).invoke(tool, MINIMAL_REQUESTS[tool], CONTEXT)
    assert outcome.kind is DispatchKind.OUTCOME
    assert outcome.envelope is not None
    assert outcome.envelope["status"] == "failed"
    assert outcome.envelope["issues"][0]["code"] == IssueCode.UNSUPPORTED_CAPABILITY.value
    assert registry.output_errors(tool, outcome.envelope) == []


async def test_schema_invalid_input_is_rejected_before_execution(registry: ToolRegistry) -> None:
    handler = completed_search()
    outcome = await make(registry, {"web_search": handler}).invoke("web_search", {"max_results": 5}, CONTEXT)
    assert outcome.kind is DispatchKind.INVALID_REQUEST
    assert outcome.envelope is not None
    assert outcome.envelope["issues"][0]["code"] == IssueCode.INVALID_REQUEST.value
    assert registry.output_errors("web_search", outcome.envelope) == []
    assert handler.calls == []


async def test_forged_identity_argument_is_rejected(registry: ToolRegistry) -> None:
    handler = completed_search()
    outcome = await make(registry, {"web_search": handler}).invoke(
        "web_search", {"query": "x", "application_id": "app-b"}, CONTEXT
    )
    assert outcome.kind is DispatchKind.INVALID_REQUEST
    assert handler.calls == []


async def test_semantic_issues_reject_before_execution(registry: ToolRegistry) -> None:
    handler = completed_search()
    handler.semantic = [Issue(IssueCode.INVALID_REQUEST, "date_from is after date_to")]
    outcome = await make(registry, {"web_search": handler}).invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.kind is DispatchKind.INVALID_REQUEST
    assert outcome.envelope is not None
    assert outcome.envelope["issues"][0]["message"] == "date_from is after date_to"
    assert handler.calls == []


async def test_successful_invocation_passes_trusted_context_and_arguments(registry: ToolRegistry) -> None:
    handler = completed_search()
    outcome = await make(registry, {"web_search": handler}).invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.kind is DispatchKind.OUTCOME
    assert outcome.envelope is not None
    assert outcome.envelope["status"] == "completed"
    assert outcome.envelope["result"] == SEARCH_RESULT
    assert registry.output_errors("web_search", outcome.envelope) == []
    (call,) = handler.calls
    assert call.context is CONTEXT
    assert call.arguments == {"query": "x"}
    assert call.request_id == outcome.envelope["request_id"]


async def test_request_ids_are_server_assigned_and_unique(registry: ToolRegistry) -> None:
    dispatcher = make(registry, {"web_search": completed_search()})
    ids = {(await dispatcher.invoke("web_search", {"query": "x"}, CONTEXT)).request_id for _ in range(50)}
    assert len(ids) == 50
    assert all(len(request_id) >= 16 for request_id in ids)


async def test_handler_cannot_mutate_caller_arguments(registry: ToolRegistry) -> None:
    arguments = {"query": "x", "include_domains": ["example.org"]}
    handler = completed_search()
    await make(registry, {"web_search": handler}).invoke("web_search", arguments, CONTEXT)
    with pytest.raises(TypeError):
        handler.calls[0].arguments["query"] = "changed"  # type: ignore[index]


async def test_handler_exception_is_contained_without_leaking_detail(registry: ToolRegistry) -> None:
    handler = RecordingHandler(error=RuntimeError("connect to 10.0.0.5 with token sk-secret failed"))
    outcome = await make(registry, {"web_search": handler}).invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.kind is DispatchKind.OUTCOME
    assert outcome.envelope is not None
    assert outcome.envelope["status"] == "failed"
    assert outcome.envelope["issues"][0]["code"] == IssueCode.INTERNAL_ERROR.value
    text = json.dumps(outcome.envelope)
    assert "sk-secret" not in text
    assert "10.0.0.5" not in text


async def test_schema_invalid_handler_result_becomes_internal_error(registry: ToolRegistry) -> None:
    handler = RecordingHandler(outcome=ToolOutcome(status=Status.COMPLETED, result={"results": "not-a-list"}))
    outcome = await make(registry, {"web_search": handler}).invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.envelope is not None
    assert outcome.envelope["status"] == "failed"
    assert outcome.envelope["issues"][0]["code"] == IssueCode.INTERNAL_ERROR.value
    assert registry.output_errors("web_search", outcome.envelope) == []


async def test_partial_without_issue_becomes_internal_error(registry: ToolRegistry) -> None:
    handler = RecordingHandler(outcome=ToolOutcome(status=Status.PARTIAL, result=SEARCH_RESULT))
    outcome = await make(registry, {"web_search": handler}).invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.envelope is not None
    assert outcome.envelope["issues"][0]["code"] == IssueCode.INTERNAL_ERROR.value


async def test_genuine_empty_result_is_completed_not_failure(registry: ToolRegistry) -> None:
    outcome = await make(registry, {"web_search": completed_search()}).invoke("web_search", {"query": "x"}, CONTEXT)
    assert outcome.envelope is not None
    assert outcome.envelope["status"] == "completed"
    assert outcome.envelope["result"]["results"] == []
    assert outcome.envelope["issues"] == []


async def test_cancellation_propagates(registry: ToolRegistry) -> None:
    handler = RecordingHandler(error=asyncio.CancelledError())
    with pytest.raises(asyncio.CancelledError):
        await make(registry, {"web_search": handler}).invoke("web_search", {"query": "x"}, CONTEXT)


async def test_body_dispatch_decodes_strictly(registry: ToolRegistry) -> None:
    handler = completed_search()
    outcome = await make(registry, {"web_search": handler}).invoke_body(
        "web_search", b'{"query": "a", "query": "b"}', CONTEXT
    )
    assert outcome.kind is DispatchKind.INVALID_REQUEST
    assert outcome.envelope is not None
    assert registry.output_errors("web_search", outcome.envelope) == []
    assert handler.calls == []


async def test_body_dispatch_rejects_oversized_body(registry: ToolRegistry) -> None:
    body = json.dumps({"query": "x" * (70 * 1024)}).encode()
    outcome = await make(registry, {"web_search": completed_search()}).invoke_body("web_search", body, CONTEXT)
    assert outcome.kind is DispatchKind.TOO_LARGE


async def test_body_dispatch_for_unknown_tool_does_not_parse(registry: ToolRegistry) -> None:
    outcome = await make(registry, {}).invoke_body("shell_exec", b"not json", CONTEXT)
    assert outcome.kind is DispatchKind.UNKNOWN_TOOL


async def test_exposed_tools_are_implemented_profiled_and_permitted(registry: ToolRegistry) -> None:
    handlers = {"web_search": completed_search(), "web_open": completed_search(), "document_read": completed_search()}
    dispatcher = make(
        registry,
        handlers,
        policy=AllowOnly(frozenset({"web_search", "document_read"})),
        profile=profile_tools("basic"),
    )
    assert dispatcher.exposed_tools(CONTEXT) == ("web_search",)


def test_handler_for_unknown_tool_is_rejected_at_construction(registry: ToolRegistry) -> None:
    with pytest.raises(ValueError, match="unknown tool"):
        make(registry, {"shell_exec": completed_search()})


SMALL = ArgumentLimits(max_string_chars=16, max_array_items=2, max_depth=3)


@pytest.mark.parametrize(
    ("arguments", "location"),
    [
        ({"query": "x" * 17}, "/query"),
        ({"query": "x", "include_domains": ["a", "b", "c"]}, "/include_domains"),
        ({"query": "x", "include_domains": ["a", "y" * 17]}, "/include_domains/1"),
        ({"query": "x", "cursor": "c" * 17}, "/cursor"),
    ],
)
async def test_configured_argument_bounds_reject_before_execution(
    registry: ToolRegistry, arguments: dict[str, Any], location: str
) -> None:
    handler = completed_search()
    outcome = await make(registry, {"web_search": handler}, argument_limits=SMALL).invoke(
        "web_search", arguments, CONTEXT
    )
    assert outcome.kind is DispatchKind.INVALID_REQUEST
    assert outcome.envelope is not None
    assert outcome.envelope["issues"][0]["message"].startswith(location + ":")
    assert handler.calls == []


async def test_object_keys_count_toward_string_bound(registry: ToolRegistry) -> None:
    outcome = await make(registry, {"web_search": completed_search()}, argument_limits=SMALL).invoke(
        "web_search", {"query": "x", "k" * 17: 1}, CONTEXT
    )
    assert outcome.kind is DispatchKind.INVALID_REQUEST


async def test_decoded_arguments_depth_is_bounded_without_recursion(registry: ToolRegistry) -> None:
    nested: Any = 1
    for _ in range(100_000):
        nested = [nested]
    limits = ArgumentLimits(max_string_chars=16, max_array_items=2, max_depth=16)
    outcome = await make(registry, {"web_search": completed_search()}, argument_limits=limits).invoke(
        "web_search", {"query": "x", "include_domains": nested}, CONTEXT
    )
    assert outcome.kind is DispatchKind.INVALID_REQUEST
    assert outcome.envelope is not None
    assert "depth" in outcome.envelope["issues"][0]["message"]


async def test_arguments_within_bounds_are_accepted(registry: ToolRegistry) -> None:
    outcome = await make(registry, {"web_search": completed_search()}, argument_limits=SMALL).invoke(
        "web_search", {"query": "x" * 16, "include_domains": ["a", "b"]}, CONTEXT
    )
    assert outcome.kind is DispatchKind.OUTCOME


def test_argument_limits_must_be_positive() -> None:
    with pytest.raises(ValueError, match="positive"):
        ArgumentLimits(max_string_chars=0, max_array_items=1, max_depth=1)
