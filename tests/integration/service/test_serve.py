"""The configured service end to end: startup validation, HTTPS, and SIGHUP credential reload (D3, D6 to D8)."""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import signal
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx2
import pytest
import uvicorn
import yaml

from grenslan.config.loader import ConfigLoadError
from grenslan.providers.registry import ImplementationRegistry, ProviderRegistrationError
from grenslan.server.runner import run_service

from fixture_providers import FixtureBehaviour, FixtureSet, fixture_config
from service_fixtures import QOR_TOKEN, ZYGOS_TOKEN, service_data, write_service_file
from tls_fixtures import TlsMaterial, make_tls_material

pytestmark = pytest.mark.integration


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return int(probe.getsockname()[1])


class Deployment:
    def __init__(self, tmp_path: Path, fixtures: FixtureSet, provider_ids: tuple[str, ...] = ()) -> None:
        self.material: TlsMaterial = make_tls_material(tmp_path)
        self.fixtures = fixtures
        self.registry = ImplementationRegistry([fixtures.implementation()])
        self.port = free_port()
        self.service_path = tmp_path / "service.yaml"
        self.provider_path = tmp_path / "providers.yaml"
        self.provider_path.write_text(yaml.safe_dump(fixture_config(*provider_ids)), encoding="utf-8")
        self.write(service_data())
        self.environ = {
            "GRENSLAN_SERVICE_CONFIG": str(self.service_path),
            "GRENSLAN_PROVIDER_CONFIG": str(self.provider_path),
            "GRENSLAN_LISTEN_PORT": str(self.port),
        }

    def write(self, data: dict[str, Any]) -> None:
        write_service_file(self.service_path, data, self.material)

    @contextlib.asynccontextmanager
    async def running(self) -> AsyncIterator[httpx2.AsyncClient]:
        ready: asyncio.Future[uvicorn.Server] = asyncio.get_running_loop().create_future()
        task = asyncio.create_task(run_service(self.environ, implementations=self.registry, started=ready.set_result))
        server = await asyncio.wait_for(asyncio.shield(ready), 10)
        try:
            async with httpx2.AsyncClient(
                base_url=f"https://localhost:{self.port}", verify=self.material.client_context(), trust_env=False
            ) as client:
                yield client
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, 10)


async def search(client: httpx2.AsyncClient, token: str) -> int:
    response = await client.post(
        "/api/v1/tools/web_search",
        json={"query": "grenslan"},
        headers={"Authorization": f"Bearer {token}"},
    )
    return response.status_code


async def test_configured_service_authenticates_consumers(tmp_path: Path) -> None:
    deployment = Deployment(tmp_path, FixtureSet())
    async with deployment.running() as client:
        assert await search(client, QOR_TOKEN) == 200
        assert await search(client, "not-a-credential-" + "x" * 30) == 401


async def test_sighup_revokes_a_removed_credential_without_restart(tmp_path: Path) -> None:
    deployment = Deployment(tmp_path, FixtureSet())
    async with deployment.running() as client:
        assert await search(client, ZYGOS_TOKEN) == 200
        data = service_data()
        del data["credentials"]["zygos"]
        deployment.write(data)
        os.kill(os.getpid(), signal.SIGHUP)
        for _ in range(100):
            if await search(client, ZYGOS_TOKEN) == 401:
                break
            await asyncio.sleep(0.02)
        assert await search(client, ZYGOS_TOKEN) == 401
        assert await search(client, QOR_TOKEN) == 200


async def test_invalid_service_configuration_stops_startup_before_binding(tmp_path: Path) -> None:
    deployment = Deployment(tmp_path, FixtureSet())
    data = service_data()
    data["credentials"]["qor"]["permissions"] = ["not_a_tool"]
    deployment.write(data)
    with pytest.raises(ConfigLoadError):
        await run_service(deployment.environ, implementations=deployment.registry)
    with socket.create_server(("127.0.0.1", deployment.port)):
        pass


async def test_unknown_environment_setting_stops_startup(tmp_path: Path) -> None:
    deployment = Deployment(tmp_path, FixtureSet())
    with pytest.raises(ConfigLoadError, match="GRENSLAN_LISTEN_PROT"):
        await run_service({**deployment.environ, "GRENSLAN_LISTEN_PROT": "1"}, implementations=deployment.registry)


async def test_provider_declaration_mismatch_stops_startup(tmp_path: Path) -> None:
    fixtures = FixtureSet(behaviours={"primary": FixtureBehaviour(describe_overrides={"family": "retrieval"})})
    deployment = Deployment(tmp_path, fixtures, ("primary",))
    with pytest.raises(ProviderRegistrationError):
        await run_service(deployment.environ, implementations=deployment.registry)


async def test_failed_provider_does_not_stop_startup_and_is_shut_down(tmp_path: Path) -> None:
    fixtures = FixtureSet(behaviours={"broken": FixtureBehaviour(initialize="fail")})
    deployment = Deployment(tmp_path, fixtures, ("broken", "primary"))
    async with deployment.running() as client:
        assert await search(client, QOR_TOKEN) == 200
    assert fixtures.calls["broken"].shut_down == 1
    assert fixtures.calls["primary"].shut_down == 1


async def capabilities(client: httpx2.AsyncClient, token: str) -> dict[str, Any]:
    response = await client.post(
        "/api/v1/tools/capabilities_get", json={}, headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    body: dict[str, Any] = response.json()
    assert body["status"] == "completed"
    return dict(body["result"])


async def test_capabilities_reflect_the_credential_and_configuration(tmp_path: Path) -> None:
    deployment = Deployment(tmp_path, FixtureSet(), ("primary",))
    async with deployment.running() as client:
        qor = await capabilities(client, QOR_TOKEN)
        zygos = await capabilities(client, ZYGOS_TOKEN)
    assert qor["profile"] == "full"
    assert {entry["name"]: entry["status"] for entry in qor["capabilities"]} == {
        "capabilities_get": "enabled",
        "web_search": "unsupported",
        "image_search": "unsupported",
    }
    assert zygos["profile"] == "search_only"
    assert {entry["name"] for entry in zygos["capabilities"]} == {"capabilities_get", "web_search", "image_search"}
    assert "primary" not in json.dumps(qor)
