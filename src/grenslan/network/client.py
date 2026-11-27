"""The outbound HTTP client providers use for every request to an external destination.

Requests are checked against the provider's network scope before sending and
again where each connection is opened (``backend.PolicyBackend``). Redirects
are followed here, not by the transport, so each hop is checked. A credential
is attached only while the request stays at the credential's origin; once a
redirect leaves that origin it is never sent again in the same request. Proxy
environment variables are not consulted. TLS verification cannot be turned
off. The response body, the number of redirects and the total time are
bounded.
"""

from __future__ import annotations

import ssl
from collections.abc import Sequence
from dataclasses import dataclass
from types import TracebackType
from urllib.parse import urljoin, urlsplit

import anyio
import httpcore2

from grenslan.network.backend import PolicyBackend, Resolver, system_resolver
from grenslan.network.errors import DestinationDenied, OutboundError
from grenslan.network.policy import NetworkPolicy, parse_origin

__all__ = ["Credential", "OutboundClient", "OutboundError", "OutboundResponse", "outbound_ssl_context"]

REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
# Header names that carry credentials. They may only be supplied as a Credential.
CREDENTIAL_HEADERS = frozenset({"authorization", "proxy-authorization", "cookie"})
BODY_HEADERS = frozenset({"content-type", "content-length", "content-encoding", "transfer-encoding"})
DEFAULT_MAX_RESPONSE_BYTES = 16 * 1024 * 1024


def outbound_ssl_context(ca_file: str | None = None) -> ssl.SSLContext:
    """A verifying client context requiring TLS 1.2 or later.

    With ``ca_file`` it trusts only that approved private CA bundle; otherwise
    the system trust store.
    """
    context = ssl.create_default_context(cafile=ca_file)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    return context


class Credential:
    """Headers that authenticate to one origin, such as ``https://api.example.org``."""

    __slots__ = ("headers", "origin")

    def __init__(self, origin: str, headers: Sequence[tuple[str, str]]) -> None:
        parts = urlsplit(origin)
        if parts.path not in ("", "/") or parts.query or parts.fragment:
            raise ValueError("a credential origin must be an origin: scheme, host and optional port only")
        try:
            self.origin = parse_origin(origin)
        except DestinationDenied as error:
            raise ValueError(f"invalid credential origin: {error}") from error
        self.headers = tuple(headers)

    def __repr__(self) -> str:
        return f"Credential(origin={self.origin!r}, headers=<{len(self.headers)} redacted>)"


@dataclass(frozen=True, slots=True)
class OutboundResponse:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes
    url: str
    redirects: tuple[str, ...]

    def header(self, name: str) -> str | None:
        name = name.lower()
        return next((value for key, value in self.headers if key.lower() == name), None)


def _classify(error: BaseException) -> OutboundError:
    chain: list[BaseException] = []
    current: BaseException | None = error
    while current is not None and current not in chain:
        chain.append(current)
        current = current.__cause__ or current.__context__
    for candidate in chain:
        if isinstance(candidate, OutboundError):
            return candidate
    if any(isinstance(candidate, ssl.SSLError) for candidate in chain):
        return OutboundError("tls", "TLS verification or negotiation failed")
    if isinstance(error, httpcore2.TimeoutException):
        return OutboundError("timeout", "the destination did not respond in time")
    if isinstance(error, httpcore2.ConnectError):
        return OutboundError("connect", "the connection could not be established")
    return OutboundError("protocol", "the destination's response could not be read")


class OutboundClient:
    def __init__(
        self,
        policy: NetworkPolicy,
        *,
        ssl_context: ssl.SSLContext | None = None,
        resolver: Resolver = system_resolver,
        max_redirects: int = 5,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_connections: int = 10,
    ) -> None:
        context = outbound_ssl_context() if ssl_context is None else ssl_context
        if context.verify_mode != ssl.CERT_REQUIRED or not context.check_hostname:
            raise ValueError("outbound TLS verification must be enabled")
        if context.minimum_version not in (ssl.TLSVersion.TLSv1_2, ssl.TLSVersion.TLSv1_3):
            raise ValueError("outbound TLS must require version 1.2 or later")
        self._policy = policy
        self._max_redirects = max_redirects
        self._max_response_bytes = max_response_bytes
        self._pool = httpcore2.AsyncConnectionPool(
            ssl_context=context,
            network_backend=PolicyBackend(policy, resolver),
            max_connections=max_connections,
            http1=True,
            http2=False,
            retries=0,
        )

    async def __aenter__(self) -> OutboundClient:
        return self

    async def __aexit__(
        self, kind: type[BaseException] | None, error: BaseException | None, traceback: TracebackType | None
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._pool.aclose()

    async def request(
        self,
        method: str,
        url: str,
        *,
        timeout: float,
        headers: Sequence[tuple[str, str]] = (),
        body: bytes | None = None,
        credential: Credential | None = None,
    ) -> OutboundResponse:
        """Send a request, following permitted redirects, within ``timeout`` seconds in total."""
        if any(name.lower() in CREDENTIAL_HEADERS for name, _ in headers):
            raise ValueError("credential headers must be supplied as a Credential")
        try:
            with anyio.fail_after(timeout):
                return await self._follow(method.upper(), url, list(headers), body, credential)
        except TimeoutError as error:
            raise OutboundError("timeout", "the request did not complete in time") from error

    async def _follow(
        self,
        method: str,
        url: str,
        headers: list[tuple[str, str]],
        body: bytes | None,
        credential: Credential | None,
    ) -> OutboundResponse:
        visited: list[str] = []
        at_credential_origin = credential is not None
        while True:
            target = self._policy.check_url(url)
            if credential is not None and target.origin != credential.origin:
                at_credential_origin = False
            sent = list(headers)
            if at_credential_origin and credential is not None:
                sent.extend(credential.headers)
            status, response_headers, content = await self._send(method, url, sent, body)
            location = next((value for key, value in response_headers if key.lower() == "location"), None)
            if status not in REDIRECT_STATUSES or location is None:
                return OutboundResponse(status, tuple(response_headers), content, url, tuple(visited))
            if len(visited) >= self._max_redirects:
                raise OutboundError("redirect_limit", f"more than {self._max_redirects} redirects")
            visited.append(url)
            url = urljoin(url, location)
            if status == 303 or (status in (301, 302) and method == "POST"):
                method = "GET" if method != "HEAD" else method
                body = None
                headers = [(name, value) for name, value in headers if name.lower() not in BODY_HEADERS]

    async def _send(
        self, method: str, url: str, headers: list[tuple[str, str]], body: bytes | None
    ) -> tuple[int, list[tuple[str, str]], bytes]:
        encoded = [(name.encode("latin-1"), value.encode("latin-1")) for name, value in headers]
        try:
            async with self._pool.stream(method, url, headers=encoded, content=body) as response:
                chunks: list[bytes] = []
                size = 0
                async for chunk in response.aiter_stream():
                    size += len(chunk)
                    if size > self._max_response_bytes:
                        raise OutboundError("too_large", f"the response exceeds {self._max_response_bytes} bytes")
                    chunks.append(chunk)
                return (
                    response.status,
                    [(key.decode("latin-1"), value.decode("latin-1")) for key, value in response.headers],
                    b"".join(chunks),
                )
        except OutboundError:
            raise
        except (httpcore2.NetworkError, httpcore2.ProtocolError, httpcore2.TimeoutException, ssl.SSLError) as error:
            raise _classify(error) from error
