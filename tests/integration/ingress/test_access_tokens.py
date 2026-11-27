"""OAuth access tokens on REST and MCP over real local HTTPS (TC-048)."""

from __future__ import annotations

import asyncio
import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.exceptions import MCPError

from grenslan.server.oauth import AccessTokenValidator, TokenPolicy, TrustedIssuer

from ingress_fixtures import RunningServer, running_server
from jwt_fixtures import ISSUER, RESOURCE, SigningKey, claims, rsa_key
from tls_fixtures import TlsMaterial, make_tls_material

pytestmark = pytest.mark.integration
VERSION = "2026-07-28"
METADATA_PATH = "/.well-known/oauth-protected-resource/mcp"
SCOPES = {"grenslan.search": frozenset({"web_search"}), "grenslan.read": frozenset({"document_read"})}


@pytest.fixture(scope="module")
def key() -> SigningKey:
    return rsa_key()


def trusted(key: SigningKey) -> TrustedIssuer:
    return TrustedIssuer(
        issuer=ISSUER,
        application_id="qor",
        keys=(key.public_jwk(),),
        scope_permissions=SCOPES,
        user_claim="sub",
    )


def tokens(key: SigningKey) -> AccessTokenValidator:
    policy = TokenPolicy(resource=RESOURCE, leeway_seconds=0, max_lifetime_seconds=3600)
    return AccessTokenValidator(policy, [trusted(key)])


@pytest.fixture
def material(tmp_path: Path) -> TlsMaterial:
    return make_tls_material(tmp_path)


@pytest.fixture
async def server(material: TlsMaterial, key: SigningKey) -> AsyncIterator[RunningServer]:
    async with running_server(material, tokens=tokens(key)) as running:
        yield running


@pytest.fixture
async def http(material: TlsMaterial) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(verify=material.client_context(), trust_env=False) as client:
        yield client


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_protected_resource_metadata_is_published(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.get(f"{server.base_url}{METADATA_PATH}")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {
        "resource": RESOURCE,
        "authorization_servers": [ISSUER],
        "scopes_supported": ["grenslan.read", "grenslan.search"],
        "bearer_methods_supported": ["header"],
    }


async def test_metadata_is_not_published_without_oauth(material: TlsMaterial, http: httpx2.AsyncClient) -> None:
    async with running_server(material) as plain:
        response = await http.get(f"{plain.base_url}{METADATA_PATH}")
    assert response.status_code == 404


async def test_challenge_points_to_metadata(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(f"{server.base_url}/api/v1/tools/web_search", json={"query": "x"})
    assert response.status_code == 401
    challenge = response.headers["www-authenticate"]
    assert challenge.startswith("Bearer ")
    assert f'resource_metadata="https://localhost{METADATA_PATH}"' in challenge
    assert "error=" not in challenge


async def test_rejected_token_challenge_says_invalid_token(
    server: RunningServer, http: httpx2.AsyncClient, key: SigningKey
) -> None:
    token = key.sign(claims(aud="https://elsewhere.example/mcp"))
    response = await http.post(f"{server.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=bearer(token))
    assert response.status_code == 401
    assert 'error="invalid_token"' in response.headers["www-authenticate"]
    assert server.handler.calls == []


async def test_token_authorizes_rest_call(server: RunningServer, http: httpx2.AsyncClient, key: SigningKey) -> None:
    token = key.sign(claims(sub="alice"))
    response = await http.post(f"{server.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=bearer(token))
    assert response.status_code == 200
    (call,) = server.handler.calls
    assert (call.context.application_id, call.context.user_id) == ("qor", "alice")


async def test_token_without_scope_is_forbidden(
    server: RunningServer, http: httpx2.AsyncClient, key: SigningKey
) -> None:
    token = key.sign(claims(scope="grenslan.read"))
    response = await http.post(f"{server.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=bearer(token))
    assert response.status_code == 403
    assert server.handler.calls == []


async def test_identity_headers_are_refused_for_tokens(
    server: RunningServer, http: httpx2.AsyncClient, key: SigningKey
) -> None:
    headers = {**bearer(key.sign(claims())), "Grenslan-User-Id": "mallory"}
    response = await http.post(f"{server.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=headers)
    assert response.status_code == 403
    assert server.handler.calls == []


async def test_token_authorizes_mcp_discovery_and_call(
    server: RunningServer, http: httpx2.AsyncClient, key: SigningKey
) -> None:
    http.headers.update(bearer(key.sign(claims(sub="alice"))))
    transport = streamable_http_client(f"{server.base_url}/mcp", http_client=http, terminate_on_close=False)
    async with Client(transport, mode=VERSION) as client:
        assert [tool.name for tool in (await client.list_tools()).tools] == ["web_search"]
        result = await client.call_tool("web_search", {"query": "x"})
    assert result.is_error is False
    (call,) = server.handler.calls
    assert (call.context.application_id, call.context.user_id) == ("qor", "alice")


async def test_mcp_without_token_gets_metadata_challenge(server: RunningServer, http: httpx2.AsyncClient) -> None:
    response = await http.post(
        f"{server.base_url}/mcp",
        content=b"{}",
        headers={"Content-Type": "application/json", "MCP-Protocol-Version": VERSION, "Mcp-Method": "tools/list"},
    )
    assert response.status_code == 401
    assert "resource_metadata=" in response.headers["www-authenticate"]


async def test_token_expiry_stops_active_work(material: TlsMaterial, http: httpx2.AsyncClient, key: SigningKey) -> None:
    gate = asyncio.Event()
    async with running_server(material, tokens=tokens(key), gate=gate) as running:
        token = key.sign(claims(exp=int(time.time()) + 2))
        response = await asyncio.wait_for(
            http.post(f"{running.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=bearer(token)), 10
        )
        assert response.status_code == 401
        assert running.handler.cancelled


async def test_issuer_removal_stops_active_work(
    material: TlsMaterial, http: httpx2.AsyncClient, key: SigningKey
) -> None:
    gate = asyncio.Event()
    validator = tokens(key)
    async with running_server(material, tokens=validator, gate=gate) as running:
        request = asyncio.create_task(
            http.post(
                f"{running.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=bearer(key.sign(claims()))
            )
        )
        await asyncio.wait_for(running.handler.started.wait(), 5)
        validator.replace([])
        response = await asyncio.wait_for(request, 5)
        assert response.status_code == 401
        assert running.handler.cancelled


async def test_static_credentials_still_work_with_oauth_enabled(
    server: RunningServer, http: httpx2.AsyncClient
) -> None:
    from ingress_fixtures import TOKEN

    response = await http.post(f"{server.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=bearer(TOKEN))
    assert response.status_code == 200


async def test_revoked_token_rejected_with_mcp_protocol_error(
    material: TlsMaterial, http: httpx2.AsyncClient, key: SigningKey
) -> None:
    gate = asyncio.Event()
    validator = tokens(key)
    async with running_server(material, tokens=validator, gate=gate) as running:
        http.headers.update(bearer(key.sign(claims())))
        transport = streamable_http_client(f"{running.base_url}/mcp", http_client=http, terminate_on_close=False)
        async with Client(transport, mode=VERSION) as client:
            call = asyncio.create_task(client.call_tool("web_search", {"query": "x"}))
            await asyncio.wait_for(running.handler.started.wait(), 5)
            validator.replace([])
            with pytest.raises(MCPError):
                await asyncio.wait_for(call, 5)
        assert running.handler.cancelled
