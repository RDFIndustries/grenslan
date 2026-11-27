"""MCP Streamable HTTP endpoint, current protocol revision only (TC-001, TC-048).

The SDK always serves both protocol eras. :class:`McpGate` runs in front of it
and admits only POST requests that carry exactly one ``MCP-Protocol-Version``
header naming the supported revision. Every handshake-era request therefore
fails before the SDK sees it, and legacy session headers are removed.

Each request is authenticated by the gate. The resulting trusted context is
placed in the ASGI scope, where the tool handlers read it. Tool discovery lists
only the tools the context may use, with the canonical projected schemas. Tool
results carry the canonical envelope as ``structuredContent``.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.types import (
    CallToolRequestParams,
    CallToolResult,
    ListToolsResult,
    PaginatedRequestParams,
    TextContent,
    Tool,
)
from mcp_types.jsonrpc import INVALID_PARAMS, INVALID_REQUEST
from starlette.applications import Starlette
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from grenslan import __version__
from grenslan.contracts.envelope import FAILURE_STATUSES
from grenslan.contracts.registry import ToolRegistry
from grenslan.server.app_support import IngressSettings, authenticate, header_values, run_while_authorized, send_json
from grenslan.server.auth import ApplicationCredential, CredentialStore
from grenslan.service.context import InvocationContext
from grenslan.service.dispatch import DispatchKind, ToolDispatcher

SUPPORTED_PROTOCOL_VERSION = "2026-07-28"
HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022
MAX_TEXT_CONTENT_BYTES = 8192
_CONTEXT_KEY = "grenslan_context"
_CREDENTIAL_KEY = "grenslan_credential"
_LEGACY_HEADERS = (b"mcp-session-id", b"last-event-id")
_FAILURE_VALUES = frozenset(status.value for status in FAILURE_STATUSES)


def _jsonrpc_error(code: int, message: str, data: Any = None) -> dict[str, Any]:
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "error": error}


def _trusted(ctx: ServerRequestContext[Any, Any]) -> tuple[InvocationContext, ApplicationCredential]:
    request = ctx.request
    state = request.scope.get("state", {}) if request is not None else {}
    context, credential = state.get(_CONTEXT_KEY), state.get(_CREDENTIAL_KEY)
    if not isinstance(context, InvocationContext) or not isinstance(credential, ApplicationCredential):
        raise MCPError(INVALID_REQUEST, "request was not authenticated")
    return context, credential


def _text_summary(envelope: dict[str, Any]) -> str:
    serialized = json.dumps(envelope, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
    if len(serialized.encode("utf-8")) <= MAX_TEXT_CONTENT_BYTES:
        return serialized
    return f"status={envelope['status']} request_id={envelope['request_id']}; the full envelope is in structuredContent"


def build_mcp_server(registry: ToolRegistry, dispatcher: ToolDispatcher, store: CredentialStore) -> Server[Any]:
    tools = {
        name: Tool(
            name=name,
            description=registry.description(name),
            input_schema=registry.input_schema(name),
            output_schema=registry.output_schema(name),
        )
        for name in registry.tool_names
    }

    async def list_tools(ctx: ServerRequestContext[Any, Any], params: PaginatedRequestParams | None) -> ListToolsResult:
        context, _ = _trusted(ctx)
        return ListToolsResult(tools=[tools[name] for name in dispatcher.exposed_tools(context)])

    async def call_tool(ctx: ServerRequestContext[Any, Any], params: CallToolRequestParams) -> CallToolResult:
        context, credential = _trusted(ctx)
        arguments = params.arguments if params.arguments is not None else {}
        result = await run_while_authorized(
            store, credential, lambda: dispatcher.invoke(params.name, arguments, context)
        )
        if result is None:
            raise MCPError(INVALID_REQUEST, "the credential is no longer authorized")
        if result.kind is DispatchKind.UNKNOWN_TOOL or result.envelope is None:
            raise MCPError(INVALID_PARAMS, "unknown tool")
        envelope = result.envelope
        return CallToolResult(
            content=[TextContent(type="text", text=_text_summary(envelope))],
            structured_content=envelope,
            is_error=envelope["status"] in _FAILURE_VALUES,
        )

    return Server("grenslan", version=__version__, on_list_tools=list_tools, on_call_tool=call_tool)


class McpGate:
    """Admit only authenticated, current-revision POST requests to the SDK app."""

    def __init__(self, sdk_app: ASGIApp, store: CredentialStore, settings: IngressSettings) -> None:
        self._sdk_app = sdk_app
        self._store = store
        self._settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["method"] != "POST":
            await send_json(send, 405, None, [(b"allow", b"POST")])
            return
        headers = header_values(scope)
        authenticated = authenticate(self._store, headers)
        if not isinstance(authenticated, tuple):
            await authenticated(scope, receive, send)
            return
        credential, context = authenticated
        versions = headers.get("mcp-protocol-version", [])
        if len(versions) != 1:
            mismatch = _jsonrpc_error(HEADER_MISMATCH, "exactly one MCP-Protocol-Version header is required")
            await send_json(send, 400, mismatch)
            return
        requested = versions[0].decode("latin-1")
        if requested != SUPPORTED_PROTOCOL_VERSION:
            data = {"supported": [SUPPORTED_PROTOCOL_VERSION], "requested": requested}
            await send_json(
                send, 400, _jsonrpc_error(UNSUPPORTED_PROTOCOL_VERSION, "unsupported protocol version", data)
            )
            return

        body = await _read_bounded(receive, self._settings.max_request_bytes, headers)
        if body is None:
            await send_json(send, 413, {"error": "request_too_large"})
            return

        forwarded = dict(scope)
        forwarded["headers"] = [(k, v) for k, v in scope["headers"] if k.lower() not in _LEGACY_HEADERS]
        state = dict(scope.get("state", {}))
        state[_CONTEXT_KEY] = context
        state[_CREDENTIAL_KEY] = credential
        forwarded["state"] = state
        await self._sdk_app(forwarded, _replay(body, receive), send)


async def _read_bounded(receive: Receive, limit: int, headers: dict[str, list[bytes]]) -> bytes | None:
    declared = headers.get("content-length", [])
    if len(declared) == 1 and declared[0].isdigit() and int(declared[0]) > limit:
        return None
    received = bytearray()
    while True:
        message = await receive()
        if message["type"] != "http.request":
            return bytes(received)
        received.extend(message.get("body", b""))
        if len(received) > limit:
            return None
        if not message.get("more_body", False):
            return bytes(received)


def _replay(body: bytes, receive: Receive) -> Receive:
    delivered = False

    async def replay() -> Message:
        nonlocal delivered
        if not delivered:
            delivered = True
            return {"type": "http.request", "body": body, "more_body": False}
        return await receive()

    return replay


def build_mcp_app(
    registry: ToolRegistry, dispatcher: ToolDispatcher, store: CredentialStore, settings: IngressSettings
) -> tuple[ASGIApp, Any]:
    """Return the gated MCP ASGI app and an async context manager for its lifespan."""
    server = build_mcp_server(registry, dispatcher, store)
    # Host and Origin are enforced for every route by the outer request gate.
    sdk_app: Starlette = server.streamable_http_app(
        stateless_http=True,
        json_response=True,
        max_request_body_size=settings.max_request_bytes,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @asynccontextmanager
    async def lifespan() -> AsyncIterator[None]:
        async with server.session_manager.run():
            yield

    return McpGate(sdk_app, store, settings), lifespan
