"""Service configuration validation and environment overrides (SERVICE-CONFIGURATION.md)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from service_fixtures import QOR_TOKEN, oauth_section, service_data, write_service_file

from grenslan.config.loader import ConfigLoadError
from grenslan.config.provider_config import ConfigValidationError
from grenslan.config.service_config import (
    ServiceConfig,
    apply_environment,
    load_service_config_file,
    validate_service_config,
)
from grenslan.contracts.registry import ToolRegistry

TOOLS = frozenset(ToolRegistry.load().tool_names)


def valid(data: dict[str, Any]) -> ServiceConfig:
    return validate_service_config(data, tool_names=TOOLS)


def problems(data: dict[str, Any]) -> dict[str, str]:
    with pytest.raises(ConfigValidationError) as excinfo:
        valid(data)
    return {problem.location: problem.message for problem in excinfo.value.problems}


def with_path(path: tuple[str, ...], value: Any) -> dict[str, Any]:
    data = service_data()
    target = data
    for name in path[:-1]:
        target = target[name]
    if value is _REMOVE:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return data


_REMOVE = object()


def test_sample_configuration_is_valid() -> None:
    config = valid(service_data())
    assert config.data["listen"]["port"] == 8443
    assert set(config.data["credentials"]) == {"qor", "zygos"}


def test_validated_configuration_is_immutable() -> None:
    config = valid(service_data())
    with pytest.raises(TypeError):
        config.data["listen"]["port"] = 1


@pytest.mark.parametrize(
    ("path", "value", "location"),
    [
        pytest.param(("config_version",), "2.0", "/config_version", id="version"),
        pytest.param(("surprise",), {}, "/", id="unknown-top-level"),
        pytest.param(("listen", "extra"), 1, "/listen", id="unknown-nested"),
        pytest.param(("listen", "port"), 0, "/listen/port", id="port-low"),
        pytest.param(("listen", "port"), 65536, "/listen/port", id="port-high"),
        pytest.param(("tls", "certificate_file"), "relative.pem", "/tls/certificate_file", id="relative-path"),
        pytest.param(("ingress", "allowed_hosts"), [], "/ingress/allowed_hosts", id="no-hosts"),
        pytest.param(("ingress", "allowed_hosts"), ["localhost:8443"], "/ingress/allowed_hosts/0", id="host-port"),
        pytest.param(("ingress", "max_request_bytes"), 0, "/ingress/max_request_bytes", id="body-limit"),
        pytest.param(("ingress", "argument_limits", "max_depth"), 0, "/ingress/argument_limits/max_depth", id="depth"),
        pytest.param(("ingress", "argument_limits"), _REMOVE, "/ingress", id="no-numeric-default"),
        pytest.param(("security_events", "window_seconds"), 0, "/security_events/window_seconds", id="window"),
        pytest.param(("credentials", "qor", "token_sha256"), "ABC", "/credentials/qor/token_sha256", id="digest"),
        pytest.param(("credentials", "qor", "permissions"), [], "/credentials/qor/permissions", id="no-permissions"),
        pytest.param(("credentials", "Bad Name"), {}, "/credentials", id="credential-id"),
        pytest.param(
            ("credentials", "qor", "identity"), {"user_id": "a b"}, "/credentials/qor/identity/user_id", id="identity"
        ),
    ],
)
def test_schema_violations_are_located(path: tuple[str, ...], value: Any, location: str) -> None:
    assert location in problems(with_path(path, value))


@pytest.mark.parametrize(
    "origin",
    ["https://zygos.lan/path", "ftp://zygos.lan", "https://zygos.lan:443", "https://user@zygos.lan", "zygos.lan"],
)
def test_origins_must_be_exact_serialized_origins(origin: str) -> None:
    assert "/ingress/allowed_origins/0" in problems(with_path(("ingress", "allowed_origins"), [origin]))


def test_hosts_and_origins_are_normalized_to_lower_case() -> None:
    data = with_path(("ingress", "allowed_hosts"), ["Grenslan.LAN", "::1"])
    data["ingress"]["allowed_origins"] = ["https://Zygos.LAN:8080"]
    config = valid(data)
    assert config.data["ingress"]["allowed_hosts"] == ("grenslan.lan", "::1")
    assert config.data["ingress"]["allowed_origins"] == ("https://zygos.lan:8080",)


def test_permissions_must_name_registered_tools() -> None:
    data = with_path(("credentials", "qor", "permissions"), ["web_search", "web_serach"])
    assert "/credentials/qor/permissions/1" in problems(data)


def test_token_digests_must_be_unique() -> None:
    data = service_data()
    data["credentials"]["zygos"]["token_sha256"] = data["credentials"]["qor"]["token_sha256"]
    assert "/credentials/zygos/token_sha256" in problems(data)


def test_profiles_must_exist_and_custom_names_cannot_shadow_built_ins() -> None:
    data = with_path(("credentials", "qor", "profile"), "missing")
    data["tools"]["profile"] = "absent"
    data["tools"]["custom_profiles"]["basic"] = ["web_search"]
    data["tools"]["custom_profiles"]["odd"] = ["not_a_tool"]
    found = problems(data)
    assert {"/tools/profile", "/credentials/qor/profile", "/tools/custom_profiles/basic"} <= set(found)
    assert "/tools/custom_profiles/odd/0" in found


def test_every_schema_problem_is_reported_together() -> None:
    data = with_path(("listen", "port"), 0)
    data["ingress"]["max_request_bytes"] = 0
    data["security_events"]["window_seconds"] = 0
    assert {"/listen/port", "/ingress/max_request_bytes", "/security_events/window_seconds"} <= set(problems(data))


def test_problem_messages_never_quote_values() -> None:
    data = with_path(("credentials", "qor", "token_sha256"), QOR_TOKEN)
    data["credentials"]["qor"]["permissions"] = [QOR_TOKEN]
    with pytest.raises(ConfigValidationError) as excinfo:
        valid(data)
    assert all(QOR_TOKEN not in problem.message for problem in excinfo.value.problems)


def test_oauth_section_is_optional_and_validated(tmp_path: Path) -> None:
    assert valid(service_data()).data.get("oauth") is None
    config = valid(service_data(oauth=oauth_section(tmp_path / "jwks.json")))
    assert config.data["oauth"]["resource"] == "https://localhost/mcp"


@pytest.mark.parametrize(
    ("change", "location"),
    [
        pytest.param({"resource": "http://localhost/mcp"}, "/oauth/resource", id="resource-https"),
        pytest.param({"resource": "https://localhost/mcp?x=1"}, "/oauth/resource", id="resource-query"),
        pytest.param({"resource": "https://elsewhere/mcp"}, "/oauth/resource", id="resource-host-allowed"),
        pytest.param({"issuers": {}}, "/oauth/issuers", id="no-issuers"),
    ],
)
def test_oauth_constraints(tmp_path: Path, change: dict[str, Any], location: str) -> None:
    section = {**oauth_section(tmp_path / "jwks.json"), **change}
    assert location in problems(service_data(oauth=section))


def test_oauth_issuer_constraints(tmp_path: Path) -> None:
    section = oauth_section(tmp_path / "jwks.json", issuer="http://idp.example")
    section["issuers"]["idp"]["scopes"] = {"grenslan.search": ["unknown_tool"]}
    found = problems(service_data(oauth=section))
    assert {
        "/oauth/issuers/idp/issuer",
        "/oauth/issuers/idp/scopes/grenslan.search/0",
    } <= set(found)


def test_jwks_file_must_be_absolute(tmp_path: Path) -> None:
    section = oauth_section(Path("keys.json"))
    assert "/oauth/issuers/idp/jwks_file" in problems(service_data(oauth=section))


def test_issuer_values_must_be_unique(tmp_path: Path) -> None:
    section = oauth_section(tmp_path / "jwks.json")
    section["issuers"]["again"] = dict(section["issuers"]["idp"])
    assert "/oauth/issuers/again/issuer" in problems(service_data(oauth=section))


# Environment overrides (D5)


def test_environment_overrides_apply_and_are_validated() -> None:
    data, found = apply_environment(
        service_data(),
        {
            "GRENSLAN_LISTEN_HOST": "192.0.2.10",
            "GRENSLAN_LISTEN_PORT": "9443",
            "GRENSLAN_ALLOWED_HOSTS": "grenslan, localhost",
            "GRENSLAN_ALLOWED_ORIGINS": "",
            "GRENSLAN_MAX_REQUEST_BYTES": "2048",
            "GRENSLAN_TOOLS_PROFILE": "basic",
            "GRENSLAN_TLS_CERTIFICATE_FILE": "/etc/c.pem",
            "GRENSLAN_TLS_PRIVATE_KEY_FILE": "/etc/k.pem",
            "GRENSLAN_SERVICE_CONFIG": "/etc/grenslan/service.yaml",
            "GRENSLAN_PROVIDER_CONFIG": "/etc/grenslan/providers.yaml",
            "PATH": "/usr/bin",
        },
    )
    assert found == []
    config = valid(data)
    assert config.data["listen"] == {"host": "192.0.2.10", "port": 9443}
    assert config.data["ingress"]["allowed_hosts"] == ("grenslan", "localhost")
    assert config.data["ingress"]["allowed_origins"] == ()
    assert config.data["ingress"]["max_request_bytes"] == 2048
    assert config.data["tools"]["profile"] == "basic"
    assert config.data["tls"]["certificate_file"] == "/etc/c.pem"


def test_environment_does_not_modify_the_parsed_file() -> None:
    original = service_data()
    apply_environment(original, {"GRENSLAN_LISTEN_PORT": "9443"})
    assert original["listen"]["port"] == 8443


@pytest.mark.parametrize(
    ("environ", "variable"),
    [
        pytest.param({"GRENSLAN_LISTEN_PORTT": "1"}, "GRENSLAN_LISTEN_PORTT", id="misspelt"),
        pytest.param({"GRENSLAN_CREDENTIALS": "x"}, "GRENSLAN_CREDENTIALS", id="policy-not-overridable"),
        pytest.param({"GRENSLAN_LISTEN_PORT": "+80"}, "GRENSLAN_LISTEN_PORT", id="signed"),
        pytest.param({"GRENSLAN_MAX_REQUEST_BYTES": "1e3"}, "GRENSLAN_MAX_REQUEST_BYTES", id="not-decimal"),
        pytest.param({"GRENSLAN_ALLOWED_HOSTS": "a,,b"}, "GRENSLAN_ALLOWED_HOSTS", id="empty-item"),
    ],
)
def test_environment_problems_name_the_variable_not_the_value(environ: dict[str, str], variable: str) -> None:
    _, found = apply_environment(service_data(), environ)
    assert [problem.location for problem in found] == [variable]
    assert all(value not in problem.message for problem in found for value in environ.values())


def test_overridden_value_is_still_validated() -> None:
    data, found = apply_environment(service_data(), {"GRENSLAN_LISTEN_PORT": "70000"})
    assert found == []
    assert "/listen/port" in problems(data)


# File loading


def test_load_file_applies_environment_and_validates(tmp_path: Path) -> None:
    path = write_service_file(tmp_path / "service.yaml", service_data())
    config = load_service_config_file(path, {"GRENSLAN_LISTEN_PORT": "9000"}, tool_names=TOOLS)
    assert config.data["listen"]["port"] == 9000


def test_load_file_reports_environment_and_schema_problems_together(tmp_path: Path) -> None:
    path = write_service_file(tmp_path / "service.yaml", with_path(("listen", "port"), 0))
    with pytest.raises(ConfigLoadError) as excinfo:
        load_service_config_file(path, {"GRENSLAN_TYPO": "1"}, tool_names=TOOLS)
    assert {problem.location for problem in excinfo.value.problems} >= {"GRENSLAN_TYPO", "/listen/port"}


def test_load_file_rejects_unsafe_yaml(tmp_path: Path) -> None:
    path = tmp_path / "service.yaml"
    path.write_text("config_version: '1.0'\nconfig_version: '1.0'\n", encoding="utf-8")
    with pytest.raises(ConfigLoadError) as excinfo:
        load_service_config_file(path, {}, tool_names=TOOLS)
    assert excinfo.value.problems[0].location == "line 2"


def test_missing_file_is_a_load_error(tmp_path: Path) -> None:
    with pytest.raises(ConfigLoadError):
        load_service_config_file(tmp_path / "absent.yaml", {}, tool_names=TOOLS)


def test_shipped_sample_is_valid() -> None:
    sample = Path(__file__).parents[3] / "examples" / "service.yaml"
    config = load_service_config_file(sample, {}, tool_names=TOOLS)
    assert set(config.data["credentials"]) == {"qor", "zygos"}
