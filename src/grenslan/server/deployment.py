"""Build the running service from its validated configuration, and reload access policy live.

Startup builds credentials, issuers, ingress policy, the exposure profile and
the security log from a :class:`ServiceConfig`. ``SIGHUP`` re-reads the
service file and its key-set files through :class:`AccessReloader`: if
everything validates, consumer credentials and OAuth issuers are replaced and
only work whose grant was removed or changed is cancelled; if anything fails,
nothing changes. Every other setting needs a restart, and a change to one is
logged rather than applied.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Collection, Mapping
from pathlib import Path
from typing import Any

from grenslan.config.loader import DEFAULT_MAX_CONFIG_BYTES, ConfigLoadError, LoadProblem
from grenslan.config.service_config import ServiceConfig, load_service_config_file
from grenslan.server.app_support import IngressSettings
from grenslan.server.auth import ApplicationCredential, CredentialStore
from grenslan.server.authenticator import Authenticator
from grenslan.server.oauth import AccessTokenValidator, TokenPolicy, TrustedIssuer
from grenslan.server.security_events import SecurityLog
from grenslan.service.dispatch import ArgumentLimits
from grenslan.service.profiles import profile_tools

_LOGGER = logging.getLogger("grenslan.config")
_RELOADABLE = ("credentials", "oauth")


def _profile(config: ServiceConfig, name: str) -> frozenset[str]:
    custom = config.data["tools"].get("custom_profiles", {})
    if name in custom:
        return profile_tools("custom", custom=custom[name])
    return profile_tools(name)


def exposure_profile(config: ServiceConfig) -> frozenset[str]:
    """The tools the service exposes by default."""
    return _profile(config, config.data["tools"]["profile"])


def build_credentials(config: ServiceConfig) -> list[ApplicationCredential]:
    """Consumer credentials; a credential's profile narrows its permissions and never adds to them."""
    credentials = []
    for credential_id, entry in config.data["credentials"].items():
        permissions = frozenset(entry["permissions"])
        if "profile" in entry:
            permissions &= _profile(config, entry["profile"])
        identity = entry.get("identity", {})
        credentials.append(
            ApplicationCredential(
                credential_id=credential_id,
                application_id=entry["application_id"],
                token_sha256=bytes.fromhex(entry["token_sha256"]),
                permissions=permissions,
                delegation=entry["delegation"],
                user_id=identity.get("user_id"),
                agent_id=identity.get("agent_id"),
                instance_id=identity.get("instance_id"),
                profile=entry.get("profile"),
            )
        )
    return credentials


def _reject_constant(_name: str) -> Any:
    raise ValueError("non-finite number")


def _unique_members(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    members = dict(pairs)
    if len(members) != len(pairs):
        raise ValueError("duplicate member")
    return members


def _read_key_set(path: Path) -> list[Any]:
    """The ``keys`` of a JSON Web Key Set file. Errors never quote the file's content."""
    try:
        with path.open("rb") as handle:
            raw = handle.read(DEFAULT_MAX_CONFIG_BYTES + 1)
    except OSError:
        raise ValueError("key set file cannot be read") from None
    if len(raw) > DEFAULT_MAX_CONFIG_BYTES:
        raise ValueError("key set file exceeds the size limit")
    try:
        document = json.loads(raw, object_pairs_hook=_unique_members, parse_constant=_reject_constant)
    except ValueError:
        document = None
    keys = document.get("keys") if isinstance(document, dict) else None
    if not isinstance(keys, list):
        raise ValueError('not a JSON Web Key Set: expected one object with a "keys" array')
    return keys


def load_issuers(config: ServiceConfig) -> list[TrustedIssuer]:
    """Trusted issuers with keys read from their key-set files; raises :class:`ConfigLoadError`."""
    oauth = config.data.get("oauth")
    if oauth is None:
        return []
    issuers: list[TrustedIssuer] = []
    problems: list[LoadProblem] = []
    for issuer_id, entry in oauth["issuers"].items():
        location = f"/oauth/issuers/{issuer_id}/jwks_file"
        try:
            keys = _read_key_set(Path(entry["jwks_file"]))
            issuers.append(
                TrustedIssuer(
                    issuer=entry["issuer"],
                    application_id=entry["application_id"],
                    keys=tuple(keys),
                    scope_permissions={scope: frozenset(tools) for scope, tools in entry["scopes"].items()},
                    user_claim=entry["user_claim"],
                )
            )
        except ValueError as exc:
            # TrustedIssuer's messages describe the problem without key material.
            problems.append(LoadProblem(location, str(exc)))
    if problems:
        raise ConfigLoadError(problems)
    return issuers


def build_authenticator(config: ServiceConfig, issuers: list[TrustedIssuer]) -> Authenticator:
    tokens = None
    oauth = config.data.get("oauth")
    if oauth is not None:
        policy = TokenPolicy(
            resource=oauth["resource"],
            leeway_seconds=oauth["leeway_seconds"],
            max_lifetime_seconds=oauth["max_token_lifetime_seconds"],
        )
        tokens = AccessTokenValidator(policy, issuers)
    return Authenticator(CredentialStore(build_credentials(config)), tokens)


def ingress_settings(config: ServiceConfig) -> IngressSettings:
    ingress = config.data["ingress"]
    return IngressSettings(
        allowed_hosts=frozenset(ingress["allowed_hosts"]),
        allowed_origins=frozenset(ingress["allowed_origins"]),
        max_request_bytes=ingress["max_request_bytes"],
    )


def argument_limits(config: ServiceConfig) -> ArgumentLimits:
    limits = config.data["ingress"]["argument_limits"]
    return ArgumentLimits(
        max_string_chars=limits["max_string_chars"],
        max_array_items=limits["max_array_items"],
        max_depth=limits["max_depth"],
    )


def security_log(config: ServiceConfig) -> SecurityLog:
    events = config.data["security_events"]
    return SecurityLog(max_events_per_window=events["max_events_per_window"], window_seconds=events["window_seconds"])


def restart_required(running: ServiceConfig, candidate: ServiceConfig) -> list[str]:
    """Changed settings that only a restart applies, as dotted paths."""
    changed = [
        section
        for section in sorted(set(running.data) | set(candidate.data))
        if section not in _RELOADABLE and running.data.get(section) != candidate.data.get(section)
    ]
    before, after = running.data.get("oauth"), candidate.data.get("oauth")
    if before is None and after is not None:
        changed.append("oauth")
    elif before is not None and after is not None:
        changed += [
            f"oauth.{name}"
            for name in ("resource", "leeway_seconds", "max_token_lifetime_seconds")
            if before[name] != after[name]
        ]
    return changed


def log_problems(problems: list[LoadProblem], what: str) -> None:
    for problem in problems:
        _LOGGER.warning("%s: %s: %s", what, problem.location, problem.message)


class AccessReloader:
    """Re-reads the service file and replaces credentials and issuers when all of it is valid.

    Runs on the service event loop, because revocation callbacks cancel request work.
    """

    def __init__(
        self,
        path: Path,
        environ: Mapping[str, str],
        tool_names: Collection[str],
        running: ServiceConfig,
        authenticator: Authenticator,
    ) -> None:
        self._path = path
        self._environ = dict(environ)
        self._tool_names = tool_names
        self._running = running
        self._authenticator = authenticator

    def reload(self) -> bool:
        try:
            candidate = load_service_config_file(self._path, self._environ, tool_names=self._tool_names)
            issuers = load_issuers(candidate)
            credentials = build_credentials(candidate)
        except ConfigLoadError as exc:
            log_problems(exc.problems, "reload rejected; nothing changed")
            return False
        for setting in restart_required(self._running, candidate):
            _LOGGER.warning("reload: %s changed; it takes effect only after a restart", setting)
        self._authenticator.credentials.replace(credentials)
        tokens = self._authenticator.tokens
        if tokens is not None:
            # Without an oauth section there are no issuers, so removing it revokes every token now;
            # the metadata document is withdrawn at restart.
            tokens.replace(issuers)
        _LOGGER.info("reload: credentials and issuers replaced")
        return True
