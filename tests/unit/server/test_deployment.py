"""Building the running service from its configuration, and live credential reload (SERVICE-CONFIGURATION.md)."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import pytest
from service_fixtures import (
    QOR_TOKEN,
    ZYGOS_TOKEN,
    oauth_section,
    service_data,
    write_jwks,
    write_service_file,
)

from grenslan.config.loader import ConfigLoadError
from grenslan.config.service_config import ServiceConfig, validate_service_config
from grenslan.contracts.registry import ToolRegistry
from grenslan.server.auth import AuthenticationFailed, token_digest
from grenslan.server.deployment import (
    AccessReloader,
    build_authenticator,
    build_credentials,
    exposure_profile,
    ingress_settings,
    load_issuers,
)
from grenslan.service.profiles import ALWAYS_AVAILABLE, PROFILES

from jwt_fixtures import SigningKey, claims, ec_key, rsa_key

TOOLS = frozenset(ToolRegistry.load().tool_names)


def configured(data: dict[str, Any]) -> ServiceConfig:
    return validate_service_config(data, tool_names=TOOLS)


def bearer(token: str) -> list[bytes]:
    return [b"Bearer " + token.encode("ascii")]


def test_credentials_carry_namespace_digest_identity_and_delegation() -> None:
    by_id = {credential.credential_id: credential for credential in build_credentials(configured(service_data()))}
    assert by_id["qor"].application_id == "qor"
    assert by_id["qor"].token_sha256 == token_digest(QOR_TOKEN)
    assert by_id["qor"].delegation is True
    assert by_id["zygos"].user_id == "zygos-owner"
    assert by_id["zygos"].agent_id is None


def test_credential_profile_narrows_but_never_grants() -> None:
    data = service_data()
    data["tools"]["custom_profiles"]["search_only"] = ["web_search", "web_open"]
    by_id = {credential.credential_id: credential for credential in build_credentials(configured(data))}
    # web_open is in the profile but not permitted; image_search is permitted but not in the profile.
    assert by_id["zygos"].permissions == frozenset({"web_search", "capabilities_get"})
    assert by_id["qor"].permissions == frozenset({"web_search", "image_search", "capabilities_get"})


def test_exposure_profile_resolves_built_in_and_custom_profiles() -> None:
    assert exposure_profile(configured(service_data())) == PROFILES["full"]
    data = service_data()
    data["tools"]["profile"] = "search_only"
    assert exposure_profile(configured(data)) == frozenset({"web_search", "image_search"}) | ALWAYS_AVAILABLE


def test_ingress_settings_use_normalized_hosts() -> None:
    data = service_data()
    data["ingress"]["allowed_hosts"] = ["Grenslan"]
    data["ingress"]["allowed_origins"] = ["https://Zygos.lan"]
    settings = ingress_settings(configured(data))
    assert settings.allowed_hosts == frozenset({"grenslan"})
    assert settings.allowed_origins == frozenset({"https://zygos.lan"})
    assert settings.max_request_bytes == 65536


def test_issuers_load_from_key_set_files_and_validate_tokens(tmp_path: Path) -> None:
    key = rsa_key()
    config = configured(service_data(oauth=oauth_section(write_jwks(tmp_path / "jwks.json", key, ec_key()))))
    authenticator = build_authenticator(config, load_issuers(config))
    principal = authenticator.authenticate(bearer(key.sign(claims())))
    assert principal.application_id == "qor"
    assert principal.permissions == frozenset({"web_search"})
    assert principal.user_id == "user-1"


def test_without_oauth_tokens_are_not_accepted() -> None:
    config = configured(service_data())
    assert load_issuers(config) == []
    authenticator = build_authenticator(config, [])
    assert authenticator.tokens is None
    assert authenticator.authenticate(bearer(QOR_TOKEN)).application_id == "qor"


@pytest.mark.parametrize(
    ("content", "message"),
    [
        pytest.param(None, "cannot be read", id="missing"),
        pytest.param("not json", "JSON Web Key Set", id="not-json"),
        pytest.param('{"keys": [], "keys": []}', "JSON Web Key Set", id="duplicate-member"),
        pytest.param('{"keys": NaN}', "JSON Web Key Set", id="non-finite"),
        pytest.param('["keys"]', "JSON Web Key Set", id="not-object"),
        pytest.param('{"keys": []}', "signing key", id="empty"),
    ],
)
def test_key_set_problems_are_located(tmp_path: Path, content: str | None, message: str) -> None:
    path = tmp_path / "jwks.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    config = configured(service_data(oauth=oauth_section(path)))
    with pytest.raises(ConfigLoadError) as excinfo:
        load_issuers(config)
    [problem] = excinfo.value.problems
    assert problem.location == "/oauth/issuers/idp/jwks_file"
    assert message in problem.message


def test_private_key_material_is_refused_without_echoing_it(tmp_path: Path) -> None:
    key = rsa_key()
    from jwt.algorithms import RSAAlgorithm

    private = RSAAlgorithm.to_jwk(key.private_key, as_dict=True)
    path = tmp_path / "jwks.json"
    path.write_text(json.dumps({"keys": [private]}), encoding="utf-8")
    with pytest.raises(ConfigLoadError) as excinfo:
        load_issuers(configured(service_data(oauth=oauth_section(path))))
    assert "public" in str(excinfo.value)
    assert private["d"] not in str(excinfo.value)


# Live reload (D3)


class Reload:
    def __init__(self, tmp_path: Path, data: dict[str, Any]) -> None:
        self.path = write_service_file(tmp_path / "service.yaml", data)
        self.config = configured(data)
        self.authenticator = build_authenticator(self.config, load_issuers(self.config))
        self.reloader = AccessReloader(self.path, {}, TOOLS, self.config, self.authenticator)

    def rewrite(self, data: dict[str, Any]) -> bool:
        write_service_file(self.path, data)
        return self.reloader.reload()

    def accepts(self, token: str) -> bool:
        try:
            self.authenticator.authenticate(bearer(token))
        except AuthenticationFailed:
            return False
        return True


def test_reload_revokes_only_the_removed_credential(tmp_path: Path) -> None:
    reload = Reload(tmp_path, service_data())
    qor = reload.authenticator.authenticate(bearer(QOR_TOKEN))
    zygos = reload.authenticator.authenticate(bearer(ZYGOS_TOKEN))
    revoked: list[str] = []
    reload.authenticator.watch(qor, lambda: revoked.append("qor"))
    reload.authenticator.watch(zygos, lambda: revoked.append("zygos"))
    data = service_data()
    del data["credentials"]["zygos"]
    assert reload.rewrite(data)
    assert revoked == ["zygos"]
    assert reload.accepts(QOR_TOKEN)
    assert not reload.accepts(ZYGOS_TOKEN)


def test_reload_applies_a_changed_grant_as_revocation(tmp_path: Path) -> None:
    reload = Reload(tmp_path, service_data())
    qor = reload.authenticator.authenticate(bearer(QOR_TOKEN))
    revoked: list[str] = []
    reload.authenticator.watch(qor, lambda: revoked.append("qor"))
    data = service_data()
    data["credentials"]["qor"]["permissions"] = ["web_search"]
    assert reload.rewrite(data)
    assert revoked == ["qor"]
    assert reload.authenticator.authenticate(bearer(QOR_TOKEN)).permissions == frozenset({"web_search"})


def test_invalid_reload_changes_nothing_and_logs_without_values(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    reload = Reload(tmp_path, service_data())
    data = service_data()
    del data["credentials"]["zygos"]
    data["credentials"]["qor"]["permissions"] = [QOR_TOKEN.replace("-", "_")]
    with caplog.at_level(logging.WARNING, logger="grenslan.config"):
        assert not reload.rewrite(data)
    assert reload.accepts(ZYGOS_TOKEN)
    assert "/credentials/qor/permissions/0" in caplog.text
    assert QOR_TOKEN.replace("-", "_") not in caplog.text


def test_unreadable_key_set_on_reload_changes_nothing(tmp_path: Path) -> None:
    key = rsa_key()
    jwks = write_jwks(tmp_path / "jwks.json", key)
    reload = Reload(tmp_path, service_data(oauth=oauth_section(jwks)))
    jwks.write_text("{", encoding="utf-8")
    data = service_data(oauth=oauth_section(jwks))
    del data["credentials"]["zygos"]
    assert not reload.rewrite(data)
    assert reload.accepts(ZYGOS_TOKEN)
    assert reload.accepts(key.sign(claims()))


def test_reload_rotates_issuer_keys(tmp_path: Path) -> None:
    old, new = rsa_key("old"), rsa_key("new")
    jwks = write_jwks(tmp_path / "jwks.json", old)
    reload = Reload(tmp_path, service_data(oauth=oauth_section(jwks)))
    old_token = old.sign(claims())
    principal = reload.authenticator.authenticate(bearer(old_token))
    revoked: list[str] = []
    reload.authenticator.watch(principal, lambda: revoked.append("token"))
    write_jwks(jwks, new)
    assert reload.rewrite(service_data(oauth=oauth_section(jwks)))
    assert revoked == ["token"]
    assert not reload.accepts(old_token)
    assert reload.accepts(new.sign(claims()))


def test_removing_the_oauth_section_revokes_every_token_live(tmp_path: Path) -> None:
    key: SigningKey = rsa_key()
    reload = Reload(tmp_path, service_data(oauth=oauth_section(write_jwks(tmp_path / "jwks.json", key))))
    assert reload.rewrite(service_data())
    assert not reload.accepts(key.sign(claims()))
    assert reload.accepts(QOR_TOKEN)


def test_restart_only_changes_are_reported_and_not_applied(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    key = rsa_key()
    reload = Reload(tmp_path, service_data())
    data = service_data(oauth=oauth_section(write_jwks(tmp_path / "jwks.json", key)))
    data["listen"]["port"] = 9443
    del data["credentials"]["zygos"]
    with caplog.at_level(logging.WARNING, logger="grenslan.config"):
        assert reload.rewrite(data)
    assert "listen" in caplog.text
    assert "oauth" in caplog.text
    assert not reload.accepts(ZYGOS_TOKEN)
    assert not reload.accepts(key.sign(claims()))
    assert reload.authenticator.tokens is None


def test_reload_applies_environment_overrides_as_at_startup(tmp_path: Path) -> None:
    reload = Reload(tmp_path, service_data())
    reload.reloader = AccessReloader(reload.path, {"GRENSLAN_TYPO": "1"}, TOOLS, reload.config, reload.authenticator)
    data = service_data()
    del data["credentials"]["zygos"]
    assert not reload.rewrite(data)
    assert reload.accepts(ZYGOS_TOKEN)
