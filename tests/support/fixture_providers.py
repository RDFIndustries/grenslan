"""Controlled fixture search providers, registered only by tests (PRP-001 F04).

Production code never registers these, so test data can never reach a real
deployment or stand in for a missing provider.
"""

from __future__ import annotations

import asyncio
import copy
from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any, Literal

from grenslan.providers.contract import (
    CapabilityDeclaration,
    Discovery,
    Health,
    Issue,
    LifecycleContext,
    ProviderDescription,
    ProviderExecutionContext,
    ProviderResult,
    ProviderState,
    SearchRequest,
    SearchResult,
)
from grenslan.providers.registry import Implementation, InstanceSettings

from config_fixtures import connected_config

FIXTURE_IMPLEMENTATION = "fixture_search"
Behaviour = Literal["ok", "fail", "raise", "hang"]


@dataclass
class FixtureBehaviour:
    initial_state: ProviderState = "ready"
    initialize: Behaviour = "ok"
    health: Behaviour = "ok"
    health_state: ProviderState = "ready"
    shutdown: Behaviour = "ok"
    describe_overrides: Mapping[str, Any] = field(default_factory=dict)
    results: tuple[Discovery, ...] = ()


@dataclass
class Calls:
    initialized: int = 0
    health: int = 0
    shut_down: int = 0
    searched: list[str] = field(default_factory=list)


FAILURE_DETAIL_TEXT = "fixture-secret-detail"


class FixtureSearchProvider:
    def __init__(self, provider_id: str, behaviour: FixtureBehaviour, calls: Calls) -> None:
        self.provider_id = provider_id
        self.behaviour = behaviour
        self.calls = calls

    def describe(self) -> ProviderDescription:
        values: dict[str, Any] = {
            "implementation_id": FIXTURE_IMPLEMENTATION,
            "family": "search",
            "contract_version": "1.0",
            "implementation_version": "0-test",
            "capabilities": (CapabilityDeclaration(capability="search.query", categories=("general",)),),
            "supported_platforms": ("any",),
            "dependency_manifest_id": "fixture",
        }
        values.update(self.behaviour.describe_overrides)
        return ProviderDescription(**values)

    async def _act(self, behaviour: Behaviour) -> None:
        if behaviour == "raise":
            raise RuntimeError(FAILURE_DETAIL_TEXT)
        if behaviour == "hang":
            await asyncio.sleep(3600)

    async def initialize(self, context: LifecycleContext) -> ProviderResult[Health]:
        self.calls.initialized += 1
        await self._act(self.behaviour.initialize)
        if self.behaviour.initialize == "fail":
            issue = Issue(code="provider_unavailable", message="fixture initialization failed")
            return ProviderResult(outcome="failed", value=None, issues=(issue,))
        return ProviderResult(outcome="completed", value=Health(state=self.behaviour.initial_state))

    async def health(self, context: LifecycleContext) -> Health:
        self.calls.health += 1
        await self._act(self.behaviour.health)
        return Health(state=self.behaviour.health_state)

    async def shutdown(self, context: LifecycleContext) -> ProviderResult[None]:
        self.calls.shut_down += 1
        await self._act(self.behaviour.shutdown)
        return ProviderResult(outcome="completed", value=None)

    async def search(self, request: SearchRequest, context: ProviderExecutionContext) -> ProviderResult[SearchResult]:
        self.calls.searched.append(request.query)
        result = SearchResult(items=self.behaviour.results, constraints=(), observed_at="2026-11-27T00:00:00Z")
        return ProviderResult(outcome="completed", value=result)


class NoSearchMethod(FixtureSearchProvider):
    """Declares search.query but has no callable search method."""

    search = None  # type: ignore[assignment]


@dataclass
class FixtureSet:
    behaviours: dict[str, FixtureBehaviour] = field(default_factory=dict)
    calls: dict[str, Calls] = field(default_factory=dict)
    provider_class: type[FixtureSearchProvider] = FixtureSearchProvider

    def implementation(self) -> Implementation:
        def create(settings: InstanceSettings) -> FixtureSearchProvider:
            behaviour = self.behaviours.setdefault(settings.provider_id, FixtureBehaviour())
            calls = self.calls.setdefault(settings.provider_id, Calls())
            return self.provider_class(settings.provider_id, behaviour, calls)

        return Implementation(implementation_id=FIXTURE_IMPLEMENTATION, family="search", factory=create)


def fixture_config(*provider_ids: str, disabled: tuple[str, ...] = (), timeout_ms: int = 2000) -> dict[str, Any]:
    """A connected provider configuration routing search through fixture instances in order."""
    config = copy.deepcopy(connected_config())
    config["providers"] = {
        provider_id: {
            "family": "search",
            "implementation": FIXTURE_IMPLEMENTATION,
            "enabled": provider_id not in disabled,
            "network_scope": "public_web",
            "disclosure_scope": "search_queries",
            "limits": {"timeout_ms": timeout_ms},
            "search": {"deployment": "internal"},
        }
        for provider_id in provider_ids
    }
    config["routing"] = {family: [] for family in config["routing"]}
    config["routing"]["search"] = list(provider_ids)
    return config
