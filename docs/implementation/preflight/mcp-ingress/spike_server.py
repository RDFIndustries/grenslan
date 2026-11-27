"""Disposable preflight spike: modern-only MCP over direct HTTPS.

Not Grenslan service code. Demonstrates that an ingress gate placed in front
of the public MCP SDK Streamable HTTP app keeps the SDK's handshake-era path
unreachable, and that uvicorn can serve the app directly over TLS >= 1.2.
"""
from __future__ import annotations

import json
import ssl
import sys
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from starlette.applications import Starlette
from starlette.routing import Mount

from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker
from mcp.server import Server, ServerRequestContext
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import CallToolRequestParams, CallToolResult, ListToolsResult, PaginatedRequestParams, TextContent, Tool

SUPPORTED = "2026-07-28"
HEADER_MISMATCH = -32020
UNSUPPORTED_PROTOCOL_VERSION = -32022
TOKEN = "spike-test-token"  # test-only fixture credential
ALLOWED_ORIGINS = {"https://localhost"}
REGISTRY_PATH = Path(__file__).resolve().parents[3] / "contracts" / "TOOL_SCHEMAS.json"


def project(registry: dict, ref: str) -> dict:
    """Self-contained schema: the referenced definition plus every reachable local $def."""
    defs = registry["$defs"]

    def refs(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "$ref":
                    yield v
                else:
                    yield from refs(v)
        elif isinstance(node, list):
            for v in node:
                yield from refs(v)

    root = dict(defs[ref.split("/")[-1]])
    reachable: dict = {}
    pending = list(refs(root))
    while pending:
        name = pending.pop().split("/")[-1]
        if name not in reachable:
            reachable[name] = defs[name]
            pending.extend(refs(defs[name]))
    return {"$schema": registry["$schema"], "$defs": reachable, **root}


REGISTRY = json.loads(REGISTRY_PATH.read_text())
WEB_SEARCH = REGISTRY["tools"]["web_search"]
INPUT_SCHEMA = project(REGISTRY, WEB_SEARCH["inputSchema"]["$ref"])
OUTPUT_SCHEMA = project(REGISTRY, WEB_SEARCH["outputSchema"]["$ref"])
INPUT_VALIDATOR = Draft202012Validator(INPUT_SCHEMA, format_checker=FormatChecker())
OUTPUT_VALIDATOR = Draft202012Validator(OUTPUT_SCHEMA, format_checker=FormatChecker())
TOOL = Tool(name="web_search", description=WEB_SEARCH["description"], input_schema=INPUT_SCHEMA, output_schema=OUTPUT_SCHEMA)


async def list_tools(ctx: ServerRequestContext, params: PaginatedRequestParams | None) -> ListToolsResult:
    return ListToolsResult(tools=[TOOL])


async def call_tool(ctx: ServerRequestContext, params: CallToolRequestParams) -> CallToolResult:
    args = params.arguments or {}
    if params.name != "web_search" or not INPUT_VALIDATOR.is_valid(args):
        return CallToolResult(content=[TextContent(type="text", text="invalid invocation")], is_error=True)
    envelope = {"schema_version": "1.0", "request_id": "spike-req", "status": "completed", "effective_mode": "sync",
                "issues": [], "result": {"results": [], "constraints": [], "ranking": "provider_order", "freshness": "default"}}
    OUTPUT_VALIDATOR.validate(envelope)
    return CallToolResult(content=[TextContent(type="text", text="0 results")], structured_content=envelope)


mcp = Server("grenslan-spike", on_list_tools=list_tools, on_call_tool=call_tool)


def _error(status: int, code: int | None, message: str, data: dict | None = None,
           extra_headers: list[tuple[bytes, bytes]] | None = None):
    body = b""
    headers = [(b"content-length", b"0")]
    if code is not None:
        err: dict = {"code": code, "message": message}
        if data is not None:
            err["data"] = data
        body = json.dumps({"jsonrpc": "2.0", "error": err}).encode()
        headers = [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    return status, headers + (extra_headers or []), body


class ModernOnlyGate:
    """Reject everything the SDK would route to its handshake-era handler."""

    def __init__(self, app, path: str = "/mcp") -> None:
        self.app = app
        self.path = path

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"].rstrip("/") != self.path:
            await self.app(scope, receive, send)
            return
        headers = scope["headers"]
        values = lambda name: [v for k, v in headers if k == name]  # noqa: E731
        rejection = None
        if scope["method"] != "POST":
            rejection = _error(405, None, "", extra_headers=[(b"allow", b"POST")])
        elif any(o.decode("latin-1") not in ALLOWED_ORIGINS for o in values(b"origin")) or len(values(b"origin")) > 1:
            rejection = _error(403, -32600, "Origin not allowed")
        else:
            auth = values(b"authorization")
            if len(auth) != 1 or auth[0] != f"Bearer {TOKEN}".encode():
                rejection = _error(401, None, "", extra_headers=[(b"www-authenticate", b"Bearer")])
            else:
                versions = values(b"mcp-protocol-version")
                if len(versions) != 1:
                    rejection = _error(400, HEADER_MISMATCH, "Exactly one MCP-Protocol-Version header is required")
                elif versions[0].decode("latin-1") != SUPPORTED:
                    rejection = _error(400, UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version",
                                       {"supported": [SUPPORTED], "requested": versions[0].decode("latin-1")})
        if rejection is not None:
            status, hdrs, body = rejection
            await send({"type": "http.response.start", "status": status, "headers": hdrs})
            await send({"type": "http.response.body", "body": body})
            return
        # Legacy-era headers carry no meaning in this revision; drop them.
        scope = dict(scope)
        scope["headers"] = [(k, v) for k, v in headers if k not in (b"mcp-session-id", b"last-event-id")]
        await self.app(scope, receive, send)


@asynccontextmanager
async def lifespan(app: Starlette) -> AsyncIterator[None]:
    async with mcp.session_manager.run():
        yield


security = TransportSecuritySettings(allowed_hosts=["localhost:*"], allowed_origins=sorted(ALLOWED_ORIGINS))
inner = Starlette(routes=[Mount("/", app=mcp.streamable_http_app(stateless_http=True, transport_security=security))],
                  lifespan=lifespan)
app = ModernOnlyGate(inner)


def tls_factory(config, default):
    ctx = default()
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    return ctx


if __name__ == "__main__":
    cert, key, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
    uvicorn.run(app, host="127.0.0.1", port=port, ssl_certfile=cert, ssl_keyfile=key,
                ssl_context_factory=tls_factory, log_level="warning")
