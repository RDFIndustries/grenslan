"""A provider's network scope, applied to URLs and to connection targets.

A scope (``network_scopes`` in the provider configuration) lists approved
``scheme://host:port`` destinations and may admit the public web, which means
any host over https on port 443. Any other port must be a listed destination.

A listed destination with ``allow_private_address`` may resolve to private,
loopback or link-local addresses; every other destination must resolve only
to public addresses. Plain http is for the local network only: it needs
``allow_outbound_http``, a listed destination with ``allow_private_address``,
and addresses that are not public. The public web never admits it. Metadata,
unspecified, multicast and broadcast addresses are never reachable.
"""

from __future__ import annotations

import ipaddress
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Literal
from urllib.parse import urlsplit

from grenslan.network.addresses import IPAddress, address_permitted, never_reachable
from grenslan.network.errors import DestinationDenied

__all__ = ["DestinationDenied", "NetworkPolicy", "Target", "normalize_host"]

DEFAULT_PORTS = {"http": 80, "https": 443}


def normalize_host(host: str) -> str:
    """Lower-case ASCII form used for every comparison; IP literals in canonical form."""
    host = host.lower().rstrip(".")
    try:
        return str(ipaddress.ip_address(host))
    except ValueError:
        pass
    try:
        return host.encode("idna").decode("ascii")
    except UnicodeError as error:
        raise DestinationDenied("the host name is invalid") from error


AddressRule = Literal["public", "any", "local"]
"""Which resolved addresses a connection may use: only public ones, public or
private, or only non-public ones (plain http on the local network)."""


@dataclass(frozen=True, slots=True)
class Target:
    scheme: str
    host: str
    port: int
    allow_private: bool

    @property
    def origin(self) -> tuple[str, str, int]:
        return (self.scheme, self.host, self.port)


def parse_origin(url: str) -> tuple[str, str, int]:
    """Scheme, normalized host and port of an absolute http(s) URL; raises ``DestinationDenied``."""
    parts = urlsplit(url)
    scheme = parts.scheme.lower()
    if scheme not in DEFAULT_PORTS:
        raise DestinationDenied(f"the scheme {scheme or '(none)'!r} is not permitted")
    if parts.username is not None or parts.password is not None:
        raise DestinationDenied("URLs carrying user information are not permitted")
    if not parts.hostname:
        raise DestinationDenied("the URL has no host")
    try:
        port = parts.port
    except ValueError as error:
        raise DestinationDenied("the URL port is invalid") from error
    if port == 0:
        raise DestinationDenied("the URL port is invalid")
    return scheme, normalize_host(parts.hostname), DEFAULT_PORTS[scheme] if port is None else port


@dataclass(frozen=True, slots=True)
class NetworkPolicy:
    destinations: frozenset[tuple[str, str, int, bool]]
    public_web: bool
    allow_outbound_http: bool

    @classmethod
    def from_scope(cls, scope: Mapping[str, Any]) -> NetworkPolicy:
        return cls(
            frozenset(
                (
                    entry["scheme"],
                    normalize_host(entry["host"]),
                    int(entry["port"]),
                    bool(entry.get("allow_private_address", False)),
                )
                for entry in scope["destinations"]
            ),
            bool(scope["public_web"]),
            bool(scope["allow_outbound_http"]),
        )

    def check_url(self, url: str) -> Target:
        """The approved target for ``url``; raises ``DestinationDenied`` before anything is sent."""
        scheme, host, port = parse_origin(url)
        if scheme == "http" and not self.allow_outbound_http:
            raise DestinationDenied("plain http is not permitted by the network scope")
        listed = [private for (s, h, p, private) in self.destinations if (s, h, p) == (scheme, host, port)]
        if scheme == "http":
            if not any(listed):
                raise DestinationDenied("plain http is permitted only to listed local network destinations")
            return Target(scheme, host, port, True)
        if listed:
            return Target(scheme, host, port, any(listed))
        if self.public_web and port == DEFAULT_PORTS["https"]:
            return Target(scheme, host, port, False)
        raise DestinationDenied(f"{scheme}://{host}:{port} is not an approved destination")

    def connection_rule(self, host: str, port: int) -> AddressRule:
        """The addresses a connection to ``host:port`` may use; denies unknown targets.

        This is the check made where connections are opened, independent of
        any URL check made before the request. A connection does not carry
        its scheme, so a host and port listed for plain http is held to
        local addresses whatever the scheme.
        """
        host = normalize_host(host)
        listed = [(s, private) for (s, h, p, private) in self.destinations if (h, p) == (host, port)]
        if any(scheme == "http" for scheme, _ in listed):
            if not (self.allow_outbound_http and any(private for scheme, private in listed if scheme == "http")):
                raise DestinationDenied(f"{host}:{port} is not an approved destination")
            return "local"
        if listed:
            return "any" if any(private for _, private in listed) else "public"
        if self.public_web and port == DEFAULT_PORTS["https"]:
            return "public"
        raise DestinationDenied(f"{host}:{port} is not an approved destination")

    @staticmethod
    def address_allowed(address: IPAddress, rule: AddressRule) -> bool:
        if never_reachable(address):
            return False
        if rule == "local":
            return not address_permitted(address)
        return rule == "any" or address_permitted(address)
