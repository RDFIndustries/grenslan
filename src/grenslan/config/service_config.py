"""Service configuration: TLS, ingress, consumer credentials, OAuth issuers and profiles.

Specified by ``docs/implementation/SERVICE-CONFIGURATION.md``. Validation has
the same two stages as the provider configuration: the packaged JSON Schema
(``SERVICE_CONFIG_SCHEMA.json``) checks structure and closed objects; if it
passes, the cross-field checks follow and all of their problems are reported
together. Problem messages name a location but never the configured value.

A short allowlist of settings can be overridden by ``GRENSLAN_*`` environment
variables. Any other ``GRENSLAN_*`` variable is an error, so a misspelt
override cannot be silently ignored. Credentials, issuers and profiles are
never overridable: they are security policy and belong in the reviewed file.
"""

from __future__ import annotations

import copy
import ipaddress
import json
import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from jsonschema import Draft202012Validator

from grenslan.config.loader import DEFAULT_MAX_CONFIG_BYTES, ConfigLoadError, LoadProblem, read_config_data
from grenslan.config.provider_config import (
    ConfigProblem,
    ConfigValidationError,
    freeze_config,
    schema_problems,
)
from grenslan.service.profiles import PROFILES

PACKAGED_SCHEMA = Path(__file__).with_name("SERVICE_CONFIG_SCHEMA.json")

SERVICE_CONFIG_VARIABLE = "GRENSLAN_SERVICE_CONFIG"
PROVIDER_CONFIG_VARIABLE = "GRENSLAN_PROVIDER_CONFIG"
_PATH_VARIABLES = frozenset({SERVICE_CONFIG_VARIABLE, PROVIDER_CONFIG_VARIABLE})
_OVERRIDES: Mapping[str, tuple[tuple[str, str], str]] = {
    "GRENSLAN_LISTEN_HOST": (("listen", "host"), "string"),
    "GRENSLAN_LISTEN_PORT": (("listen", "port"), "integer"),
    "GRENSLAN_TLS_CERTIFICATE_FILE": (("tls", "certificate_file"), "string"),
    "GRENSLAN_TLS_PRIVATE_KEY_FILE": (("tls", "private_key_file"), "string"),
    "GRENSLAN_ALLOWED_HOSTS": (("ingress", "allowed_hosts"), "list"),
    "GRENSLAN_ALLOWED_ORIGINS": (("ingress", "allowed_origins"), "list"),
    "GRENSLAN_MAX_REQUEST_BYTES": (("ingress", "max_request_bytes"), "integer"),
    "GRENSLAN_TOOLS_PROFILE": (("tools", "profile"), "string"),
}
_DECIMAL = re.compile(r"^[0-9]{1,10}$")
_LABEL = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
_DEFAULT_PORTS = {"http": 80, "https": 443}


@dataclass(frozen=True, slots=True)
class ServiceConfig:
    """Validated, immutable service configuration. Host names and origins are lower case."""

    data: Mapping[str, Any]


@cache
def _schema_validator() -> Draft202012Validator:
    schema = json.loads(PACKAGED_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    return Draft202012Validator(schema)


def _parse_override(kind: str, raw: str) -> Any:
    if kind == "integer":
        if not _DECIMAL.fullmatch(raw):
            raise ValueError("must be a decimal integer")
        return int(raw)
    if kind == "list":
        if raw == "":
            return []
        items = [item.strip() for item in raw.split(",")]
        if any(not item for item in items):
            raise ValueError("must be a comma-separated list without empty items")
        return items
    return raw


def apply_environment(
    data: Mapping[str, Any], environ: Mapping[str, str]
) -> tuple[dict[str, Any], list[ConfigProblem]]:
    """Return a copy of ``data`` with the permitted overrides applied, and the problems found."""
    result = copy.deepcopy(dict(data))
    problems: list[ConfigProblem] = []
    for variable in sorted(environ):
        if not variable.startswith("GRENSLAN_") or variable in _PATH_VARIABLES:
            continue
        override = _OVERRIDES.get(variable)
        if override is None:
            problems.append(ConfigProblem(variable, "not a recognised Grenslan setting"))
            continue
        (section, key), kind = override
        try:
            value = _parse_override(kind, environ[variable])
        except ValueError as exc:
            problems.append(ConfigProblem(variable, str(exc)))
            continue
        target = result.setdefault(section, {})
        if isinstance(target, dict):
            target[key] = value
    return result, problems


def is_host(value: str) -> bool:
    """True for an IP address or a host name (lower case, without a port)."""
    try:
        ipaddress.ip_address(value)
    except ValueError:
        pass
    else:
        return True
    labels = value.split(".")
    return len(value) <= 253 and all(_LABEL.fullmatch(label) for label in labels) and not labels[-1].isdigit()


class _Checker:
    def __init__(self, data: dict[str, Any], tool_names: Collection[str]) -> None:
        self.data = data
        self.tools = tool_names
        self.problems: list[ConfigProblem] = []

    def problem(self, location: str, message: str) -> None:
        self.problems.append(ConfigProblem(location, message))

    def run(self) -> list[ConfigProblem]:
        if not is_host(self.data["listen"]["host"].lower()):
            self.problem("/listen/host", "must be an IP address or host name")
        ingress = self.data["ingress"]
        ingress["allowed_hosts"] = [
            self.host(f"/ingress/allowed_hosts/{i}", h) for i, h in enumerate(ingress["allowed_hosts"])
        ]
        ingress["allowed_origins"] = [
            self.origin(f"/ingress/allowed_origins/{i}", origin) for i, origin in enumerate(ingress["allowed_origins"])
        ]
        profiles = self.profiles()
        if self.data["tools"]["profile"] not in profiles:
            self.problem("/tools/profile", "unknown profile")
        digests: set[str] = set()
        for credential_id, credential in self.data["credentials"].items():
            base = f"/credentials/{credential_id}"
            self.tool_list(f"{base}/permissions", credential["permissions"])
            if credential["token_sha256"] in digests:
                self.problem(f"{base}/token_sha256", "token digest is already used by another credential")
            digests.add(credential["token_sha256"])
            if "profile" in credential and credential["profile"] not in profiles:
                self.problem(f"{base}/profile", "unknown profile")
        if "oauth" in self.data:
            self.oauth(self.data["oauth"], set(ingress["allowed_hosts"]))
        return self.problems

    def host(self, location: str, value: str) -> str:
        normalized = value.lower()
        if not is_host(normalized):
            self.problem(location, "must be a host name or IP address without a port")
        return normalized

    def origin(self, location: str, value: str) -> str:
        normalized = value.lower()
        try:
            parts = urlsplit(normalized)
            port = parts.port
        except ValueError:
            self.problem(location, "must be an origin of the form scheme://host[:port]")
            return normalized
        if (
            parts.scheme not in _DEFAULT_PORTS
            or not parts.hostname
            or "@" in parts.netloc
            or parts.path
            or parts.query
            or parts.fragment
            or normalized.endswith(("?", "#"))
            or not is_host(parts.hostname)
        ):
            self.problem(location, "must be an origin of the form scheme://host[:port] with scheme https or http")
        elif port == _DEFAULT_PORTS[parts.scheme]:
            self.problem(location, "must omit the default port, as browsers do")
        return normalized

    def tool_list(self, location: str, tools: list[str]) -> None:
        for index, tool in enumerate(tools):
            if tool not in self.tools:
                self.problem(f"{location}/{index}", "not a registered tool")

    def profiles(self) -> set[str]:
        custom = self.data["tools"].get("custom_profiles", {})
        for name, tools in custom.items():
            base = f"/tools/custom_profiles/{name}"
            if name in PROFILES or name == "custom":
                self.problem(base, "a custom profile cannot reuse a built-in profile name")
            for index, tool in enumerate(tools):
                if tool not in PROFILES["full"]:
                    self.problem(f"{base}/{index}", "not a tool that a profile can expose")
        return set(PROFILES) | set(custom)

    def https_url(self, location: str, value: str) -> str | None:
        try:
            parts = urlsplit(value)
            parts.port  # noqa: B018 - raises for an invalid port
        except ValueError:
            parts = None
        if parts is None or parts.scheme != "https" or not parts.hostname or "@" in parts.netloc:
            self.problem(location, "must be an https URL with a host")
            return None
        if parts.query or parts.fragment or "?" in value or "#" in value:
            self.problem(location, "must not have a query or fragment")
            return None
        return parts.hostname

    def oauth(self, oauth: Mapping[str, Any], allowed_hosts: set[str]) -> None:
        host = self.https_url("/oauth/resource", oauth["resource"])
        if host is not None and host not in allowed_hosts:
            self.problem("/oauth/resource", "the resource host must be in ingress.allowed_hosts")
        seen: set[str] = set()
        for issuer_id, issuer in oauth["issuers"].items():
            base = f"/oauth/issuers/{issuer_id}"
            self.https_url(f"{base}/issuer", issuer["issuer"])
            if issuer["issuer"] in seen:
                self.problem(f"{base}/issuer", "issuer is already configured")
            seen.add(issuer["issuer"])
            for scope, tools in issuer["scopes"].items():
                self.tool_list(f"{base}/scopes/{scope}", tools)


def validate_service_config(data: Mapping[str, Any], *, tool_names: Collection[str]) -> ServiceConfig:
    """Validate configuration data or raise :class:`ConfigValidationError` listing every problem."""
    problems = schema_problems(_schema_validator(), data)
    checked = copy.deepcopy(dict(data))
    if not problems:
        problems = _Checker(checked, tool_names).run()
    if problems:
        raise ConfigValidationError(problems)
    return ServiceConfig(freeze_config(checked))


def load_service_config_file(
    path: Path,
    environ: Mapping[str, str],
    *,
    tool_names: Collection[str],
    max_bytes: int = DEFAULT_MAX_CONFIG_BYTES,
) -> ServiceConfig:
    """Read ``path``, apply environment overrides and validate; every failure is a :class:`ConfigLoadError`."""
    data, environment_problems = apply_environment(read_config_data(path, max_bytes=max_bytes), environ)
    problems = [LoadProblem(p.location, p.message) for p in environment_problems]
    try:
        config = validate_service_config(data, tool_names=tool_names)
    except ConfigValidationError as exc:
        problems += [LoadProblem(p.location, p.message) for p in exc.problems]
    if problems:
        raise ConfigLoadError(problems)
    return config
