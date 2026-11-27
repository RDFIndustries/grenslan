"""The HTTPS application: REST tool invocation and the MCP endpoint (TC-002, TC-048, TC-050).

Every request first passes the request gate. It needs exactly one ``Host``
header naming a configured host, and an ``Origin``, if present, must be
configured; a present but unlisted origin gets 403. Each protected request is
then authenticated independently. The trusted context is established from the
credential and any permitted delegation headers, and the request is handed to
the common dispatcher. If the credential is revoked or changed while its work
runs, the work is cancelled.

Routes not yet provided by an implemented milestone (artifact delivery and
uploads) are not registered, so they return 404 instead of a placeholder.
"""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import Response
from starlette.routing import Route
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from grenslan.contracts.envelope import Status
from grenslan.contracts.registry import ToolRegistry
from grenslan.server.app_support import (
    IngressSettings,
    authenticate,
    error_response,
    header_values,
    json_response,
    run_while_authorized,
    send_json,
    unauthorized,
)
from grenslan.server.auth import CredentialStore
from grenslan.server.mcp_endpoint import build_mcp_app
from grenslan.service.dispatch import DispatchKind, DispatchResult, ToolDispatcher

__all__ = ["IngressSettings", "create_app"]

_SECURITY_HEADERS = [(b"cache-control", b"no-store"), (b"x-content-type-options", b"nosniff")]
_STATUS_BY_KIND = {
    DispatchKind.UNKNOWN_TOOL: 404,
    DispatchKind.FORBIDDEN: 403,
    DispatchKind.INVALID_REQUEST: 400,
    DispatchKind.TOO_LARGE: 413,
}


class _BodyTooLarge(Exception):
    pass


def _is_json(content_types: list[bytes]) -> bool:
    if len(content_types) != 1:
        return False
    media_type, _, parameters = content_types[0].decode("latin-1").partition(";")
    if media_type.strip().lower() != "application/json":
        return False
    for parameter in filter(None, (p.strip() for p in parameters.split(";"))):
        name, _, value = parameter.partition("=")
        if name.strip().lower() == "charset" and value.strip().strip('"').lower() != "utf-8":
            return False
    return True


async def _read_body(request: Request, limit: int) -> bytes:
    declared = request.headers.get("content-length")
    if declared is not None and declared.isdigit() and int(declared) > limit:
        raise _BodyTooLarge
    received = bytearray()
    async for chunk in request.stream():
        received.extend(chunk)
        if len(received) > limit:
            raise _BodyTooLarge
    return bytes(received)


def _rest_response(result: DispatchResult) -> Response:
    if result.envelope is None:
        return error_response(404, "unknown_tool")
    if result.kind is DispatchKind.OUTCOME:
        status = 202 if result.envelope["status"] == Status.ACCEPTED.value else 200
    else:
        status = _STATUS_BY_KIND[result.kind]
    return json_response(status, result.envelope)


def _rest_endpoint(
    dispatcher: ToolDispatcher, store: CredentialStore, settings: IngressSettings
) -> Callable[[Request], Awaitable[Response]]:
    async def invoke_tool(request: Request) -> Response:
        headers = header_values(request.scope)
        authenticated = authenticate(store, headers)
        if isinstance(authenticated, Response):
            return authenticated
        credential, context = authenticated
        if not _is_json(headers.get("content-type", [])):
            return error_response(400, "unsupported_content_type")
        try:
            body = await _read_body(request, settings.max_request_bytes)
        except _BodyTooLarge:
            return error_response(413, "request_too_large")
        tool = request.path_params["tool_name"]
        result = await run_while_authorized(store, credential, lambda: dispatcher.invoke_body(tool, body, context))
        if result is None:
            return unauthorized()
        return _rest_response(result)

    return invoke_tool


def _host_name(value: bytes) -> str | None:
    try:
        text = value.decode("ascii").strip().lower()
    except UnicodeDecodeError:
        return None
    if text.startswith("["):
        end = text.find("]")
        return text[1:end] if end > 0 else None
    return text.rsplit(":", 1)[0] if text.count(":") == 1 else text


class RequestGate:
    """Host and Origin checks for every HTTP request, plus no-store and nosniff on every response."""

    def __init__(self, app: ASGIApp, settings: IngressSettings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                existing = {name.lower() for name, _ in message.get("headers", [])}
                message = dict(message)
                message["headers"] = list(message.get("headers", [])) + [
                    header for header in _SECURITY_HEADERS if header[0] not in existing
                ]
            await send(message)

        headers = header_values(scope)
        hosts = headers.get("host", [])
        if len(hosts) != 1 or _host_name(hosts[0]) not in self.settings.allowed_hosts:
            await send_json(send_with_headers, 400, {"error": "host_not_allowed"})
            return
        origins = headers.get("origin", [])
        if origins and (len(origins) != 1 or origins[0].decode("latin-1") not in self.settings.allowed_origins):
            body = {"jsonrpc": "2.0", "error": {"code": -32600, "message": "origin not allowed"}}
            await send_json(send_with_headers, 403, body)
            return
        await self.app(scope, receive, send_with_headers)


def create_app(
    *,
    registry: ToolRegistry,
    dispatcher: ToolDispatcher,
    credentials: CredentialStore,
    settings: IngressSettings,
) -> ASGIApp:
    mcp_app, mcp_lifespan = build_mcp_app(registry, dispatcher, credentials, settings)

    @asynccontextmanager
    async def lifespan(_app: Starlette) -> AsyncIterator[None]:
        async with mcp_lifespan():
            yield

    routes = [
        Route("/api/v1/tools/{tool_name}", _rest_endpoint(dispatcher, credentials, settings), methods=["POST"]),
        Route("/mcp", mcp_app),
    ]
    return RequestGate(Starlette(routes=routes, lifespan=lifespan), settings)
