"""Configured provider instances, their lifecycle and route eligibility (PC-006, PC-010, PC-056).

Startup creates every enabled instance through the registry (a declaration
mismatch stops startup) and then initializes them concurrently, each within
its deadline: the lower of the global and the instance ``timeout_ms``. An
instance that fails, raises or overruns is ``unavailable`` with an explicit
issue, and the rest of the service starts normally. Disabled instances are
never created.

Eligibility for a capability follows the configured route order, keeping only
``ready`` or ``degraded`` instances that declare the capability. Nothing is
substituted when no instance qualifies.

Provider exception text is never logged or reported, because it may contain
configuration details; only the exception type is logged.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Awaitable, Callable, Coroutine
from dataclasses import dataclass, field
from typing import Any, TypeVar, get_args

import anyio

from grenslan.config.provider_config import ProviderConfig
from grenslan.providers.contract import (
    Family,
    Health,
    Issue,
    LifecycleContext,
    Provider,
    ProviderDescription,
    ProviderState,
)
from grenslan.providers.registry import ImplementationRegistry

_LOGGER = logging.getLogger("grenslan.providers")
_SERVING = frozenset({"ready", "degraded"})
_OPERATIONAL = frozenset({"ready", "degraded", "unavailable"})
T = TypeVar("T")


class _Cancellation:
    def __init__(self) -> None:
        self._event = anyio.Event()

    def requested(self) -> bool:
        return self._event.is_set()

    async def wait(self) -> None:
        await self._event.wait()

    def cancel(self) -> None:
        self._event.set()


@dataclass
class _Instance:
    provider_id: str
    family: Family
    timeout_seconds: float
    provider: Provider | None = None
    description: ProviderDescription | None = None
    health: Health = field(default_factory=lambda: Health(state="uninitialized"))


def _unavailable(code: str, message: str) -> Health:
    return Health(state="unavailable", issues=(Issue(code=code, message=message),))  # type: ignore[arg-type]


class _Overran(Exception):
    pass


class ProviderSet:
    """The running provider instances of one service process."""

    def __init__(self, instances: dict[str, _Instance], routes: dict[str, tuple[str, ...]]) -> None:
        self._instances = instances
        self._routes = routes

    @classmethod
    async def start(cls, config: ProviderConfig, registry: ImplementationRegistry) -> ProviderSet:
        global_timeout = int(config.data["limits"]["timeout_ms"])
        instances: dict[str, _Instance] = {}
        for provider_id, settings in config.providers.items():
            timeout_ms = min(global_timeout, int(settings["limits"].get("timeout_ms", global_timeout)))
            instance = _Instance(provider_id, settings["family"], timeout_ms / 1000)
            if settings["enabled"]:
                instance.provider, instance.description = registry.create(provider_id, config)
            else:
                instance.health = Health(state="disabled")
            instances[provider_id] = instance
        routes = {family: config.routes(family) for family in get_args(Family)}
        providers = cls(instances, routes)
        await providers._each(providers._initialize)
        return providers

    async def _each(
        self, action: Callable[[_Instance, Provider], Coroutine[Any, Any, None]], states: frozenset[str] | None = None
    ) -> None:
        async with anyio.create_task_group() as group:
            for instance in self._instances.values():
                if instance.provider is not None and (states is None or instance.health.state in states):
                    group.start_soon(action, instance, instance.provider)

    async def _bounded(self, instance: _Instance, call: Callable[[LifecycleContext], Awaitable[T]]) -> T:
        cancellation = _Cancellation()
        context = LifecycleContext(
            provider_id=instance.provider_id,
            deadline_monotonic=time.monotonic() + instance.timeout_seconds,
            cancellation=cancellation,
        )
        with anyio.move_on_after(instance.timeout_seconds):
            return await call(context)
        cancellation.cancel()
        raise _Overran

    def _transition(self, instance: _Instance, health: Health) -> None:
        if health.state != instance.health.state:
            _LOGGER.info("provider %s: %s -> %s", instance.provider_id, instance.health.state, health.state)
        instance.health = health

    async def _guarded(self, instance: _Instance, call: Callable[[LifecycleContext], Awaitable[Health]]) -> None:
        try:
            health = await self._bounded(instance, call)
        except _Overran:
            _LOGGER.warning("provider %s: lifecycle call exceeded its deadline", instance.provider_id)
            health = _unavailable("timeout", "the provider did not respond within its deadline")
        except Exception as error:  # noqa: BLE001 - provider failures are contained, never surfaced raw
            _LOGGER.warning("provider %s: lifecycle call failed (%s)", instance.provider_id, type(error).__name__)
            health = _unavailable("internal_error", "the provider failed")
        if health.state not in _OPERATIONAL:
            health = _unavailable("provider_unavailable", "the provider reported an invalid state")
        self._transition(instance, health)

    async def _initialize(self, instance: _Instance, provider: Provider) -> None:
        self._transition(instance, Health(state="initializing"))

        async def initialize(context: LifecycleContext) -> Health:
            result = await provider.initialize(context)
            if result.value is not None and result.outcome in ("completed", "partial"):
                return result.value
            return Health(state="unavailable", issues=result.issues)

        await self._guarded(instance, initialize)

    async def refresh_health(self) -> None:
        """Re-check every operational instance within its deadline."""

        async def check(instance: _Instance, provider: Provider) -> None:
            await self._guarded(instance, provider.health)

        await self._each(check, _OPERATIONAL)

    async def shutdown(self) -> None:
        """Stop every created instance; each gets its deadline and ends ``stopped`` regardless of outcome."""

        async def stop(instance: _Instance, provider: Provider) -> None:
            self._transition(instance, Health(state="stopping"))
            try:
                await self._bounded(instance, provider.shutdown)
            except _Overran:
                _LOGGER.warning("provider %s: shutdown exceeded its deadline", instance.provider_id)
            except Exception as error:  # noqa: BLE001 - provider failures are contained, never surfaced raw
                _LOGGER.warning("provider %s: shutdown failed (%s)", instance.provider_id, type(error).__name__)
            self._transition(instance, Health(state="stopped"))

        await self._each(stop, frozenset({"initializing", *_OPERATIONAL}))

    def state(self, provider_id: str) -> ProviderState:
        return self._instances[provider_id].health.state

    def health(self, provider_id: str) -> Health:
        return self._instances[provider_id].health

    def description(self, provider_id: str) -> ProviderDescription | None:
        return self._instances[provider_id].description

    def eligible(self, family: Family, capability: str) -> tuple[str, ...]:
        """Instances that may serve ``capability`` now, in configured route order."""
        return tuple(
            provider_id
            for provider_id in self._routes.get(family, ())
            if self._serves(self._instances[provider_id], capability)
        )

    def declaring(self, family: Family, capability: str) -> tuple[str, ...]:
        """Enabled instances whose declaration includes ``capability``, whatever their state, in route order."""
        return tuple(
            provider_id
            for provider_id in self._routes.get(family, ())
            if self._declares(self._instances[provider_id], capability)
        )

    def provider(self, provider_id: str) -> Any:
        """The instance itself, only while it is ready or degraded."""
        instance = self._instances.get(provider_id)
        if instance is None or instance.provider is None or instance.health.state not in _SERVING:
            raise LookupError(f"provider {provider_id!r} is not available")
        return instance.provider

    @staticmethod
    def _declares(instance: _Instance, capability: str) -> bool:
        if instance.description is None:
            return False
        return any(declaration.capability == capability for declaration in instance.description.capabilities)

    @classmethod
    def _serves(cls, instance: _Instance, capability: str) -> bool:
        return instance.health.state in _SERVING and cls._declares(instance, capability)
