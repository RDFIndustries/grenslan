"""Explicit provider registration, declaration checks, lifecycle and eligibility (PC-004, PC-010, PC-056)."""

from __future__ import annotations

import asyncio
import dataclasses
import json
import logging
import time
from collections.abc import Awaitable
from pathlib import Path

import pytest

from grenslan.config.provider_config import ConfigValidationError, ProviderConfig, validate_provider_config
from grenslan.providers.contract import CapabilityDeclaration, Provider
from grenslan.providers.registry import (
    ConfigurationProblem,
    Implementation,
    ImplementationRegistry,
    InstanceSettings,
    ProviderRegistrationError,
)
from grenslan.providers.runtime import ProviderSet

from fixture_providers import (
    FAILURE_DETAIL_TEXT,
    FIXTURE_IMPLEMENTATION,
    FIXTURE_MANIFEST,
    FixtureBehaviour,
    FixtureSet,
    NoSearchMethod,
    fixture_config,
)


def config(*provider_ids: str, registry: ImplementationRegistry, **kwargs: object) -> ProviderConfig:
    return validate_provider_config(fixture_config(*provider_ids, **kwargs), registry.specs())  # type: ignore[arg-type]


async def started(fixtures: FixtureSet, *provider_ids: str, **kwargs: object) -> ProviderSet:
    registry = ImplementationRegistry([fixtures.implementation()])
    return await ProviderSet.start(config(*provider_ids, registry=registry, **kwargs), registry)


async def bounded[T](call: Awaitable[T]) -> T:
    """Fail, rather than hang, if a lifecycle deadline is not enforced."""
    return await asyncio.wait_for(call, 5)


def test_duplicate_implementation_ids_are_refused() -> None:
    implementation = FixtureSet().implementation()
    with pytest.raises(ValueError, match="duplicate"):
        ImplementationRegistry([implementation, implementation])


def test_configuration_cannot_select_an_unregistered_implementation() -> None:
    with pytest.raises(ConfigValidationError):
        validate_provider_config(fixture_config("primary"), ImplementationRegistry([]).specs())


async def test_ready_providers_are_eligible_in_configured_order() -> None:
    providers = await started(FixtureSet(), "secondary", "primary")
    assert providers.state("primary") == "ready"
    assert providers.eligible("search", "search.query") == ("secondary", "primary")


async def test_disabled_provider_is_never_created_or_eligible() -> None:
    fixtures = FixtureSet()
    providers = await started(fixtures, "primary", "spare", disabled=("spare",))
    assert providers.state("spare") == "disabled"
    assert "spare" not in fixtures.calls
    assert providers.eligible("search", "search.query") == ("primary",)


async def test_failed_initialization_leaves_other_providers_usable() -> None:
    fixtures = FixtureSet(behaviours={"broken": FixtureBehaviour(initialize="fail")})
    providers = await started(fixtures, "broken", "primary")
    assert providers.state("broken") == "unavailable"
    assert providers.health("broken").issues[0].code == "provider_unavailable"
    assert providers.eligible("search", "search.query") == ("primary",)


async def test_initialization_exception_is_contained_without_its_message(caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.INFO)
    fixtures = FixtureSet(behaviours={"broken": FixtureBehaviour(initialize="raise")})
    providers = await started(fixtures, "broken", "primary")
    assert providers.state("broken") == "unavailable"
    assert providers.health("broken").issues[0].code == "internal_error"
    assert FAILURE_DETAIL_TEXT not in caplog.text
    assert FAILURE_DETAIL_TEXT not in repr(providers.health("broken"))


async def test_hung_initialization_is_bounded_by_the_deadline() -> None:
    fixtures = FixtureSet(behaviours={"slow": FixtureBehaviour(initialize="hang")})
    begin = time.monotonic()
    providers = await bounded(started(fixtures, "slow", "primary", timeout_ms=200))
    assert time.monotonic() - begin < 2
    assert providers.state("slow") == "unavailable"
    assert providers.health("slow").issues[0].code == "timeout"
    assert providers.state("primary") == "ready"


async def test_degraded_provider_remains_eligible() -> None:
    fixtures = FixtureSet(behaviours={"partial": FixtureBehaviour(initial_state="degraded")})
    providers = await started(fixtures, "partial")
    assert providers.state("partial") == "degraded"
    assert providers.eligible("search", "search.query") == ("partial",)


async def test_invalid_initial_state_is_treated_as_unavailable() -> None:
    fixtures = FixtureSet(behaviours={"odd": FixtureBehaviour(initial_state="stopped")})
    providers = await started(fixtures, "odd")
    assert providers.state("odd") == "unavailable"


async def test_undeclared_capability_is_not_eligible() -> None:
    providers = await started(FixtureSet(), "primary")
    assert providers.eligible("search", "retrieval.http") == ()
    assert providers.eligible("retrieval", "retrieval.http") == ()


async def test_no_configured_provider_means_no_eligible_route() -> None:
    providers = await started(FixtureSet())
    assert providers.eligible("search", "search.query") == ()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        pytest.param({"implementation_id": "other"}, "implementation", id="implementation-id"),
        pytest.param({"family": "retrieval"}, "family", id="family"),
        pytest.param({"contract_version": "2.0"}, "contract", id="contract-version"),
        pytest.param(
            {"capabilities": (CapabilityDeclaration(capability="retrieval.http"),)},
            "capability",
            id="foreign-capability",
        ),
        pytest.param({"capabilities": ()}, "capabilit", id="no-capabilities"),
    ],
)
async def test_declaration_mismatch_stops_startup(overrides: dict[str, object], message: str) -> None:
    fixtures = FixtureSet(behaviours={"primary": FixtureBehaviour(describe_overrides=overrides)})
    with pytest.raises(ProviderRegistrationError, match=message) as excinfo:
        await started(fixtures, "primary")
    assert "primary" in str(excinfo.value)


async def test_declared_capability_needs_its_method() -> None:
    with pytest.raises(ProviderRegistrationError, match="search"):
        await started(FixtureSet(provider_class=NoSearchMethod), "primary")


async def test_factory_failure_stops_startup_without_its_message() -> None:
    def broken(_settings: object) -> object:
        raise RuntimeError(FAILURE_DETAIL_TEXT)

    registry = ImplementationRegistry(
        [Implementation(FIXTURE_IMPLEMENTATION, "search", broken, FIXTURE_MANIFEST)]  # type: ignore[arg-type]
    )
    with pytest.raises(ProviderRegistrationError) as excinfo:
        await ProviderSet.start(config("primary", registry=registry), registry)
    assert FAILURE_DETAIL_TEXT not in str(excinfo.value)


async def test_health_refresh_follows_provider_state() -> None:
    fixtures = FixtureSet()
    providers = await started(fixtures, "primary")
    behaviour = fixtures.behaviours["primary"]
    for state in ("degraded", "unavailable", "ready"):
        behaviour.health_state = state
        await providers.refresh_health()
        assert providers.state("primary") == state


@pytest.mark.parametrize(("behaviour", "code"), [("raise", "internal_error"), ("hang", "timeout")])
async def test_failed_health_check_marks_unavailable(behaviour: str, code: str) -> None:
    fixtures = FixtureSet()
    providers = await started(fixtures, "primary", timeout_ms=200)
    fixtures.behaviours["primary"].health = behaviour  # type: ignore[assignment]
    await bounded(providers.refresh_health())
    assert providers.state("primary") == "unavailable"
    assert providers.health("primary").issues[0].code == code


async def test_health_refresh_skips_disabled_providers() -> None:
    fixtures = FixtureSet()
    providers = await started(fixtures, "primary", "spare", disabled=("spare",))
    await providers.refresh_health()
    assert providers.state("spare") == "disabled"


async def test_shutdown_stops_every_provider_within_the_deadline() -> None:
    fixtures = FixtureSet(
        behaviours={"stuck": FixtureBehaviour(shutdown="hang"), "noisy": FixtureBehaviour(shutdown="raise")}
    )
    providers = await started(fixtures, "stuck", "noisy", "primary", timeout_ms=200)
    begin = time.monotonic()
    await bounded(providers.shutdown())
    assert time.monotonic() - begin < 2
    assert {providers.state(p) for p in ("stuck", "noisy", "primary")} == {"stopped"}
    assert all(fixtures.calls[p].shut_down == 1 for p in ("stuck", "noisy", "primary"))
    assert providers.eligible("search", "search.query") == ()


async def test_global_timeout_applies_without_an_instance_override() -> None:
    raw = fixture_config("slow")
    raw["providers"]["slow"]["limits"] = {}
    raw["limits"] = {**raw["limits"], "timeout_ms": 200}
    fixtures = FixtureSet(behaviours={"slow": FixtureBehaviour(initialize="hang")})
    registry = ImplementationRegistry([fixtures.implementation()])
    begin = time.monotonic()
    providers = await bounded(ProviderSet.start(validate_provider_config(raw, registry.specs()), registry))
    assert time.monotonic() - begin < 2
    assert providers.state("slow") == "unavailable"


async def test_provider_instance_is_available_only_while_eligible() -> None:
    fixtures = FixtureSet(behaviours={"broken": FixtureBehaviour(initialize="fail")})
    providers = await started(fixtures, "broken", "primary")
    assert providers.provider("primary").describe().implementation_id == FIXTURE_IMPLEMENTATION
    with pytest.raises(LookupError):
        providers.provider("broken")


def test_every_contract_capability_has_an_execution_method() -> None:
    from typing import get_args

    from grenslan.providers.contract import Capability
    from grenslan.providers.registry import METHOD_BY_CAPABILITY

    assert set(METHOD_BY_CAPABILITY) == set(get_args(Capability))


async def test_manifest_verification_failure_stops_startup(tmp_path: Path) -> None:
    manifest = tmp_path / "fixture.json"
    data = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(data | {"implementation_version": "other"}), encoding="utf-8")
    with pytest.raises(ProviderRegistrationError, match="primary"):
        await started(FixtureSet(manifest=manifest), "primary")


async def test_disabled_provider_implementation_is_not_verified(tmp_path: Path) -> None:
    fixtures = FixtureSet(manifest=tmp_path / "absent.json")
    providers = await started(fixtures, "spare", disabled=("spare",))
    assert providers.state("spare") == "disabled"


def test_check_registers_enabled_instances_without_initializing() -> None:
    fixtures = FixtureSet()
    registry = ImplementationRegistry([fixtures.implementation()])
    registry.check(config("primary", "spare", registry=registry, disabled=("spare",)))
    assert fixtures.calls["primary"].initialized == 0
    assert "spare" not in fixtures.calls


def test_unsupported_platform_stops_registration() -> None:
    fixtures = FixtureSet(
        behaviours={"primary": FixtureBehaviour(describe_overrides={"supported_platforms": ("linux-aarch64",)})}
    )
    registry = ImplementationRegistry([fixtures.implementation()], platform="linux-x86_64")
    with pytest.raises(ProviderRegistrationError, match="platform"):
        registry.check(config("primary", registry=registry))


def test_factories_receive_resolved_scopes_and_effective_limits() -> None:
    received: list[InstanceSettings] = []
    fixtures = FixtureSet()
    base = fixtures.implementation()

    def factory(settings: InstanceSettings) -> Provider:
        received.append(settings)
        return base.factory(settings)

    registry = ImplementationRegistry([dataclasses.replace(base, factory=factory)])
    loaded = config("one", registry=registry, timeout_ms=1500)
    registry.check(loaded)
    (settings,) = received
    assert settings.network_scope == loaded.data["network_scopes"]["public_web"]
    assert settings.disclosure_scope == loaded.data["disclosure_scopes"]["search_queries"]
    assert settings.limits["timeout_ms"] == 1500
    assert settings.limits["max_items"] == loaded.data["limits"]["max_items"]


def test_a_configuration_problem_from_a_factory_is_reported_with_its_message() -> None:
    fixtures = FixtureSet()
    base = fixtures.implementation()

    def factory(settings: InstanceSettings) -> Provider:
        raise ConfigurationProblem("adapter_settings/engines", "at least one engine is required")

    registry = ImplementationRegistry([dataclasses.replace(base, factory=factory)])
    with pytest.raises(ProviderRegistrationError, match=r"'one'.*adapter_settings/engines: at least one engine"):
        registry.check(config("one", registry=registry))
