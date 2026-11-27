"""Ingress pieces shared by the REST and MCP interfaces."""

from __future__ import annotations

import json
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

import anyio
from starlette.responses import Response
from starlette.types import Send

from grenslan.server.auth import AuthenticationFailed, ContextRejected, establish_context
from grenslan.server.authenticator import Authenticator, Principal
from grenslan.server.oauth import TokenPrincipal
from grenslan.service.context import InvocationContext
from grenslan.service.dispatch import DispatchResult


@dataclass(frozen=True, slots=True)
class IngressSettings:
    """Operator-configured ingress policy.

    ``allowed_hosts`` are host names (without port) that the ``Host`` header
    may carry. ``allowed_origins`` are exact ``Origin`` values a browser-based
    client may send; requests without an ``Origin`` header are not affected.
    """

    allowed_hosts: frozenset[str]
    allowed_origins: frozenset[str]
    max_request_bytes: int

    def __post_init__(self) -> None:
        if self.max_request_bytes < 1:
            raise ValueError("max_request_bytes must be positive")
        if not self.allowed_hosts:
            raise ValueError("at least one allowed host is required")


def encode_json(body: Any) -> bytes:
    return json.dumps(body, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")


def json_response(status: int, body: Any, headers: dict[str, str] | None = None) -> Response:
    return Response(encode_json(body), status_code=status, media_type="application/json", headers=headers)


def error_response(status: int, code: str, headers: dict[str, str] | None = None) -> Response:
    return json_response(status, {"error": code}, headers)


def unauthorized(challenge: str) -> Response:
    return error_response(401, "unauthorized", {"WWW-Authenticate": challenge})


async def send_json(
    send: Send, status: int, body: Any | None, extra_headers: list[tuple[bytes, bytes]] | None = None
) -> None:
    """Send a complete response from raw ASGI code; ``None`` sends an empty body."""
    payload = b"" if body is None else encode_json(body)
    headers = [(b"content-length", str(len(payload)).encode())]
    if body is not None:
        headers.append((b"content-type", b"application/json"))
    await send({"type": "http.response.start", "status": status, "headers": headers + (extra_headers or [])})
    await send({"type": "http.response.body", "body": payload})


def header_values(scope: dict[str, Any] | Any) -> dict[str, list[bytes]]:
    """All request headers by lowercase name, keeping every repeated value."""
    grouped: dict[str, list[bytes]] = {}
    for name, value in scope["headers"]:
        grouped.setdefault(name.decode("latin-1").lower(), []).append(value)
    return grouped


def authenticate(
    authenticator: Authenticator, headers: dict[str, list[bytes]]
) -> tuple[Principal, InvocationContext] | Response:
    authorization = headers.get("authorization", [])
    try:
        credential = authenticator.authenticate(authorization)
    except AuthenticationFailed:
        return unauthorized(authenticator.challenge(token_presented=bool(authorization)))
    try:
        return credential, establish_context(credential, headers)
    except ContextRejected as exc:
        return error_response(exc.status, "invalid_context" if exc.status == 400 else "delegation_not_permitted")


async def run_while_authorized(
    authenticator: Authenticator,
    principal: Principal,
    work: Callable[[], Awaitable[DispatchResult]],
) -> DispatchResult | None:
    """Run ``work``; return None if the principal was revoked, changed or expired before it finished."""
    with anyio.CancelScope() as scope:
        if isinstance(principal, TokenPrincipal):
            scope.deadline = anyio.current_time() + max(0.0, principal.expires_at - time.time())
        unwatch = authenticator.watch(principal, scope.cancel)
        try:
            return await work()
        finally:
            unwatch()
    return None
