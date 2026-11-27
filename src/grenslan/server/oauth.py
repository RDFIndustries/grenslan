"""MCP-compatible OAuth access tokens, validated locally as signed JWTs (TC-048).

The operator configures the token audience (Grenslan's resource URI), the
trusted authorization servers and each server's public signing keys. A token
is accepted only if every check passes:

- its signature verifies with a configured key of the issuer named in the
  token, using that key's algorithm (RS256 or ES256 only, so unsigned and
  HMAC tokens are refused);
- its header carries no ``jku``, ``x5u``, ``jwk``, ``x5c``, ``crit`` or
  ``b64`` parameter, so a token can never nominate its own key;
- ``iss``, ``aud``, ``exp`` and ``iat`` are present, the audience includes the
  resource URI (RFC 8707), and the token is current within the configured
  clock leeway and no longer-lived than the configured maximum.

An issuer maps to one application namespace. Token scopes map to tool
permissions through operator configuration, and an optional claim supplies the
user identity. Tokens never carry delegation rights, so ``Grenslan-*``
identity headers are refused for them.

Replacing the issuer configuration revokes in-flight work for tokens whose
issuer settings or signing key changed or were removed. Signing keys are given
as configuration; Grenslan does not fetch key sets at runtime.

The protected resource metadata document (RFC 9728) is derived from the same
configuration.
"""

from __future__ import annotations

import json
import re
import threading
import time
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any
from urllib.parse import urlsplit

import jwt
from jwt.exceptions import PyJWTError

from grenslan.server.auth import IDENTITY_PATTERN

MAX_TOKEN_BYTES = 4096
_TOKEN_SHAPE = re.compile(r"^[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+$")
_ALGORITHM_BY_KEY_TYPE = {"RSA": "RS256", "EC": "ES256"}
_MIN_RSA_BITS = 2048
_PRIVATE_KEY_MEMBERS = frozenset({"d", "p", "q", "dp", "dq", "qi", "oth", "k"})
_FORBIDDEN_HEADERS = frozenset({"jku", "x5u", "jwk", "x5c", "crit", "b64"})
_ACCEPTED_TYPES = frozenset({"jwt", "at+jwt", "application/at+jwt"})
_REQUIRED_CLAIMS = ["exp", "iat", "iss", "aud"]
_WELL_KNOWN = "/.well-known/oauth-protected-resource"


class InvalidAccessToken(Exception):
    """Any token rejection. The message never says which check failed."""

    def __init__(self) -> None:
        super().__init__("invalid access token")


def _require_https_url(value: str, what: str) -> None:
    parts = urlsplit(value)
    if parts.scheme != "https" or not parts.netloc or "#" in value or "?" in value:
        raise ValueError(f"{what} must be an https URL without fragment or query")


@dataclass(frozen=True, slots=True)
class _VerificationKey:
    kid: str | None
    algorithm: str
    key: Any
    fingerprint: str


def _verification_key(jwk: Mapping[str, Any]) -> tuple[str | None, str, Any]:
    if not isinstance(jwk, Mapping):
        raise ValueError("each signing key must be a JWK object")
    if _PRIVATE_KEY_MEMBERS & jwk.keys():
        raise ValueError("signing keys must be public keys; private or symmetric key material is not accepted")
    algorithm = _ALGORITHM_BY_KEY_TYPE.get(jwk.get("kty"))  # type: ignore[arg-type]
    if algorithm is None:
        raise ValueError("signing keys must have kty RSA or EC")
    if jwk.get("alg", algorithm) != algorithm:
        raise ValueError(f"unsupported signing algorithm for a {jwk['kty']} key; only {algorithm} is accepted")
    if jwk.get("use", "sig") != "sig":
        raise ValueError("signing key use must be sig")
    if jwk["kty"] == "EC" and jwk.get("crv") != "P-256":
        raise ValueError("EC signing keys must use the P-256 curve")
    kid = jwk.get("kid")
    if kid is not None and (not isinstance(kid, str) or not kid):
        raise ValueError("kid must be a non-empty string")
    try:
        parsed = jwt.PyJWK(dict(jwk), algorithm=algorithm)
    except PyJWTError:
        raise ValueError("invalid signing key") from None
    if jwk["kty"] == "RSA" and parsed.key.key_size < _MIN_RSA_BITS:
        raise ValueError(f"RSA signing keys must be at least {_MIN_RSA_BITS} bits")
    return kid, algorithm, parsed.key


@dataclass(frozen=True, slots=True)
class TrustedIssuer:
    """One trusted authorization server.

    ``issuer`` must equal the ``iss`` claim exactly. ``scope_permissions`` maps
    each scope to the tool permissions it grants. ``user_claim`` names the claim
    that supplies the user identity, or is ``None`` for no user identity.
    """

    issuer: str
    application_id: str
    keys: tuple[Mapping[str, Any], ...]
    scope_permissions: Mapping[str, frozenset[str]]
    user_claim: str | None
    _verification_keys: dict[str | None, _VerificationKey] = field(
        init=False, repr=False, compare=False, default_factory=dict
    )

    def __post_init__(self) -> None:
        # Frozen copies, so later changes by the caller cannot alter an accepted configuration.
        if any(not isinstance(jwk, Mapping) for jwk in self.keys):
            raise ValueError("each signing key must be a JWK object")
        object.__setattr__(self, "keys", tuple(MappingProxyType(dict(jwk)) for jwk in self.keys))
        object.__setattr__(
            self,
            "scope_permissions",
            MappingProxyType({scope: frozenset(tools) for scope, tools in self.scope_permissions.items()}),
        )
        _require_https_url(self.issuer, "issuer")
        if not self.application_id:
            raise ValueError("application_id is required")
        if not self.keys:
            raise ValueError("at least one signing key is required")
        grant = json.dumps(
            [
                self.issuer,
                self.application_id,
                {scope: sorted(tools) for scope, tools in self.scope_permissions.items()},
                self.user_claim,
            ],
            sort_keys=True,
        )
        compiled: dict[str | None, _VerificationKey] = {}
        for jwk in self.keys:
            kid, algorithm, key = _verification_key(jwk)
            if len(self.keys) > 1 and kid is None:
                raise ValueError("every signing key needs a kid when an issuer has several keys")
            if kid in compiled:
                raise ValueError(f"duplicate kid {kid!r}")
            fingerprint = grant + json.dumps(dict(jwk), sort_keys=True)
            compiled[kid] = _VerificationKey(kid, algorithm, key, fingerprint)
        self._verification_keys.update(compiled)

    def key_for(self, kid: object) -> _VerificationKey | None:
        if kid is None and len(self._verification_keys) == 1:
            return next(iter(self._verification_keys.values()))
        if not isinstance(kid, str):
            return None
        return self._verification_keys.get(kid)


@dataclass(frozen=True, slots=True)
class TokenPolicy:
    """``resource`` is Grenslan's resource URI, which every token's audience must include."""

    resource: str
    leeway_seconds: int
    max_lifetime_seconds: int

    def __post_init__(self) -> None:
        _require_https_url(self.resource, "resource")
        if self.leeway_seconds < 0:
            raise ValueError("leeway_seconds must not be negative")
        if self.max_lifetime_seconds < 1:
            raise ValueError("max_lifetime_seconds must be positive")


@dataclass(frozen=True, slots=True)
class TokenPrincipal:
    """The trusted grant established by a valid access token."""

    application_id: str
    permissions: frozenset[str]
    user_id: str | None
    issuer: str
    key_id: str | None
    expires_at: float
    trust: str = field(repr=False)
    delegation: bool = False
    agent_id: str | None = None
    instance_id: str | None = None


class AccessTokenValidator:
    """Validates access tokens against the current trusted issuers."""

    def __init__(self, policy: TokenPolicy, issuers: Iterable[TrustedIssuer]) -> None:
        self.policy = policy
        self._lock = threading.Lock()
        self._issuers: dict[str, TrustedIssuer] = {}
        self._trusted: frozenset[str] = frozenset()
        self._watchers: dict[int, tuple[TokenPrincipal, Callable[[], None]]] = {}
        self._next_watch = 0
        self.replace(issuers)

    @property
    def metadata_path(self) -> str:
        return _WELL_KNOWN + urlsplit(self.policy.resource).path.rstrip("/")

    @property
    def metadata_url(self) -> str:
        parts = urlsplit(self.policy.resource)
        return f"https://{parts.netloc}{self.metadata_path}"

    def metadata(self) -> dict[str, Any]:
        """The RFC 9728 protected resource metadata document."""
        with self._lock:
            issuers = list(self._issuers.values())
        scopes = sorted({scope for issuer in issuers for scope in issuer.scope_permissions})
        return {
            "resource": self.policy.resource,
            "authorization_servers": [issuer.issuer for issuer in issuers],
            "scopes_supported": scopes,
            "bearer_methods_supported": ["header"],
        }

    def replace(self, issuers: Iterable[TrustedIssuer]) -> None:
        by_issuer: dict[str, TrustedIssuer] = {}
        for issuer in issuers:
            if issuer.issuer in by_issuer:
                raise ValueError(f"duplicate issuer {issuer.issuer!r}")
            by_issuer[issuer.issuer] = issuer
        trusted = frozenset(
            key.fingerprint for issuer in by_issuer.values() for key in issuer._verification_keys.values()
        )
        with self._lock:
            self._issuers = by_issuer
            self._trusted = trusted
            revoked = [key for key, (principal, _) in self._watchers.items() if principal.trust not in trusted]
            callbacks = [self._watchers.pop(key)[1] for key in revoked]
        for callback in callbacks:
            callback()

    def watch(self, principal: TokenPrincipal, callback: Callable[[], None]) -> Callable[[], None]:
        """Call ``callback`` once if the issuer settings or key that admitted ``principal`` change."""
        with self._lock:
            stale = principal.trust not in self._trusted
            if not stale:
                key = self._next_watch
                self._next_watch += 1
                self._watchers[key] = (principal, callback)
        if stale:
            callback()
            return lambda: None

        def unwatch() -> None:
            with self._lock:
                self._watchers.pop(key, None)

        return unwatch

    def validate(self, token: str, *, now: float | None = None) -> TokenPrincipal:
        try:
            return self._validate(token, now)
        except (PyJWTError, ValueError, TypeError, KeyError):
            raise InvalidAccessToken from None

    def _validate(self, token: str, now: float | None) -> TokenPrincipal:
        if len(token) > MAX_TOKEN_BYTES or not _TOKEN_SHAPE.match(token):
            raise InvalidAccessToken
        header = jwt.get_unverified_header(token)
        algorithm = header.get("alg")
        if algorithm not in _ALGORITHM_BY_KEY_TYPE.values() or _FORBIDDEN_HEADERS & header.keys():
            raise InvalidAccessToken
        token_type = header.get("typ")
        if token_type is not None and (not isinstance(token_type, str) or token_type.lower() not in _ACCEPTED_TYPES):
            raise InvalidAccessToken

        unverified = jwt.decode(token, options={"verify_signature": False})
        issuer_id = unverified.get("iss")
        with self._lock:
            issuer = self._issuers.get(issuer_id) if isinstance(issuer_id, str) else None
        if issuer is None:
            raise InvalidAccessToken
        key = issuer.key_for(header.get("kid"))
        if key is None or key.algorithm != algorithm:
            raise InvalidAccessToken

        options: dict[str, Any] = {"require": _REQUIRED_CLAIMS}
        claims = jwt.decode(
            token,
            key.key,
            algorithms=[key.algorithm],
            audience=self.policy.resource,
            issuer=issuer.issuer,
            leeway=self.policy.leeway_seconds,
            options=options,  # type: ignore[arg-type]
        )
        expires_at, issued_at = claims["exp"], claims["iat"]
        current = now if now is not None else time.time()
        maximum = self.policy.max_lifetime_seconds
        if expires_at - issued_at > maximum or expires_at - current > maximum + self.policy.leeway_seconds:
            raise InvalidAccessToken

        scope = claims.get("scope", "")
        if not isinstance(scope, str):
            raise InvalidAccessToken
        permissions = frozenset(
            tool for granted in scope.split() for tool in issuer.scope_permissions.get(granted, frozenset())
        )

        user_id = None
        if issuer.user_claim is not None:
            user_id = claims.get(issuer.user_claim)
            if not isinstance(user_id, str) or not IDENTITY_PATTERN.match(user_id):
                raise InvalidAccessToken

        return TokenPrincipal(
            application_id=issuer.application_id,
            permissions=permissions,
            user_id=user_id,
            issuer=issuer.issuer,
            key_id=key.kid,
            expires_at=float(expires_at),
            trust=key.fingerprint,
        )
