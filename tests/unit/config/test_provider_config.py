"""Provider configuration schema and cross-field validation (PC-059, PC-060, F-G15)."""

from __future__ import annotations

from typing import Any

import pytest

from grenslan.config.provider_config import ConfigValidationError, validate_provider_config

from config_fixtures import IMPLEMENTATIONS, connected_config


def problems(config: dict[str, Any]) -> list[str]:
    with pytest.raises(ConfigValidationError) as excinfo:
        validate_provider_config(config, IMPLEMENTATIONS)
    return [f"{p.location} {p.message}" for p in excinfo.value.problems]


def assert_problem(config: dict[str, Any], location: str, fragment: str) -> None:
    found = problems(config)
    assert any(item.startswith(location + " ") and fragment in item for item in found), found


def add_external_provider(config: dict[str, Any], **overrides: Any) -> dict[str, Any]:
    provider = {
        "family": "search",
        "implementation": "academic",
        "enabled": True,
        "endpoint": {"url": "https://api.example.org/v1/"},
        "network_scope": "academic_api",
        "disclosure_scope": "search_queries",
        "limits": {},
    }
    provider.update(overrides)
    config["providers"]["academic_one"] = provider
    config["routing"]["search"].append("academic_one")
    return provider


def add_intelligence(config: dict[str, Any], *, enabled: bool = True, capabilities: list[str] | None = None) -> None:
    config["providers"]["vision"] = {
        "family": "intelligence",
        "implementation": "ollama",
        "enabled": enabled,
        "endpoint": {"url": "http://inference.internal:11434/"},
        "network_scope": "local_inference",
        "disclosure_scope": "local_only",
        "limits": {},
        "intelligence": {"model": "operator-model", "capabilities": capabilities or ["vision", "model_ocr"]},
    }
    config["routing"]["intelligence"] = ["vision"]


def add_model_ocr(config: dict[str, Any], intelligence_provider: str = "vision") -> None:
    config["providers"]["ocr_assisted"] = {
        "family": "ocr",
        "implementation": "tesseract",
        "enabled": True,
        "limits": {},
        "ocr": {"model_assisted": True, "intelligence_provider": intelligence_provider},
    }
    config["routing"]["ocr"] = ["ocr_assisted"]


def add_browser(config: dict[str, Any], *, default: str = "desktop", allowed: list[str] | None = None) -> None:
    config["browser_profiles"]["desktop"] = {"engine": "chromium", "viewport": {"width": 1280, "height": 800}}
    config["providers"]["browser_main"] = {
        "family": "browser",
        "implementation": "chromium",
        "enabled": True,
        "network_scope": "public_web",
        "disclosure_scope": "search_queries",
        "limits": {},
        "browser": {
            "engine": "chromium",
            "controller": "playwright",
            "max_sessions": 2,
            "session_lifetime_ms": 300_000,
            "max_interactions": 50,
            "max_pages": 10,
            "max_screenshot_pixels": 8_000_000,
            "profile_selection": "default",
            "allowed_profiles": allowed if allowed is not None else ["desktop"],
            "default_profile": default,
        },
    }
    config["routing"]["browser"] = ["browser_main"]


def test_valid_connected_configuration_is_accepted() -> None:
    validated = validate_provider_config(connected_config(), IMPLEMENTATIONS)
    assert validated.deployment_mode == "connected"
    assert validated.routes("search") == ("searxng_local",)


def test_validated_configuration_is_immutable() -> None:
    validated = validate_provider_config(connected_config(), IMPLEMENTATIONS)
    with pytest.raises(TypeError):
        validated.providers["searxng_local"]["enabled"] = False  # type: ignore[index]


def test_valid_extended_configuration_is_accepted() -> None:
    config = connected_config()
    add_external_provider(config, adapter_settings={"contact_email": "ops@example.org"})
    config["optional_intelligence_enabled"] = True
    add_intelligence(config)
    add_model_ocr(config)
    add_browser(config)
    validate_provider_config(config, IMPLEMENTATIONS)


def test_unknown_top_level_key_is_rejected() -> None:
    config = connected_config()
    config["plugins"] = ["anything"]
    assert_problem(config, "/", "unknown property")


def test_missing_required_global_limit_is_rejected() -> None:
    config = connected_config()
    del config["limits"]["max_redirects"]
    assert_problem(config, "/limits", "required")


def test_schema_problems_do_not_echo_values() -> None:
    config = connected_config()
    config["providers"]["searxng_local"]["limits"]["timeout_ms"] = "sk-not-a-number-secret"
    assert all("sk-not-a-number-secret" not in item for item in problems(config))


def test_unknown_implementation_is_rejected() -> None:
    config = connected_config()
    config["providers"]["http_direct"]["implementation"] = "downloaded_plugin"
    assert_problem(config, "/providers/http_direct/implementation", "not an approved installed implementation")


def test_implementation_family_must_match() -> None:
    config = connected_config()
    config["providers"]["http_direct"]["implementation"] = "chromium"
    assert_problem(config, "/providers/http_direct/implementation", "family")


def test_route_to_unknown_provider_is_rejected() -> None:
    config = connected_config()
    config["routing"]["search"].append("missing")
    assert_problem(config, "/routing/search/1", "unknown provider")


def test_route_family_must_match_provider_family() -> None:
    config = connected_config()
    config["routing"]["search"].append("http_direct")
    assert_problem(config, "/routing/search/1", "family")


def test_disabled_provider_may_remain_in_route() -> None:
    config = connected_config()
    config["providers"]["http_direct"]["enabled"] = False
    validated = validate_provider_config(config, IMPLEMENTATIONS)
    assert validated.routes("retrieval") == ()


@pytest.mark.parametrize("field", ["network_scope", "disclosure_scope"])
def test_scope_references_must_exist(field: str) -> None:
    config = connected_config()
    config["providers"]["searxng_local"][field] = "nonexistent"
    assert_problem(config, f"/providers/searxng_local/{field}", "unknown")


@pytest.mark.parametrize("family_provider", ["searxng_local", "http_direct"])
def test_enabled_network_capable_provider_requires_scopes(family_provider: str) -> None:
    config = connected_config()
    del config["providers"][family_provider]["network_scope"]
    del config["providers"][family_provider]["disclosure_scope"]
    assert_problem(config, f"/providers/{family_provider}", "network and disclosure scope")


def test_credential_reference_must_exist() -> None:
    config = connected_config()
    add_external_provider(config, credential_ref="academic_key")
    assert_problem(config, "/providers/academic_one/credential_ref", "unknown")


def test_credential_purpose_must_match_family() -> None:
    config = connected_config()
    config["credential_refs"]["academic_key"] = {
        "secret_ref": "academic_api_key",
        "network_scope": "academic_api",
        "purpose": "retrieval",
    }
    add_external_provider(config, credential_ref="academic_key")
    assert_problem(config, "/providers/academic_one/credential_ref", "purpose")


def test_credential_destination_scope_must_match_provider_scope() -> None:
    config = connected_config()
    config["credential_refs"]["academic_key"] = {
        "secret_ref": "academic_api_key",
        "network_scope": "public_web",
        "purpose": "search",
    }
    add_external_provider(config, credential_ref="academic_key")
    assert_problem(config, "/providers/academic_one/credential_ref", "network scope")


def test_credential_scope_reference_must_exist() -> None:
    config = connected_config()
    config["credential_refs"]["academic_key"] = {
        "secret_ref": "academic_api_key",
        "network_scope": "nowhere",
        "purpose": "search",
    }
    assert_problem(config, "/credential_refs/academic_key/network_scope", "unknown")


@pytest.mark.parametrize(
    "url",
    [
        "https://user:sk-pass-secret@api.example.org/v1/",
        "https://api.example.org/v1/?api_key=sk-query-secret",
        "https://api.example.org/v1/?Token=sk-query-secret",
    ],
)
def test_endpoint_must_not_carry_credentials(url: str) -> None:
    config = connected_config()
    add_external_provider(config, endpoint={"url": url})
    found = problems(config)
    assert any(item.startswith("/providers/academic_one/endpoint/url ") for item in found), found
    assert all("sk-" not in item for item in found)


def test_endpoint_must_be_an_approved_destination_of_its_scope() -> None:
    config = connected_config()
    add_external_provider(config, endpoint={"url": "https://other.example.net/v1/"})
    assert_problem(config, "/providers/academic_one/endpoint/url", "destination")


def test_endpoint_port_must_match_destination() -> None:
    config = connected_config()
    add_external_provider(config, endpoint={"url": "https://api.example.org:8443/v1/"})
    assert_problem(config, "/providers/academic_one/endpoint/url", "destination")


def test_plain_http_endpoint_requires_scope_permission() -> None:
    config = connected_config()
    config["network_scopes"]["academic_api"]["destinations"][0]["scheme"] = "http"
    config["network_scopes"]["academic_api"]["destinations"][0]["port"] = 80
    add_external_provider(config, endpoint={"url": "http://api.example.org/v1/"})
    assert_problem(config, "/providers/academic_one/endpoint/url", "plain http")


@pytest.mark.parametrize("mode", ["offline", "internal_only"])
def test_isolated_modes_deny_public_web_scopes(mode: str) -> None:
    config = connected_config()
    config["deployment_mode"] = mode
    assert_problem(config, "/providers/searxng_local/network_scope", mode)


def test_isolated_mode_accepts_providers_disabled_from_public_web() -> None:
    config = connected_config()
    config["deployment_mode"] = "offline"
    config["providers"]["searxng_local"]["enabled"] = False
    config["providers"]["http_direct"]["enabled"] = False
    validate_provider_config(config, IMPLEMENTATIONS)


def test_provider_limit_override_cannot_exceed_global_limit() -> None:
    config = connected_config()
    config["providers"]["searxng_local"]["limits"]["timeout_ms"] = 60_000
    assert_problem(config, "/providers/searxng_local/limits/timeout_ms", "global limit")


def test_adapter_settings_without_approved_schema_are_rejected() -> None:
    config = connected_config()
    config["providers"]["http_direct"]["adapter_settings"] = {"anything": True}
    assert_problem(config, "/providers/http_direct/adapter_settings", "no approved settings schema")


def test_adapter_settings_are_validated_against_closed_schema() -> None:
    config = connected_config()
    add_external_provider(config, adapter_settings={"contact_email": "ops@example.org", "extra": 1})
    assert_problem(config, "/providers/academic_one/adapter_settings", "unknown property")


def test_model_ocr_requires_existing_intelligence_provider() -> None:
    config = connected_config()
    config["optional_intelligence_enabled"] = True
    add_model_ocr(config, intelligence_provider="missing")
    assert_problem(config, "/providers/ocr_assisted/ocr/intelligence_provider", "unknown")


def test_model_ocr_requires_enabled_intelligence_provider() -> None:
    config = connected_config()
    config["optional_intelligence_enabled"] = True
    add_intelligence(config, enabled=False)
    add_model_ocr(config)
    assert_problem(config, "/providers/ocr_assisted/ocr/intelligence_provider", "enabled")


def test_model_ocr_requires_model_ocr_capability() -> None:
    config = connected_config()
    config["optional_intelligence_enabled"] = True
    add_intelligence(config, capabilities=["vision"])
    add_model_ocr(config)
    assert_problem(config, "/providers/ocr_assisted/ocr/intelligence_provider", "model_ocr")


def test_model_ocr_requires_optional_intelligence_switch() -> None:
    config = connected_config()
    add_intelligence(config)
    add_model_ocr(config)
    assert_problem(config, "/providers/ocr_assisted/ocr/intelligence_provider", "optional_intelligence_enabled")


def test_browser_default_profile_must_be_allowed() -> None:
    config = connected_config()
    add_browser(config, default="mobile")
    assert_problem(config, "/providers/browser_main/browser/default_profile", "allowed_profiles")


def test_browser_allowed_profile_must_exist() -> None:
    config = connected_config()
    add_browser(config, allowed=["desktop", "mobile"])
    assert_problem(config, "/providers/browser_main/browser/allowed_profiles/1", "unknown")


def test_browser_profile_engine_must_match() -> None:
    config = connected_config()
    add_browser(config)
    config["browser_profiles"]["desktop"]["engine"] = "webkit"
    assert_problem(config, "/providers/browser_main/browser/allowed_profiles/0", "engine")


def test_all_problems_are_reported_together() -> None:
    config = connected_config()
    config["routing"]["search"].append("missing")
    config["providers"]["searxng_local"]["limits"]["timeout_ms"] = 60_000
    assert len(problems(config)) == 2
