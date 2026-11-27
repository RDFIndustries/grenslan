"""Classification of IP addresses for outbound connections.

Only globally routable unicast addresses are public. IPv6 forms that carry an
IPv4 address (IPv4-mapped, NAT64, 6to4, Teredo) are judged by the embedded
address too, so ``::ffff:127.0.0.1`` or ``64:ff9b::a9fe:a9fe`` cannot reach
loopback or cloud metadata.
"""

from __future__ import annotations

import ipaddress

IPAddress = ipaddress.IPv4Address | ipaddress.IPv6Address

NAT64 = ipaddress.ip_network("64:ff9b::/96")
# Cloud instance metadata services. Never reachable, whatever a scope allows.
METADATA = frozenset({ipaddress.ip_address("169.254.169.254"), ipaddress.ip_address("fd00:ec2::254")})


def embedded_ipv4(address: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if address.ipv4_mapped is not None:
        return address.ipv4_mapped
    if address in NAT64:
        return ipaddress.IPv4Address(int(address) & 0xFFFFFFFF)
    if address.sixtofour is not None:
        return address.sixtofour
    if address.teredo is not None:
        return address.teredo[1]
    return None


def _related(address: IPAddress) -> list[IPAddress]:
    inner = embedded_ipv4(address) if isinstance(address, ipaddress.IPv6Address) else None
    return [address] if inner is None else [address, inner]


def never_reachable(address: IPAddress) -> bool:
    """Metadata, unspecified, multicast and broadcast addresses: denied even to private destinations."""
    return any(
        candidate in METADATA
        or candidate.is_unspecified
        or candidate.is_multicast
        or candidate == ipaddress.IPv4Address("255.255.255.255")
        for candidate in _related(address)
    )


def address_permitted(address: IPAddress) -> bool:
    """True only for a public unicast address."""
    return not never_reachable(address) and all(candidate.is_global for candidate in _related(address))
