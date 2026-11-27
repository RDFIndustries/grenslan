"""Operator-issued application credentials and trusted context (TC-003, TC-048).

Each protected HTTP request carries ``Authorization: Bearer <credential>``.
Only SHA-256 digests of credentials are held. A credential binds one
application namespace, the tools it may use and, when the operator allows
delegation, the right to assert user, agent and instance identities through
the ``Grenslan-User-Id``, ``Grenslan-Agent-Id`` and ``Grenslan-Instance-Id``
headers. Without delegation, the identities configured on the credential
apply.

Authentication failures carry one fixed message so a caller cannot tell a
malformed header from an unknown or revoked credential.
"""

from __future__ import annotations

import hashlib
import hmac
import re
import threading
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from grenslan.service.context import InvocationContext

MAX_AUTHORIZATION_BYTES = 4096
_BEARER = re.compile(rb"^[Bb][Ee][Aa][Rr][Ee][Rr] ([A-Za-z0-9\-._~+/]+=*)$")
IDENTITY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:@+-]{0,127}$")
_DELEGATION_HEADERS = {
    "grenslan-user-id": "user_id",
    "grenslan-agent-id": "agent_id",
    "grenslan-instance-id": "instance_id",
}


def token_digest(token: str) -> bytes:
    """SHA-256 digest under which a credential is stored and looked up."""
    return hashlib.sha256(token.encode("ascii")).digest()


def bearer_token(authorization: Sequence[bytes]) -> bytes:
    """The token from exactly one well-formed ``Authorization: Bearer`` header value."""
    if not authorization:
        raise AuthenticationFailed("missing")
    if len(authorization) != 1 or len(authorization[0]) > MAX_AUTHORIZATION_BYTES:
        raise AuthenticationFailed("malformed")
    match = _BEARER.match(authorization[0])
    if match is None:
        raise AuthenticationFailed("malformed")
    return match.group(1)


class ContextGrant(Protocol):
    """What an authenticated principal contributes to the trusted context."""

    @property
    def application_id(self) -> str: ...
    @property
    def permissions(self) -> frozenset[str]: ...
    @property
    def delegation(self) -> bool: ...
    @property
    def user_id(self) -> str | None: ...
    @property
    def agent_id(self) -> str | None: ...
    @property
    def instance_id(self) -> str | None: ...


class AuthenticationFailed(Exception):
    """Authentication failed. The message is fixed; ``reason`` is for operator diagnostics only."""

    def __init__(self, reason: str) -> None:
        super().__init__("authentication failed")
        self.reason = reason


class ContextRejected(Exception):
    """Delegation headers are malformed (400) or not authorized for the credential (403)."""

    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True, slots=True)
class ApplicationCredential:
    credential_id: str
    application_id: str
    token_sha256: bytes = field(repr=False)
    permissions: frozenset[str]
    delegation: bool
    user_id: str | None
    agent_id: str | None
    instance_id: str | None

    def __post_init__(self) -> None:
        if len(self.token_sha256) != hashlib.sha256().digest_size:
            raise ValueError("token_sha256 must be a SHA-256 digest")
        if not self.credential_id or not self.application_id:
            raise ValueError("credential_id and application_id are required")


class CredentialStore:
    """Current credentials, replaceable as a whole for rotation and revocation."""

    def __init__(self, credentials: Iterable[ApplicationCredential]) -> None:
        self._lock = threading.Lock()
        self._by_digest: dict[bytes, ApplicationCredential] = {}
        self._watchers: dict[int, tuple[ApplicationCredential, Callable[[], None]]] = {}
        self._next_watch = 0
        self.replace(credentials)

    def replace(self, credentials: Iterable[ApplicationCredential]) -> None:
        by_digest: dict[bytes, ApplicationCredential] = {}
        identifiers: set[str] = set()
        for credential in credentials:
            if credential.token_sha256 in by_digest or credential.credential_id in identifiers:
                raise ValueError(f"duplicate credential {credential.credential_id!r}")
            by_digest[credential.token_sha256] = credential
            identifiers.add(credential.credential_id)
        with self._lock:
            self._by_digest = by_digest
            revoked = [
                (key, callback)
                for key, (watched, callback) in self._watchers.items()
                if by_digest.get(watched.token_sha256) != watched
            ]
            for key, _ in revoked:
                del self._watchers[key]
        for _, callback in revoked:
            callback()

    def watch(self, credential: ApplicationCredential, callback: Callable[[], None]) -> Callable[[], None]:
        """Call ``callback`` once if this credential record is revoked or changed; returns an unwatch function.

        Callbacks run in the thread that calls :meth:`replace`. Replacement is
        expected on the service event loop, so a callback may cancel request work.
        """
        with self._lock:
            stale = self._by_digest.get(credential.token_sha256) != credential
            if not stale:
                key = self._next_watch
                self._next_watch += 1
                self._watchers[key] = (credential, callback)
        if stale:
            callback()
            return lambda: None

        def unwatch() -> None:
            with self._lock:
                self._watchers.pop(key, None)

        return unwatch

    def authenticate(self, authorization: Sequence[bytes]) -> ApplicationCredential:
        """Resolve the single ``Authorization`` header value to a current credential."""
        credential = self.lookup(bearer_token(authorization))
        if credential is None:
            raise AuthenticationFailed("unknown_credential")
        return credential

    def lookup(self, token: bytes) -> ApplicationCredential | None:
        """The current credential for a bearer token, or ``None``."""
        digest = hashlib.sha256(token).digest()
        with self._lock:
            credential = self._by_digest.get(digest)
        if credential is None or not hmac.compare_digest(credential.token_sha256, digest):
            return None
        return credential

    def is_current(self, credential: ApplicationCredential) -> bool:
        """True while this exact credential record is still configured."""
        with self._lock:
            return self._by_digest.get(credential.token_sha256) == credential


def establish_context(credential: ContextGrant, headers: Mapping[str, Sequence[bytes]]) -> InvocationContext:
    """Build the trusted context from a principal and lowercase-named request headers."""
    identities: dict[str, str | None] = {
        "user_id": credential.user_id,
        "agent_id": credential.agent_id,
        "instance_id": credential.instance_id,
    }
    for name, values in headers.items():
        if not name.startswith("grenslan-"):
            continue
        target = _DELEGATION_HEADERS.get(name)
        if target is None:
            raise ContextRejected(400, "unrecognized Grenslan context header")
        if not credential.delegation:
            raise ContextRejected(403, "the credential is not authorized to delegate identities")
        if len(values) != 1:
            raise ContextRejected(400, "context headers must appear exactly once")
        try:
            value = values[0].decode("ascii")
        except UnicodeDecodeError:
            raise ContextRejected(400, "invalid context header value") from None
        if not IDENTITY_PATTERN.match(value):
            raise ContextRejected(400, "invalid context header value")
        identities[target] = value
    return InvocationContext(
        application_id=credential.application_id,
        permissions=credential.permissions,
        **identities,
    )
