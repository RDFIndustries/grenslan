"""A real HTTPS server around the Grenslan app, with test-only handlers and credentials."""

from __future__ import annotations

import asyncio
import contextlib
import functools
from collections.abc import AsyncIterator, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

import uvicorn

from grenslan.contracts.envelope import Issue, Status
from grenslan.contracts.registry import ToolRegistry
from grenslan.server.app import IngressSettings, create_app
from grenslan.server.auth import ApplicationCredential, CredentialStore, token_digest
from grenslan.server.tls import server_ssl_context
from grenslan.service.dispatch import ArgumentLimits, Invocation, ToolDispatcher, ToolOutcome
from grenslan.service.profiles import profile_tools

from tls_fixtures import TlsMaterial

SEARCH_RESULT = {"results": [], "constraints": [], "ranking": "provider_order", "freshness": "default"}
TOKEN = "test-token-" + "a" * 32
DELEGATING_TOKEN = "test-token-" + "d" * 32
ALLOWED_ORIGIN = "https://agent.example"


@dataclass
class RecordingSearch:
    """Test-only web_search handler. It records invocations and can be made to wait."""

    calls: list[Invocation] = field(default_factory=list)
    gate: asyncio.Event | None = None
    started: asyncio.Event = field(default_factory=asyncio.Event)
    cancelled: bool = False

    def semantic_issues(self, arguments: Mapping[str, Any]) -> Sequence[Issue]:
        return ()

    async def __call__(self, invocation: Invocation) -> ToolOutcome:
        self.calls.append(invocation)
        self.started.set()
        if self.gate is not None:
            try:
                await self.gate.wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        return ToolOutcome(status=Status.COMPLETED, result=SEARCH_RESULT)


def credentials() -> list[ApplicationCredential]:
    return [
        ApplicationCredential(
            credential_id="plain",
            application_id="app-a",
            token_sha256=token_digest(TOKEN),
            permissions=frozenset({"web_search", "capabilities_get", "document_read"}),
            delegation=False,
            user_id="service-user",
            agent_id=None,
            instance_id=None,
        ),
        ApplicationCredential(
            credential_id="delegating",
            application_id="app-b",
            token_sha256=token_digest(DELEGATING_TOKEN),
            permissions=frozenset({"web_search"}),
            delegation=True,
            user_id=None,
            agent_id=None,
            instance_id=None,
        ),
    ]


@dataclass
class RunningServer:
    base_url: str
    handler: RecordingSearch
    store: CredentialStore
    material: TlsMaterial
    port: int


@functools.cache
def shared_registry() -> ToolRegistry:
    return ToolRegistry.load()


class PermissionPolicy:
    def permits(self, context: Any, tool: str) -> bool:
        return tool in context.permissions


@contextlib.asynccontextmanager
async def running_server(
    material: TlsMaterial, *, max_request_bytes: int = 64 * 1024, gate: asyncio.Event | None = None
) -> AsyncIterator[RunningServer]:
    registry = shared_registry()
    handler = RecordingSearch(gate=gate)
    dispatcher = ToolDispatcher(
        registry,
        handlers={"web_search": handler},
        policy=PermissionPolicy(),
        profile=profile_tools("full"),
        max_request_bytes=max_request_bytes,
        argument_limits=ArgumentLimits(max_string_chars=4096, max_array_items=100, max_depth=16),
    )
    store = CredentialStore(credentials())
    settings = IngressSettings(
        allowed_hosts=frozenset({"localhost", "127.0.0.1"}),
        allowed_origins=frozenset({ALLOWED_ORIGIN}),
        max_request_bytes=max_request_bytes,
    )
    app = create_app(registry=registry, dispatcher=dispatcher, credentials=store, settings=settings)
    tls = server_ssl_context(material.cert_file, material.key_file)
    config = uvicorn.Config(
        app,
        host="127.0.0.1",
        port=0,
        ssl_context_factory=lambda _config, _default: tls,
        log_level="warning",
        lifespan="on",
        # A request still running at teardown must fail the test, not hang the run.
        timeout_graceful_shutdown=2,
    )
    server = uvicorn.Server(config)
    task = asyncio.create_task(server.serve())
    try:
        while not server.started:
            if task.done():
                task.result()
            await asyncio.sleep(0.01)
        port = server.servers[0].sockets[0].getsockname()[1]
        yield RunningServer(f"https://localhost:{port}", handler, store, material, port)
    finally:
        server.should_exit = True
        await task
