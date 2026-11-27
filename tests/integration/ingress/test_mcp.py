"""MCP Streamable HTTP over real local HTTPS, current revision only (TC-001, TC-048, F-G02, F-G03)."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from ingress_fixtures import ALLOWED_ORIGIN, DELEGATING_TOKEN, TOKEN, RunningServer, running_server, shared_registry
from tls_fixtures import TlsMaterial, make_tls_material

pytestmark = pytest.mark.integration
VERSION = "2026-07-28"


@pytest.fixture
def material(tmp_path: Path) -> TlsMaterial:
    return make_tls_material(tmp_path)


@pytest.fixture
async def server(material: TlsMaterial) -> AsyncIterator[RunningServer]:
    async with running_server(material, max_request_bytes=8192) as running:
        yield running


@pytest.fixture
async def http(server: RunningServer) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(verify=server.material.client_context(), trust_env=False) as client:
        yield client


def mcp_client(server: RunningServer, http: httpx2.AsyncClient) -> Client:
    return Client(
        streamable_http_client(f"{server.base_url}/mcp", http_client=http, terminate_on_close=False), mode=VERSION
    )


def headers(method: str, *, token: str | None = TOKEN, name: str | None = None, **extra: str) -> dict[str, str]:
    result = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
        "MCP-Protocol-Version": VERSION,
        "Mcp-Method": method,
    }
    if token is not None:
        result["Authorization"] = f"Bearer {token}"
    if name is not None:
        result["Mcp-Name"] = name
    result.update(extra)
    return result


def rpc(method: str, params: dict[str, Any] | None = None) -> bytes:
    meta = {
        "io.modelcontextprotocol/protocolVersion": VERSION,
        "io.modelcontextprotocol/clientInfo": {"name": "grenslan-test", "version": "0"},
        "io.modelcontextprotocol/clientCapabilities": {},
    }
    return json.dumps(
        {"jsonrpc": "2.0", "id": 1, "method": method, "params": {**(params or {}), "_meta": meta}}
    ).encode()


async def test_tool_discovery_lists_only_permitted_implemented_tools(
    server: RunningServer, http: httpx2.AsyncClient
) -> None:
    http.headers["Authorization"] = f"Bearer {TOKEN}"
    async with mcp_client(server, http) as client:
        tools = (await client.list_tools()).tools
    assert [tool.name for tool in tools] == ["web_search"]
    registry = shared_registry()
    assert tools[0].input_schema == registry.input_schema("web_search")
    assert tools[0].output_schema == registry.output_schema("web_search")


async def test_call_returns_canonical_envelope_as_structured_content(
    server: RunningServer, http: httpx2.AsyncClient
) -> None:
    http.headers["Authorization"] = f"Bearer {TOKEN}"
    async with mcp_client(server, http) as client:
        result = await client.call_tool("web_search", {"query": "fixture"})
        assert client.protocol_version == VERSION
    assert result.is_error is False
    envelope = result.structured_content
    assert envelope is not None
    assert envelope["status"] == "completed"
    validator = Draft202012Validator(shared_registry().output_schema("web_search"), format_checker=FormatChecker())
    assert validator.is_valid(envelope)
    assert result.content
    (call,) = server.handler.calls
    assert call.context.application_id == "app-a"


async def test_forged_identity_argument_is_a_tool_error(server: RunningServer, http: httpx2.AsyncClient) -> None:
    http.headers["Authorization"] = f"Bearer {TOKEN}"
    async with mcp_client(server, http) as client:
        result = await client.call_tool("web_search", {"query": "x", "application_id": "app-z"})
    assert result.is_error is True
    assert result.structured_content is not None
    assert result.structured_content["issues"][0]["code"] == "invalid_request"
    assert server.handler.calls == []


async def test_unpermitted_tool_is_a_tool_error(server: RunningServer, http: httpx2.AsyncClient) -> None:
    http.headers["Authorization"] = f"Bearer {TOKEN}"
    async with mcp_client(server, http) as client:
        result = await client.call_tool("image_search", {"query": "x"})
    assert result.is_error is True
    assert result.structured_content is not None
    assert result.structured_content["issues"][0]["code"] == "unauthorized"


async def test_unknown_tool_is_a_protocol_error(server: RunningServer, http: httpx2.AsyncClient) -> None:
    http.headers["Authorization"] = f"Bearer {TOKEN}"
    async with mcp_client(server, http) as client:
        with pytest.raises(MCPError) as excinfo:
            await client.call_tool("shell_exec", {})
    assert excinfo.value.code == -32602


async def test_delegated_identity_reaches_handler(server: RunningServer, http: httpx2.AsyncClient) -> None:
    http.headers["Authorization"] = f"Bearer {DELEGATING_TOKEN}"
    http.headers["Grenslan-User-Id"] = "alice"
    async with mcp_client(server, http) as client:
        await client.call_tool("web_search", {"query": "x"})
    (call,) = server.handler.calls
    assert (call.context.application_id, call.context.user_id) == ("app-b", "alice")


async def test_missing_credentials_return_401(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(
        f"{server.base_url}/mcp", content=rpc("tools/list"), headers=headers("tools/list", token=None)
    )
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")


@pytest.mark.parametrize("method", ["GET", "DELETE", "PUT"])
async def test_non_post_methods_return_405(server: RunningServer, http: httpx2.AsyncClient, method: str) -> None:
    response = await http.request(method, f"{server.base_url}/mcp", headers=headers("tools/list"))
    assert response.status_code == 405
    assert response.headers["allow"] == "POST"


async def test_invalid_origin_returns_403(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(
        f"{server.base_url}/mcp",
        content=rpc("tools/list"),
        headers=headers("tools/list", Origin="https://attacker.example"),
    )
    assert response.status_code == 403
    assert "id" not in response.json()


async def test_allowed_origin_is_accepted(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(
        f"{server.base_url}/mcp", content=rpc("tools/list"), headers=headers("tools/list", Origin=ALLOWED_ORIGIN)
    )
    assert response.status_code == 200


async def test_invalid_origin_is_rejected_before_authentication(
    server: RunningServer, http: httpx2.AsyncClient
) -> None:
    response = await http.post(
        f"{server.base_url}/mcp",
        content=rpc("tools/list"),
        headers=headers("tools/list", token=None, Origin="https://attacker.example"),
    )
    assert response.status_code == 403


async def test_unexpected_host_is_rejected(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(
        f"{server.base_url}/mcp", content=rpc("tools/list"), headers=headers("tools/list", Host="rebound.example")
    )
    assert response.status_code == 400


@pytest.mark.parametrize("version", ["2025-11-25", "2025-06-18", "2024-11-05"])
async def test_handshake_era_versions_are_rejected(
    server: RunningServer, http: httpx2.AsyncClient, version: str
) -> None:
    response = await http.post(
        f"{server.base_url}/mcp",
        content=rpc("tools/list"),
        headers=headers("tools/list", **{"MCP-Protocol-Version": version}),
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == -32022


async def test_missing_protocol_version_is_rejected(server: RunningServer, http: httpx2.AsyncClient) -> None:
    sent = headers("tools/list")
    del sent["MCP-Protocol-Version"]
    response = await http.post(f"{server.base_url}/mcp", content=rpc("tools/list"), headers=sent)
    assert response.status_code == 400


async def test_legacy_initialize_is_not_served(server: RunningServer, http: httpx2.AsyncClient) -> None:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "x", "version": "0"},
            },
        }
    ).encode()
    sent = headers("initialize")
    del sent["MCP-Protocol-Version"]
    response = await http.post(f"{server.base_url}/mcp", content=body, headers=sent)
    assert response.status_code == 400
    assert "mcp-session-id" not in response.headers


async def test_oversized_mcp_body_returns_413(server: RunningServer, http: httpx2.AsyncClient) -> None:
    body = rpc("tools/call", {"name": "web_search", "arguments": {"query": "x" * 9000}})
    response = await http.post(f"{server.base_url}/mcp", content=body, headers=headers("tools/call", name="web_search"))
    assert response.status_code == 413
    assert server.handler.calls == []


async def test_revocation_stops_active_mcp_work(material: TlsMaterial) -> None:
    gate = asyncio.Event()
    async with running_server(material, gate=gate) as running:
        async with (
            httpx2.AsyncClient(
                verify=material.client_context(), trust_env=False, headers={"Authorization": f"Bearer {TOKEN}"}
            ) as http,
            mcp_client(running, http) as client,
        ):
            call = asyncio.create_task(client.call_tool("web_search", {"query": "x"}))
            await asyncio.wait_for(running.handler.started.wait(), 5)
            running.store.replace([])
            with pytest.raises(MCPError):
                await asyncio.wait_for(call, 5)
        assert running.handler.cancelled


async def test_auto_mode_client_settles_on_current_revision(server: RunningServer, http: httpx2.AsyncClient) -> None:
    http.headers["Authorization"] = f"Bearer {TOKEN}"
    transport = streamable_http_client(f"{server.base_url}/mcp", http_client=http, terminate_on_close=False)
    async with Client(transport, mode="auto") as client:
        await client.call_tool("web_search", {"query": "x"})
        assert client.protocol_version == VERSION


@pytest.mark.parametrize(
    "body",
    [
        pytest.param(b"{not json", id="invalid-json"),
        pytest.param(b'{"jsonrpc": "1.0", "id": 1, "method": "tools/list"}', id="wrong-jsonrpc-version"),
        pytest.param(b'[{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}]', id="batch"),
        pytest.param(b'"tools/list"', id="not-an-object"),
    ],
)
async def test_malformed_protocol_messages_are_rejected(
    server: RunningServer, http: httpx2.AsyncClient, body: bytes
) -> None:
    response = await http.post(f"{server.base_url}/mcp", content=body, headers=headers("tools/list"))
    assert response.status_code == 400
    assert "result" not in response.text
    assert server.handler.calls == []


async def test_method_header_must_match_body(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(
        f"{server.base_url}/mcp",
        content=rpc("tools/call", {"name": "web_search", "arguments": {"query": "x"}}),
        headers=headers("tools/list"),
    )
    assert response.status_code == 400
    assert server.handler.calls == []
