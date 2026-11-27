"""The common invocation boundary shared by every public interface.

MCP and REST both call :class:`ToolDispatcher`, so authorization, profile
exposure, input validation, request-ID assignment, failure containment and
output validation are applied identically whichever interface carried the
request (TC-005, TC-047, TC-049, TC-054).

Order of checks: the tool must exist in the canonical registry; the trusted
context must be permitted to use it; it must be implemented in this deployment
and exposed by the configured profile; its arguments must pass the projected
input schema and the handler's semantic checks. Only then is the handler run.
Every envelope the dispatcher returns has passed the tool's output schema.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Protocol

from grenslan.contracts import envelope as env
from grenslan.contracts.envelope import Issue, IssueCode, Status
from grenslan.contracts.json_input import MalformedInput, decode_arguments
from grenslan.contracts.registry import SchemaError, ToolRegistry
from grenslan.service.context import InvocationContext

_log = logging.getLogger(__name__)

_UNSUPPORTED = Issue(IssueCode.UNSUPPORTED_CAPABILITY, "this tool is not available in this deployment")
_FORBIDDEN = Issue(IssueCode.UNAUTHORIZED, "the authenticated context is not permitted to use this tool")
_INTERNAL = Issue(IssueCode.INTERNAL_ERROR, "the service could not complete the request")
_TOO_LARGE = Issue(IssueCode.RESOURCE_LIMIT, "request body exceeds the configured size limit")


class AuthorizationPolicy(Protocol):
    def permits(self, context: InvocationContext, tool: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class Invocation:
    """What a handler receives: validated, immutable arguments and trusted context."""

    request_id: str
    tool: str
    arguments: Mapping[str, Any]
    context: InvocationContext


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """A handler's result before envelope construction and output validation."""

    status: Status
    result: Mapping[str, Any] | None = None
    issues: Sequence[Issue] = ()
    operation: Mapping[str, Any] | None = None


class ToolHandler(Protocol):
    def semantic_issues(self, arguments: Mapping[str, Any]) -> Sequence[Issue]:
        """Cross-field checks the schema cannot express; empty when the request is acceptable."""
        ...

    async def __call__(self, invocation: Invocation) -> ToolOutcome: ...


class DispatchKind(Enum):
    """How the transport should frame the result (REST status, MCP error or tool result)."""

    OUTCOME = "outcome"
    UNKNOWN_TOOL = "unknown_tool"
    FORBIDDEN = "forbidden"
    INVALID_REQUEST = "invalid_request"
    TOO_LARGE = "too_large"


@dataclass(frozen=True, slots=True)
class DispatchResult:
    kind: DispatchKind
    request_id: str
    envelope: dict[str, Any] | None = field(default=None)


def _new_request_id() -> str:
    return "req_" + secrets.token_urlsafe(16)


def _freeze(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: _freeze(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(_freeze(item) for item in value)
    return value


def _schema_issues(errors: Sequence[SchemaError]) -> list[Issue]:
    return [Issue(IssueCode.INVALID_REQUEST, f"{error.location}: {error.message}") for error in errors]


class ToolDispatcher:
    def __init__(
        self,
        registry: ToolRegistry,
        *,
        handlers: Mapping[str, ToolHandler],
        policy: AuthorizationPolicy,
        profile: frozenset[str],
        max_request_bytes: int,
    ) -> None:
        unknown = set(handlers) - set(registry.tool_names)
        if unknown:
            raise ValueError(f"handlers registered for unknown tool names: {sorted(unknown)}")
        if max_request_bytes < 1:
            raise ValueError("max_request_bytes must be positive")
        self._registry = registry
        self._handlers = dict(handlers)
        self._policy = policy
        self._profile = profile
        self._max_request_bytes = max_request_bytes

    def exposed_tools(self, context: InvocationContext) -> tuple[str, ...]:
        """Tools to advertise to this context: implemented, in the profile and permitted."""
        return tuple(
            sorted(tool for tool in self._handlers if tool in self._profile and self._policy.permits(context, tool))
        )

    def _failed(self, kind: DispatchKind, request_id: str, issues: Sequence[Issue]) -> DispatchResult:
        return DispatchResult(kind, request_id, env.failed(request_id, issues=issues))

    def _gate(self, tool: str, context: InvocationContext, request_id: str) -> DispatchResult | None:
        if tool not in self._registry.tool_names:
            return DispatchResult(DispatchKind.UNKNOWN_TOOL, request_id)
        if not self._policy.permits(context, tool):
            return self._failed(DispatchKind.FORBIDDEN, request_id, [_FORBIDDEN])
        return None

    async def invoke_body(self, tool: str, body: bytes, context: InvocationContext) -> DispatchResult:
        """Decode a raw JSON argument body strictly, then dispatch it."""
        request_id = _new_request_id()
        rejected = self._gate(tool, context, request_id)
        if rejected is not None:
            return rejected
        try:
            arguments = decode_arguments(body, max_bytes=self._max_request_bytes)
        except MalformedInput as exc:
            if exc.too_large:
                return self._failed(DispatchKind.TOO_LARGE, request_id, [_TOO_LARGE])
            return self._failed(
                DispatchKind.INVALID_REQUEST, request_id, [Issue(IssueCode.INVALID_REQUEST, exc.reason)]
            )
        return await self._dispatch(tool, arguments, context, request_id)

    async def invoke(self, tool: str, arguments: Any, context: InvocationContext) -> DispatchResult:
        """Dispatch already-decoded arguments (the MCP layer decodes the JSON-RPC message)."""
        request_id = _new_request_id()
        rejected = self._gate(tool, context, request_id)
        if rejected is not None:
            return rejected
        return await self._dispatch(tool, arguments, context, request_id)

    async def _dispatch(self, tool: str, arguments: Any, context: InvocationContext, request_id: str) -> DispatchResult:
        handler = self._handlers.get(tool)
        if handler is None or tool not in self._profile:
            return self._failed(DispatchKind.OUTCOME, request_id, [_UNSUPPORTED])

        schema_errors = self._registry.input_errors(tool, arguments)
        if schema_errors:
            return self._failed(DispatchKind.INVALID_REQUEST, request_id, _schema_issues(schema_errors))
        semantic = list(handler.semantic_issues(arguments))
        if semantic:
            return self._failed(DispatchKind.INVALID_REQUEST, request_id, semantic)

        invocation = Invocation(request_id, tool, _freeze(arguments), context)
        try:
            outcome = await handler(invocation)
        except Exception as exc:  # noqa: BLE001 - provider and handler failures are contained, never surfaced raw
            _log.error(
                "tool handler failed", extra={"tool": tool, "request_id": request_id, "error": type(exc).__name__}
            )
            return self._failed(DispatchKind.OUTCOME, request_id, [_INTERNAL])
        return DispatchResult(DispatchKind.OUTCOME, request_id, self._envelope(tool, request_id, outcome))

    def _envelope(self, tool: str, request_id: str, outcome: ToolOutcome) -> dict[str, Any]:
        try:
            if outcome.status is Status.ACCEPTED:
                if outcome.operation is None:
                    raise ValueError("accepted outcome without an operation")
                built = env.accepted(request_id, outcome.operation, issues=outcome.issues)
            elif outcome.status is Status.COMPLETED:
                if outcome.result is None:
                    raise ValueError("completed outcome without a result")
                built = env.completed(request_id, outcome.result, issues=outcome.issues)
            elif outcome.status is Status.PARTIAL:
                if outcome.result is None:
                    raise ValueError("partial outcome without a result")
                built = env.partial(request_id, outcome.result, issues=outcome.issues)
            else:
                built = env.failed(request_id, issues=outcome.issues, status=outcome.status, result=outcome.result)
        except ValueError as exc:
            _log.error(
                "tool handler returned an invalid outcome",
                extra={"tool": tool, "request_id": request_id, "error": str(exc)},
            )
            return env.failed(request_id, issues=[_INTERNAL])

        errors = self._registry.output_errors(tool, built)
        if errors:
            _log.error(
                "tool result failed output schema validation",
                extra={"tool": tool, "request_id": request_id, "locations": [e.location for e in errors]},
            )
            return env.failed(request_id, issues=[_INTERNAL])
        return built
