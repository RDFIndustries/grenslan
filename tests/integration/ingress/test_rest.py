"""REST tool invocation over real local HTTPS (TC-048, TC-050, F-G02, F-G04)."""

from __future__ import annotations

import asyncio
import json
import ssl
from collections.abc import AsyncIterator
from pathlib import Path

import httpx2
import pytest

from ingress_fixtures import DELEGATING_TOKEN, TOKEN, RunningServer, credentials, running_server
from tls_fixtures import TlsMaterial, make_tls_material

pytestmark = pytest.mark.integration


@pytest.fixture
def material(tmp_path: Path) -> TlsMaterial:
    return make_tls_material(tmp_path)


@pytest.fixture
async def server(material: TlsMaterial) -> AsyncIterator[RunningServer]:
    async with running_server(material, max_request_bytes=4096) as running:
        yield running


@pytest.fixture
async def client(server: RunningServer) -> AsyncIterator[httpx2.AsyncClient]:
    async with httpx2.AsyncClient(
        base_url=server.base_url, verify=server.material.client_context(), trust_env=False
    ) as http:
        yield http


def auth(token: str = TOKEN) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def test_completed_search_returns_200_envelope(client: httpx2.AsyncClient, server: RunningServer) -> None:
    response = await client.post("/api/v1/tools/web_search", json={"query": "fixture"}, headers=auth())
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["request_id"].startswith("req_")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["content-type"].startswith("application/json")
    (call,) = server.handler.calls
    assert call.context.application_id == "app-a"
    assert call.context.user_id == "service-user"


async def test_missing_credentials_return_401_challenge(client: httpx2.AsyncClient, server: RunningServer) -> None:
    response = await client.post("/api/v1/tools/web_search", json={"query": "x"})
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Bearer")
    assert server.handler.calls == []


async def test_wrong_credential_returns_401(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/v1/tools/web_search", json={"query": "x"}, headers=auth("wrong-" + "x" * 40))
    assert response.status_code == 401
    assert "wrong-" not in response.text


async def test_unknown_tool_returns_404(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/v1/tools/shell_exec", json={}, headers=auth())
    assert response.status_code == 404


async def test_unknown_tool_is_indistinguishable_without_credentials(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/v1/tools/shell_exec", json={})
    assert response.status_code == 401


async def test_unpermitted_tool_returns_403_envelope(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/v1/tools/image_search", json={"query": "x"}, headers=auth())
    assert response.status_code == 403
    assert response.json()["issues"][0]["code"] == "unauthorized"


async def test_unimplemented_permitted_tool_returns_unsupported_outcome(client: httpx2.AsyncClient) -> None:
    response = await client.post("/api/v1/tools/document_read", json={"artifact_uri": "grenslan://a/b"}, headers=auth())
    assert response.status_code == 200
    assert response.json()["status"] == "failed"
    assert response.json()["issues"][0]["code"] == "unsupported_capability"


@pytest.mark.parametrize(
    "body",
    [b'{"query": "a", "query": "b"}', b"not json", b'{"query": "x", "application_id": "app-z"}', b'["query"]'],
)
async def test_invalid_request_returns_400_envelope(
    client: httpx2.AsyncClient, server: RunningServer, body: bytes
) -> None:
    response = await client.post("/api/v1/tools/web_search", content=body, headers=auth())
    assert response.status_code == 400
    assert response.json()["issues"][0]["code"] == "invalid_request"
    assert server.handler.calls == []


async def test_non_json_content_type_returns_400(client: httpx2.AsyncClient) -> None:
    headers = {**auth(), "Content-Type": "text/plain"}
    response = await client.post("/api/v1/tools/web_search", content=b'{"query": "x"}', headers=headers)
    assert response.status_code == 400


async def test_oversized_declared_body_returns_413(client: httpx2.AsyncClient, server: RunningServer) -> None:
    response = await client.post(
        "/api/v1/tools/web_search", content=json.dumps({"query": "x" * 5000}).encode(), headers=auth()
    )
    assert response.status_code == 413
    assert server.handler.calls == []


async def test_oversized_streamed_body_returns_413(client: httpx2.AsyncClient, server: RunningServer) -> None:
    async def chunks() -> AsyncIterator[bytes]:
        yield b'{"query": "'
        for _ in range(10):
            yield b"x" * 1000
        yield b'"}'

    response = await client.post("/api/v1/tools/web_search", content=chunks(), headers=auth())
    assert response.status_code == 413
    assert server.handler.calls == []


async def test_get_on_tool_route_returns_405(client: httpx2.AsyncClient) -> None:
    response = await client.get("/api/v1/tools/web_search", headers=auth())
    assert response.status_code == 405


@pytest.mark.parametrize("path", ["/api/v1/artifacts/abc", "/api/v1/uploads", "/", "/admin"])
async def test_unavailable_routes_return_404(client: httpx2.AsyncClient, path: str) -> None:
    response = await client.post(path, json={}, headers=auth())
    assert response.status_code == 404


async def test_delegated_identity_reaches_handler(client: httpx2.AsyncClient, server: RunningServer) -> None:
    headers = {**auth(DELEGATING_TOKEN), "Grenslan-User-Id": "alice", "Grenslan-Agent-Id": "researcher"}
    response = await client.post("/api/v1/tools/web_search", json={"query": "x"}, headers=headers)
    assert response.status_code == 200
    (call,) = server.handler.calls
    assert (call.context.application_id, call.context.user_id, call.context.agent_id) == (
        "app-b",
        "alice",
        "researcher",
    )


async def test_delegation_without_permission_returns_403(client: httpx2.AsyncClient, server: RunningServer) -> None:
    headers = {**auth(), "Grenslan-User-Id": "alice"}
    response = await client.post("/api/v1/tools/web_search", json={"query": "x"}, headers=headers)
    assert response.status_code == 403
    assert server.handler.calls == []


async def test_duplicate_delegation_header_returns_400(server: RunningServer) -> None:
    headers = [
        ("Authorization", f"Bearer {DELEGATING_TOKEN}"),
        ("Content-Type", "application/json"),
        ("Grenslan-User-Id", "alice"),
        ("grenslan-user-id", "bob"),
    ]
    async with httpx2.AsyncClient(verify=server.material.client_context(), trust_env=False) as http:
        response = await http.post(
            f"{server.base_url}/api/v1/tools/web_search", content=b'{"query":"x"}', headers=headers
        )
    assert response.status_code == 400
    assert server.handler.calls == []


async def test_revoked_credential_is_rejected_on_next_request(
    client: httpx2.AsyncClient, server: RunningServer
) -> None:
    assert (await client.post("/api/v1/tools/web_search", json={"query": "x"}, headers=auth())).status_code == 200
    server.store.replace([])
    assert (await client.post("/api/v1/tools/web_search", json={"query": "x"}, headers=auth())).status_code == 401


async def test_revocation_stops_active_work(material: TlsMaterial) -> None:
    gate = asyncio.Event()
    async with (
        running_server(material, gate=gate) as running,
        httpx2.AsyncClient(verify=material.client_context(), trust_env=False) as http,
    ):
        request = asyncio.create_task(
            http.post(f"{running.base_url}/api/v1/tools/web_search", json={"query": "x"}, headers=auth())
        )
        await asyncio.wait_for(running.handler.started.wait(), 5)
        running.store.replace([])
        response = await asyncio.wait_for(request, 5)
        assert response.status_code == 401
        assert running.handler.cancelled


async def test_revocation_leaves_other_credentials_work_running(material: TlsMaterial) -> None:
    gate = asyncio.Event()
    async with (
        running_server(material, gate=gate) as running,
        httpx2.AsyncClient(verify=material.client_context(), trust_env=False) as http,
    ):
        url = f"{running.base_url}/api/v1/tools/web_search"
        revoked = asyncio.create_task(http.post(url, json={"query": "a"}, headers=auth()))
        survivor = asyncio.create_task(http.post(url, json={"query": "b"}, headers=auth(DELEGATING_TOKEN)))
        while len(running.handler.calls) < 2:
            await asyncio.sleep(0.01)
        running.store.replace([c for c in credentials() if c.credential_id != "plain"])
        assert (await asyncio.wait_for(revoked, 5)).status_code == 401
        gate.set()
        assert (await asyncio.wait_for(survivor, 5)).status_code == 200


async def tls_handshake(port: int, context: ssl.SSLContext) -> None:
    _, writer = await asyncio.open_connection("127.0.0.1", port, ssl=context, server_hostname="localhost")
    writer.close()


async def test_plaintext_http_is_not_served(server: RunningServer) -> None:
    reader, writer = await asyncio.open_connection("127.0.0.1", server.port)
    writer.write(b"POST /api/v1/tools/web_search HTTP/1.1\r\nHost: localhost\r\nContent-Length: 2\r\n\r\n{}")
    await writer.drain()
    data = await asyncio.wait_for(reader.read(4096), 5)
    writer.close()
    assert not data.startswith(b"HTTP/1.1 200")
    assert b'"status"' not in data


@pytest.mark.filterwarnings("ignore:ssl.TLSVersion.TLSv1:DeprecationWarning")
async def test_tls_below_1_2_is_refused(server: RunningServer) -> None:
    context = ssl.create_default_context(cafile=str(server.material.ca_file))
    try:
        context.minimum_version = ssl.TLSVersion.TLSv1
        context.maximum_version = ssl.TLSVersion.TLSv1_1
    except ValueError:
        pytest.skip("local OpenSSL cannot offer TLS below 1.2")
    with pytest.raises((ssl.SSLError, ConnectionError)):
        await tls_handshake(server.port, context)


async def test_client_without_the_test_ca_rejects_the_server(server: RunningServer) -> None:
    context = ssl.create_default_context()
    with pytest.raises(ssl.SSLCertVerificationError):
        await tls_handshake(server.port, context)


async def test_negotiates_tls_1_3_when_offered(server: RunningServer) -> None:
    _, writer = await asyncio.open_connection(
        "127.0.0.1", server.port, ssl=server.material.client_context(), server_hostname="localhost"
    )
    assert writer.get_extra_info("ssl_object").version() == "TLSv1.3"
    writer.close()
