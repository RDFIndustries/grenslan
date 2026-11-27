"""capabilities_get: authorization-aware capability projection (TC-042, TC-043, PC-010, PC-064)."""

from __future__ import annotations

import json
from typing import Any

import pytest

from grenslan import __version__
from grenslan.config.provider_config import validate_provider_config
from grenslan.contracts.registry import ToolRegistry
from grenslan.providers.contract import CapabilityDeclaration
from grenslan.providers.registry import ImplementationRegistry
from grenslan.providers.runtime import ProviderSet
from grenslan.service.capabilities import CapabilitiesHandler, public_limits
from grenslan.service.context import InvocationContext
from grenslan.service.dispatch import ArgumentLimits, DispatchKind, ToolDispatcher
from grenslan.service.profiles import profile_tools

from fixture_providers import FixtureBehaviour, FixtureSet, fixture_config

REGISTRY = ToolRegistry.load()
SEARCH_TOOLS = ("web_search", "image_search")
EVERYTHING = frozenset(REGISTRY.tool_names)


class GrantedPermissions:
    def permits(self, context: InvocationContext, tool: str) -> bool:
        return tool in context.permissions


def context(permissions: frozenset[str] = EVERYTHING, profile: str | None = None) -> InvocationContext:
    return InvocationContext(
        application_id="app-a", user_id=None, agent_id=None, instance_id=None, permissions=permissions, profile=profile
    )


async def providers_for(fixtures: FixtureSet, *ids: str, disabled: tuple[str, ...] = ()) -> tuple[ProviderSet, Any]:
    registry = ImplementationRegistry([fixtures.implementation()])
    config = validate_provider_config(fixture_config(*ids, disabled=disabled), registry.specs())
    return await ProviderSet.start(config, registry), config


async def capabilities(
    providers: ProviderSet,
    config: Any,
    *,
    arguments: dict[str, Any] | None = None,
    caller: InvocationContext | None = None,
    profile: str = "full",
    implemented: tuple[str, ...] = SEARCH_TOOLS,
) -> dict[str, Any]:
    handler = CapabilitiesHandler(
        registry=REGISTRY,
        providers=providers,
        requirements={"capabilities_get": (), **{tool: ("search.query",) for tool in implemented}},
        profile_name=profile,
        profile=profile_tools(profile),
        limits=public_limits(config),
    )
    handlers: dict[str, Any] = {"capabilities_get": handler}
    for tool in implemented:
        handlers[tool] = handler  # only exposure matters here; search handlers are not exercised
    dispatcher = ToolDispatcher(
        REGISTRY,
        handlers=handlers,
        policy=GrantedPermissions(),
        profile=profile_tools(profile),
        max_request_bytes=65536,
        argument_limits=ArgumentLimits(max_string_chars=1024, max_array_items=64, max_depth=8),
    )
    body = json.dumps(arguments or {}).encode()
    result = await dispatcher.invoke_body("capabilities_get", body, caller or context())
    assert result.kind is DispatchKind.OUTCOME
    assert result.envelope is not None
    assert result.envelope["status"] == "completed", result.envelope
    return dict(result.envelope["result"])


def by_name(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {entry["name"]: entry for entry in result["capabilities"]}


async def test_reports_service_identity_profile_and_limits() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    result = await capabilities(providers, config)
    assert result["service"] == "grenslan"
    assert result["service_version"] == __version__
    assert result["contract_version"] == "1.0"
    assert result["profile"] == "full"
    limits = config.data["limits"]
    assert result["limits"] == {
        "max_output_bytes": limits["max_output_bytes"],
        "max_download_bytes": limits["max_download_bytes"],
        "max_timeout_ms": limits["timeout_ms"],
        "max_concurrency": limits["max_concurrency"],
    }


async def test_ready_provider_makes_search_enabled() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    entries = by_name(await capabilities(providers, config))
    assert entries["web_search"]["status"] == "enabled"
    assert entries["capabilities_get"]["status"] == "enabled"


async def test_unimplemented_visible_tools_are_unsupported() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    entries = by_name(await capabilities(providers, config))
    assert entries["document_read"]["status"] == "unsupported"
    assert entries["operation_status"]["status"] == "unsupported"


async def test_failed_provider_makes_its_functions_unavailable_and_not_others() -> None:
    fixtures = FixtureSet(behaviours={"broken": FixtureBehaviour(initialize="fail")})
    providers, config = await providers_for(fixtures, "broken")
    entries = by_name(await capabilities(providers, config))
    assert entries["web_search"]["status"] == "unavailable"
    assert entries["capabilities_get"]["status"] == "enabled"


async def test_one_working_provider_keeps_the_function_enabled() -> None:
    fixtures = FixtureSet(behaviours={"broken": FixtureBehaviour(initialize="fail")})
    providers, config = await providers_for(fixtures, "broken", "primary")
    assert by_name(await capabilities(providers, config))["web_search"]["status"] == "enabled"


async def test_no_enabled_provider_means_disabled() -> None:
    providers, config = await providers_for(FixtureSet(), "spare", disabled=("spare",))
    assert by_name(await capabilities(providers, config))["web_search"]["status"] == "disabled"
    providers, config = await providers_for(FixtureSet())
    assert by_name(await capabilities(providers, config))["web_search"]["status"] == "disabled"


async def test_degraded_provider_is_enabled_with_a_limitation() -> None:
    fixtures = FixtureSet(behaviours={"partial": FixtureBehaviour(initial_state="degraded")})
    providers, config = await providers_for(fixtures, "partial")
    entry = by_name(await capabilities(providers, config))["web_search"]
    assert entry["status"] == "enabled"
    assert entry["limitations"]


async def test_formats_and_limitations_come_from_serving_declarations() -> None:
    declaration = (
        CapabilityDeclaration(
            capability="search.query", formats=("json", "html"), limitations=("results are snippets only",)
        ),
    )
    fixtures = FixtureSet(behaviours={"primary": FixtureBehaviour(describe_overrides={"capabilities": declaration})})
    providers, config = await providers_for(fixtures, "primary")
    entry = by_name(await capabilities(providers, config))["web_search"]
    assert entry["formats"] == ["html", "json"]
    assert entry["limitations"] == ["results are snippets only"]


async def test_provider_identities_and_health_details_are_never_reported() -> None:
    fixtures = FixtureSet(behaviours={"secret_instance": FixtureBehaviour(initialize="fail")})
    providers, config = await providers_for(fixtures, "secret_instance")
    text = json.dumps(await capabilities(providers, config))
    assert "secret_instance" not in text
    assert "fixture" not in text


async def test_unauthorized_tools_are_omitted() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    caller = context(frozenset({"capabilities_get", "web_search"}))
    entries = by_name(await capabilities(providers, config, caller=caller))
    assert set(entries) == {"capabilities_get", "web_search"}


async def test_tools_outside_the_profile_are_omitted() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    entries = by_name(await capabilities(providers, config, profile="basic"))
    assert "document_read" not in entries
    assert "web_search" in entries
    assert set(entries) <= profile_tools("basic")


async def test_requested_tools_are_reported_in_order_without_revealing_authorization() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    caller = context(frozenset({"capabilities_get", "web_search"}))
    result = await capabilities(
        providers,
        config,
        caller=caller,
        arguments={"tools": ["image_search", "web_search", "no_such_tool", "web_search"]},
    )
    assert [(entry["name"], entry["status"]) for entry in result["capabilities"]] == [
        ("image_search", "disabled"),
        ("web_search", "enabled"),
        ("no_such_tool", "unsupported"),
    ]
    assert set(result["capabilities"][0]) == {"name", "status"}


async def test_credential_profile_name_is_reported() -> None:
    providers, config = await providers_for(FixtureSet(), "primary")
    result = await capabilities(providers, config, caller=context(profile="search_only"))
    assert result["profile"] == "search_only"


async def test_health_changes_are_reflected() -> None:
    fixtures = FixtureSet()
    providers, config = await providers_for(fixtures, "primary")
    fixtures.behaviours["primary"].health_state = "unavailable"
    await providers.refresh_health()
    assert by_name(await capabilities(providers, config))["web_search"]["status"] == "unavailable"


def test_every_handler_needs_declared_requirements() -> None:
    with pytest.raises(ValueError, match="capabilities_get"):
        CapabilitiesHandler(
            registry=REGISTRY,
            providers=None,  # type: ignore[arg-type]
            requirements={},
            profile_name="full",
            profile=profile_tools("full"),
            limits={},
        )
