"""Validate the configuration, start providers, and serve HTTPS until stopped (SERVICE-CONFIGURATION.md D6 to D8).

Everything is validated before the port is bound: both configuration files
with their environment overrides, the TLS pair, the issuers' key sets and every
provider's declaration. Any failure there stops startup. A provider that fails
to initialize does not stop startup; it is ``unavailable``.

The service runs as one process with one event loop. ``SIGHUP`` reloads
credentials and issuers on that loop, so revocation can cancel request work.
"""

from __future__ import annotations

import asyncio
import contextlib
import os
import signal
import ssl
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import uvicorn

from grenslan.config.loader import ConfigLoadError, LoadProblem, load_provider_config_file
from grenslan.config.provider_config import ProviderConfig
from grenslan.config.service_config import (
    PROVIDER_CONFIG_VARIABLE,
    SERVICE_CONFIG_VARIABLE,
    ServiceConfig,
    load_service_config_file,
)
from grenslan.contracts.registry import ToolRegistry
from grenslan.providers.builtin import builtin_registry
from grenslan.providers.registry import ImplementationRegistry
from grenslan.providers.runtime import ProviderSet
from grenslan.server.app import create_app
from grenslan.server.authenticator import Authenticator
from grenslan.server.deployment import (
    AccessReloader,
    argument_limits,
    build_authenticator,
    exposure_profile,
    ingress_settings,
    load_issuers,
    security_log,
)
from grenslan.server.tls import server_ssl_context
from grenslan.service.capabilities import CapabilitiesHandler, public_limits
from grenslan.service.context import InvocationContext
from grenslan.service.dispatch import ToolDispatcher

DEFAULT_SERVICE_CONFIG = Path("/etc/grenslan/service.yaml")
DEFAULT_PROVIDER_CONFIG = Path("/etc/grenslan/providers.yaml")
# Every implemented tool and the provider capabilities it needs; capabilities_get reports from this.
TOOL_REQUIREMENTS: dict[str, tuple[str, ...]] = {"capabilities_get": ()}


class GrantedPermissions:
    """A tool is permitted when the authenticated grant lists it."""

    def permits(self, context: InvocationContext, tool: str) -> bool:
        return tool in context.permissions


@dataclass(frozen=True)
class ConfigPaths:
    service: Path
    providers: Path

    @classmethod
    def from_environment(cls, environ: Mapping[str, str]) -> ConfigPaths:
        return cls(
            service=Path(environ.get(SERVICE_CONFIG_VARIABLE, DEFAULT_SERVICE_CONFIG)),
            providers=Path(environ.get(PROVIDER_CONFIG_VARIABLE, DEFAULT_PROVIDER_CONFIG)),
        )


@dataclass(frozen=True)
class ValidatedConfiguration:
    service: ServiceConfig
    providers: ProviderConfig
    authenticator: Authenticator
    tls: ssl.SSLContext


def validate_configuration(
    paths: ConfigPaths, environ: Mapping[str, str], tools: ToolRegistry, implementations: ImplementationRegistry
) -> ValidatedConfiguration:
    """Everything ``check-config`` checks. Raises ``ConfigLoadError`` or ``TlsConfigError``.

    Each problem location is prefixed with the file it was found in.
    """
    with _located(paths.service):
        service = load_service_config_file(paths.service, environ, tool_names=frozenset(tools.tool_names))
        authenticator = build_authenticator(service, load_issuers(service))
    tls_files = service.data["tls"]
    tls = server_ssl_context(Path(tls_files["certificate_file"]), Path(tls_files["private_key_file"]))
    with _located(paths.providers):
        providers = load_provider_config_file(paths.providers, implementations.specs())
    return ValidatedConfiguration(service, providers, authenticator, tls)


@contextlib.contextmanager
def _located(path: Path) -> Iterator[None]:
    try:
        yield
    except ConfigLoadError as exc:
        raise ConfigLoadError([LoadProblem(f"{path}: {p.location}", p.message) for p in exc.problems]) from None


async def run_service(
    environ: Mapping[str, str] | None = None,
    *,
    implementations: ImplementationRegistry | None = None,
    started: Callable[[uvicorn.Server], None] | None = None,
) -> None:
    """Run until the server is told to exit; ``started`` receives the server once it is listening."""
    environ = dict(os.environ if environ is None else environ)
    implementations = builtin_registry() if implementations is None else implementations
    paths = ConfigPaths.from_environment(environ)
    tools = ToolRegistry.load()
    validated = validate_configuration(paths, environ, tools, implementations)
    service = validated.service
    providers = await ProviderSet.start(validated.providers, implementations)
    try:
        profile = exposure_profile(service)
        capabilities = CapabilitiesHandler(
            registry=tools,
            providers=providers,
            requirements=TOOL_REQUIREMENTS,
            profile_name=service.data["tools"]["profile"],
            profile=profile,
            limits=public_limits(validated.providers),
        )
        handlers = {"capabilities_get": capabilities}
        if set(handlers) != set(TOOL_REQUIREMENTS):
            raise RuntimeError("every implemented tool must declare its provider requirements")
        dispatcher = ToolDispatcher(
            tools,
            handlers=handlers,
            policy=GrantedPermissions(),
            profile=profile,
            max_request_bytes=service.data["ingress"]["max_request_bytes"],
            argument_limits=argument_limits(service),
        )
        app = create_app(
            registry=tools,
            dispatcher=dispatcher,
            authenticator=validated.authenticator,
            settings=ingress_settings(service),
            security=security_log(service),
        )
        server = uvicorn.Server(_uvicorn_config(app, service, validated.tls))
        reloader = AccessReloader(paths.service, environ, frozenset(tools.tool_names), service, validated.authenticator)
        loop = asyncio.get_running_loop()
        loop.add_signal_handler(signal.SIGHUP, reloader.reload)
        try:
            serving = asyncio.create_task(server.serve())
            while not server.started and not serving.done():
                await asyncio.sleep(0.01)
            if server.started and started is not None:
                started(server)
            await serving
        finally:
            loop.remove_signal_handler(signal.SIGHUP)
    finally:
        await providers.shutdown()


def _uvicorn_config(app: Any, service: ServiceConfig, tls: ssl.SSLContext) -> uvicorn.Config:
    listen = service.data["listen"]
    return uvicorn.Config(
        app,
        host=listen["host"],
        port=listen["port"],
        ssl_context_factory=lambda _config, _default: tls,
        lifespan="on",
        # No reverse proxy is part of the design, so forwarded headers are never trusted.
        proxy_headers=False,
        server_header=False,
        log_config=None,
    )
