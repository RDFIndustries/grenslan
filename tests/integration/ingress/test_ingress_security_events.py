"""Security events emitted by real HTTPS requests, and what they must never contain."""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest

from grenslan.server.oauth import AccessTokenValidator, TokenPolicy, TrustedIssuer

from ingress_fixtures import ALLOWED_ORIGIN, TOKEN, RunningServer, running_server
from jwt_fixtures import ISSUER, RESOURCE, SigningKey, claims, rsa_key
from tls_fixtures import TlsMaterial, make_tls_material

pytestmark = pytest.mark.integration
VERSION = "2026-07-28"
REJECTED_IDENTITY = "mallory-identity-value"


@pytest.fixture(scope="module")
def key() -> SigningKey:
    return rsa_key()


@pytest.fixture
def material(tmp_path: Path) -> TlsMaterial:
    return make_tls_material(tmp_path)


@pytest.fixture
async def server(material: TlsMaterial, key: SigningKey) -> AsyncIterator[RunningServer]:
    issuer = TrustedIssuer(
        issuer=ISSUER,
        application_id="qor",
        keys=(key.public_jwk(),),
        scope_permissions={"grenslan.search": frozenset({"web_search"})},
        user_claim="sub",
    )
    tokens = AccessTokenValidator(TokenPolicy(resource=RESOURCE, leeway_seconds=0, max_lifetime_seconds=3600), [issuer])
    async with running_server(material, max_request_bytes=8192, tokens=tokens) as running:
        yield running


@pytest.fixture
async def http(material: TlsMaterial) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(verify=material.client_context(), trust_env=False) as client:
        yield client


@pytest.fixture(autouse=True)
def capture(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO, logger="grenslan.security")


def events(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [r.security_event for r in caplog.records if hasattr(r, "security_event")]


async def post(http: httpx2.AsyncClient, server: RunningServer, **kwargs: object) -> httpx2.Response:
    return await http.post(f"{server.base_url}/api/v1/tools/web_search", **kwargs)  # type: ignore[arg-type]


async def test_unknown_credential_is_recorded_without_the_token(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    sent = "wrong-token-" + "z" * 32
    await post(http, server, json={"query": "x"}, headers={"Authorization": f"Bearer {sent}"})
    (event,) = events(caplog)
    assert event == {
        "event": "authentication_failed",
        "interface": "rest",
        "client": "127.0.0.1",
        "reason": "unknown_credential",
    }
    assert sent not in caplog.text


async def test_missing_credentials_are_recorded(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    await post(http, server, json={"query": "x"})
    assert events(caplog)[0]["reason"] == "missing"


async def test_token_rejection_reason_reaches_the_log_only(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture, key: SigningKey
) -> None:
    token = key.sign(claims(exp=int(time.time()) - 60))
    response = await post(http, server, json={"query": "x"}, headers={"Authorization": f"Bearer {token}"})
    assert "expired" not in response.text
    assert "expired" not in response.headers["www-authenticate"]
    assert events(caplog)[0]["reason"] == "token_expired"
    assert token not in caplog.text


async def test_rejected_delegation_is_attributed_without_header_values(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}", "Grenslan-User-Id": REJECTED_IDENTITY}
    await post(http, server, json={"query": "x"}, headers=headers)
    (event,) = events(caplog)
    assert event["event"] == "context_rejected"
    assert event["principal"] == "credential:plain"
    assert event["application_id"] == "app-a"
    assert event["reason"] == "delegation_not_permitted"
    assert REJECTED_IDENTITY not in caplog.text
    assert TOKEN not in caplog.text


async def test_rejected_origin_is_recorded(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    await http.post(f"{server.base_url}/mcp", content=b"{}", headers={"Origin": "https://attacker.example"})
    (event,) = events(caplog)
    assert event == {"event": "origin_rejected", "client": "127.0.0.1", "origin": "https://attacker.example"}


async def test_allowed_origin_is_not_recorded(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    headers = {"Authorization": f"Bearer {TOKEN}", "Origin": ALLOWED_ORIGIN}
    await post(http, server, json={"query": "x"}, headers=headers)
    assert events(caplog) == []


async def test_rejected_host_is_recorded(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    await post(http, server, json={"query": "x"}, headers={"Host": "rebound.example"})
    (event,) = events(caplog)
    assert event == {"event": "host_rejected", "client": "127.0.0.1", "host": "rebound.example"}


async def test_denied_tool_is_recorded_for_rest_and_mcp(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    auth = {"Authorization": f"Bearer {TOKEN}"}
    await http.post(f"{server.base_url}/api/v1/tools/image_search", json={"query": "x"}, headers=auth)
    body = (
        b'{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"image_search","arguments":{"query":"x"},'
        b'"_meta":{"io.modelcontextprotocol/protocolVersion":"2026-07-28",'
        b'"io.modelcontextprotocol/clientInfo":{"name":"t","version":"0"},'
        b'"io.modelcontextprotocol/clientCapabilities":{}}}}'
    )
    mcp_headers = {
        **auth,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
        "MCP-Protocol-Version": VERSION,
        "Mcp-Method": "tools/call",
        "Mcp-Name": "image_search",
    }
    response = await http.post(f"{server.base_url}/mcp", content=body, headers=mcp_headers)
    assert response.status_code == 200
    denied = [e for e in events(caplog) if e["event"] == "authorization_denied"]
    assert [(e["interface"], e["tool"], e["principal"]) for e in denied] == [
        ("rest", "image_search", "credential:plain"),
        ("mcp", "image_search", "credential:plain"),
    ]


async def test_oversized_request_is_recorded(
    server: RunningServer, http: httpx2.AsyncClient, caplog: pytest.LogCaptureFixture
) -> None:
    body = b'{"query":"' + b"x" * 9000 + b'"}'
    headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    assert (await post(http, server, content=body, headers=headers)).status_code == 413
    (event,) = events(caplog)
    assert (event["event"], event["interface"], event["principal"]) == ("request_too_large", "rest", "credential:plain")


async def test_revoked_work_is_recorded(material: TlsMaterial, caplog: pytest.LogCaptureFixture) -> None:
    gate = asyncio.Event()
    async with (
        running_server(material, gate=gate) as running,
        httpx2.AsyncClient(verify=material.client_context(), trust_env=False) as http,
    ):
        request = asyncio.create_task(
            post(http, running, json={"query": "x"}, headers={"Authorization": f"Bearer {TOKEN}"})
        )
        await asyncio.wait_for(running.handler.started.wait(), 5)
        running.store.replace([])
        await asyncio.wait_for(request, 5)
    (event,) = events(caplog)
    assert (event["event"], event["reason"], event["principal"]) == ("work_revoked", "revoked", "credential:plain")


async def test_expired_work_is_recorded(
    material: TlsMaterial, caplog: pytest.LogCaptureFixture, key: SigningKey
) -> None:
    issuer = TrustedIssuer(
        issuer=ISSUER,
        application_id="qor",
        keys=(key.public_jwk(),),
        scope_permissions={"grenslan.search": frozenset({"web_search"})},
        user_claim=None,
    )
    tokens = AccessTokenValidator(TokenPolicy(resource=RESOURCE, leeway_seconds=0, max_lifetime_seconds=3600), [issuer])
    async with (
        running_server(material, gate=asyncio.Event(), tokens=tokens) as running,
        httpx2.AsyncClient(verify=material.client_context(), trust_env=False) as http,
    ):
        token = key.sign(claims(exp=int(time.time()) + 2))
        await asyncio.wait_for(
            post(http, running, json={"query": "x"}, headers={"Authorization": f"Bearer {token}"}), 10
        )
    (event,) = events(caplog)
    assert (event["event"], event["reason"], event["principal"]) == (
        "work_revoked",
        "expired",
        "token:" + ISSUER + "#rsa-1",
    )
