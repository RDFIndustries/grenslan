"""Provider and execution configuration validation (PC-059, PC-060).

Validation has two stages. The adopted JSON Schema (packaged as a byte-identical
copy of ``docs/contracts/PROVIDER_CONFIG_SCHEMA.json``) checks structure,
closed objects and formats. If it passes, the normative cross-field checks
follow; all of their problems are reported together. Configuration selects
implementation IDs from an explicit registry of installed implementations; it
never names modules, paths or anything executable.

Problem messages give a JSON pointer and a reason but never the configured
value, because a misplaced secret must not reach logs or error output.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any, get_args
from urllib.parse import parse_qsl, urlsplit

from jsonschema import Draft202012Validator, FormatChecker

from grenslan.contracts.registry import describe_validation_error
from grenslan.providers.contract import Family

PACKAGED_SCHEMA = Path(__file__).with_name("PROVIDER_CONFIG_SCHEMA.json")

FAMILIES: tuple[Family, ...] = get_args(Family)
NETWORK_FAMILIES = frozenset({"search", "retrieval", "browser", "intelligence"})
ISOLATED_MODES = frozenset({"offline", "internal_only"})
_DEFAULT_PORTS = {"http": 80, "https": 443}
_SECRET_QUERY_MARKERS = ("key", "token", "secret", "password", "passwd", "auth", "signature", "sig", "credential")


@dataclass(frozen=True, slots=True)
class ImplementationSpec:
    """An approved installed implementation that configuration may select."""

    family: Family
    settings_schema: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if self.settings_schema is not None:
            Draft202012Validator.check_schema(self.settings_schema)


@dataclass(frozen=True, slots=True)
class ConfigProblem:
    location: str
    message: str


class ConfigValidationError(ValueError):
    def __init__(self, problems: list[ConfigProblem]) -> None:
        super().__init__(f"{len(problems)} configuration problem(s)")
        self.problems = problems


def freeze_config(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: freeze_config(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(freeze_config(item) for item in value)
    return value


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    """Validated, immutable provider configuration."""

    data: Mapping[str, Any]

    @property
    def deployment_mode(self) -> str:
        return str(self.data["deployment_mode"])

    @property
    def providers(self) -> Mapping[str, Mapping[str, Any]]:
        providers: Mapping[str, Mapping[str, Any]] = self.data["providers"]
        return providers

    def routes(self, family: Family) -> tuple[str, ...]:
        """Configured route order for ``family``, limited to instances that may execute."""
        if family == "intelligence" and not self.data["optional_intelligence_enabled"]:
            return ()
        return tuple(pid for pid in self.data["routing"][family] if self.providers[pid]["enabled"])


@cache
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(PACKAGED_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema, format_checker=FormatChecker())


def schema_problems(validator: Draft202012Validator, instance: Any, prefix: str = "") -> list[ConfigProblem]:
    problems = []
    for error in sorted(validator.iter_errors(instance), key=lambda e: list(e.absolute_path)):
        described = describe_validation_error(error)
        location = prefix + ("" if described.location == "/" and prefix else described.location)
        problems.append(ConfigProblem(location or "/", described.message))
    return problems


class _Checker:
    def __init__(self, data: Mapping[str, Any], implementations: Mapping[str, ImplementationSpec]) -> None:
        self.data = data
        self.implementations = implementations
        self.problems: list[ConfigProblem] = []

    def problem(self, location: str, message: str) -> None:
        self.problems.append(ConfigProblem(location, message))

    def run(self) -> list[ConfigProblem]:
        for scope_id, scope in self.data["network_scopes"].items():
            for index, destination in enumerate(scope["destinations"]):
                if destination["scheme"] == "http" and not destination.get("allow_private_address", False):
                    self.problem(
                        f"/network_scopes/{scope_id}/destinations/{index}",
                        "plain http is permitted only to local network destinations; set allow_private_address",
                    )
        for provider_id, provider in self.data["providers"].items():
            self.provider(f"/providers/{provider_id}", provider)
        for credential_id, credential in self.data["credential_refs"].items():
            if credential["network_scope"] not in self.data["network_scopes"]:
                self.problem(f"/credential_refs/{credential_id}/network_scope", "unknown network scope reference")
        for family in FAMILIES:
            for index, provider_id in enumerate(self.data["routing"][family]):
                location = f"/routing/{family}/{index}"
                provider = self.data["providers"].get(provider_id)
                if provider is None:
                    self.problem(location, "route names an unknown provider")
                elif provider["family"] != family:
                    self.problem(location, "provider family does not match the route family")
        return self.problems

    def provider(self, base: str, provider: Mapping[str, Any]) -> None:
        family = provider["family"]
        implementation = self.implementations.get(provider["implementation"])
        if implementation is None:
            self.problem(f"{base}/implementation", "not an approved installed implementation")
        elif implementation.family != family:
            self.problem(f"{base}/implementation", "implementation family does not match the provider family")

        for field, scopes in (("network_scope", "network_scopes"), ("disclosure_scope", "disclosure_scopes")):
            if field in provider and provider[field] not in self.data[scopes]:
                self.problem(f"{base}/{field}", f"unknown {field.replace('_', ' ')} reference")

        enabled = provider["enabled"]
        if (
            enabled
            and family in NETWORK_FAMILIES
            and not ("network_scope" in provider and "disclosure_scope" in provider)
        ):
            self.problem(base, "an enabled network-capable provider requires a network and disclosure scope")

        network_scope = self.data["network_scopes"].get(provider.get("network_scope"))
        mode = self.data["deployment_mode"]
        if enabled and network_scope is not None and mode in ISOLATED_MODES and network_scope["public_web"]:
            self.problem(f"{base}/network_scope", f"a public web network scope is not permitted in {mode} mode")

        if "credential_ref" in provider:
            self.credential(base, provider)
        if "endpoint" in provider:
            self.endpoint(f"{base}/endpoint/url", provider["endpoint"]["url"], network_scope)
        for name, value in provider["limits"].items():
            if value > self.data["limits"][name]:
                self.problem(f"{base}/limits/{name}", "provider limit exceeds the global limit")
        if "adapter_settings" in provider and implementation is not None:
            self.adapter_settings(f"{base}/adapter_settings", provider["adapter_settings"], implementation)
        if enabled and provider.get("ocr", {}).get("model_assisted"):
            self.model_ocr(f"{base}/ocr/intelligence_provider", provider["ocr"]["intelligence_provider"])
        if "browser" in provider:
            self.browser(f"{base}/browser", provider["browser"])

    def credential(self, base: str, provider: Mapping[str, Any]) -> None:
        location = f"{base}/credential_ref"
        credential = self.data["credential_refs"].get(provider["credential_ref"])
        if credential is None:
            self.problem(location, "unknown credential reference")
            return
        if credential["purpose"] != provider["family"]:
            self.problem(location, "credential purpose does not match the provider family")
        if credential["network_scope"] != provider.get("network_scope"):
            self.problem(location, "credential network scope does not match the provider network scope")

    def endpoint(self, location: str, url: str, network_scope: Mapping[str, Any] | None) -> None:
        parts = urlsplit(url)
        if "@" in parts.netloc:
            self.problem(location, "endpoint must not contain user information")
        for name, _ in parse_qsl(parts.query, keep_blank_values=True):
            if any(marker in name.lower() for marker in _SECRET_QUERY_MARKERS):
                self.problem(location, "endpoint must not carry credentials in query parameters")
                break
        if network_scope is None:
            return
        scheme = parts.scheme.lower()
        try:
            port = parts.port or _DEFAULT_PORTS.get(scheme)
        except ValueError:
            self.problem(location, "endpoint port is invalid")
            return
        host = (parts.hostname or "").lower()
        if not any(
            destination["scheme"] == scheme and destination["host"].lower() == host and destination["port"] == port
            for destination in network_scope["destinations"]
        ):
            self.problem(location, "endpoint is not an approved destination of its network scope")
        if scheme == "http" and not network_scope["allow_outbound_http"]:
            self.problem(location, "a plain http endpoint requires allow_outbound_http in its network scope")

    def adapter_settings(self, location: str, settings: Any, implementation: ImplementationSpec) -> None:
        if implementation.settings_schema is None:
            self.problem(location, "the implementation has no approved settings schema")
            return
        validator = Draft202012Validator(implementation.settings_schema, format_checker=FormatChecker())
        self.problems.extend(schema_problems(validator, settings, prefix=location))

    def model_ocr(self, location: str, intelligence_id: str) -> None:
        intelligence = self.data["providers"].get(intelligence_id)
        if intelligence is None or intelligence["family"] != "intelligence":
            self.problem(location, "unknown intelligence provider reference")
            return
        if not intelligence["enabled"]:
            self.problem(location, "model-assisted OCR must reference an enabled intelligence provider")
        if "model_ocr" not in intelligence["intelligence"]["capabilities"]:
            self.problem(location, "the intelligence provider does not declare model_ocr capability")
        if not self.data["optional_intelligence_enabled"]:
            self.problem(location, "model-assisted OCR requires optional_intelligence_enabled")

    def browser(self, base: str, settings: Mapping[str, Any]) -> None:
        if settings["default_profile"] not in settings["allowed_profiles"]:
            self.problem(f"{base}/default_profile", "the default profile must be listed in allowed_profiles")
        for index, name in enumerate(settings["allowed_profiles"]):
            profile = self.data["browser_profiles"].get(name)
            if profile is None:
                self.problem(f"{base}/allowed_profiles/{index}", "unknown browser profile")
            elif profile["engine"] != settings["engine"]:
                self.problem(
                    f"{base}/allowed_profiles/{index}", "browser profile engine does not match the provider engine"
                )


def validate_provider_config(
    data: Mapping[str, Any], implementations: Mapping[str, ImplementationSpec]
) -> ProviderConfig:
    """Validate configuration data or raise :class:`ConfigValidationError` listing every problem."""
    problems = schema_problems(_schema_validator(), data)
    if not problems:
        problems = _Checker(data, implementations).run()
    if problems:
        raise ConfigValidationError(problems)
    return ProviderConfig(freeze_config(dict(data)))
