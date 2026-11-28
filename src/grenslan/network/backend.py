"""An httpcore2 network backend that opens only connections the network scope permits.

Every connection resolves its host once, is refused if any answer is a
prohibited address, connects to a checked address literal rather than the
name, and confirms that the connected peer is that address. A later DNS
change cannot redirect an established check, and a name that resolves to a
mix of public and private addresses is refused outright. Unix sockets are
never an outbound destination.
"""

from __future__ import annotations

import ipaddress
import socket
from collections.abc import Awaitable, Callable, Iterable
from typing import Any

import anyio
import httpcore2

from grenslan.network.addresses import IPAddress
from grenslan.network.errors import DestinationDenied, OutboundError
from grenslan.network.policy import NetworkPolicy

Resolver = Callable[[str, int], Awaitable[list[str]]]


async def system_resolver(host: str, port: int) -> list[str]:
    try:
        answers = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except socket.gaierror:
        return []
    return list(dict.fromkeys(str(answer[4][0]) for answer in answers))


def _literal(host: str) -> IPAddress | None:
    try:
        return ipaddress.ip_address(host)
    except ValueError:
        return None


class PolicyBackend(httpcore2.AsyncNetworkBackend):
    def __init__(self, policy: NetworkPolicy, resolver: Resolver) -> None:
        self._inner = httpcore2.AnyIOBackend()
        self._policy = policy
        self._resolver = resolver

    async def _answers(self, host: str, port: int) -> list[IPAddress]:
        literal = _literal(host)
        if literal is not None:
            return [literal]
        answers: list[IPAddress] = []
        for answer in await self._resolver(host, port):
            parsed = _literal(answer.split("%", 1)[0])
            if parsed is None:
                raise OutboundError("unresolved", f"{host!r} resolved to an unusable answer")
            answers.append(parsed)
        return answers

    async def connect_tcp(
        self,
        host: str,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: Iterable[Any] | None = None,
    ) -> httpcore2.AsyncNetworkStream:
        rule = self._policy.connection_rule(host, port)
        answers = await self._answers(host, port)
        if not answers:
            raise OutboundError("unresolved", f"{host!r} has no address")
        if any(not NetworkPolicy.address_allowed(answer, rule) for answer in answers):
            raise DestinationDenied(f"{host!r} resolves to a prohibited address")
        failure: Exception | None = None
        for answer in answers:
            try:
                stream = await self._inner.connect_tcp(str(answer), port, timeout, local_address, socket_options)
            except (httpcore2.ConnectError, httpcore2.ConnectTimeout) as error:
                failure = error
                continue
            peer = stream.get_extra_info("socket").getpeername()
            if _literal(str(peer[0]).split("%", 1)[0]) != answer or peer[1] != port:
                await stream.aclose()
                raise DestinationDenied(f"the connected peer is not the checked address for {host!r}")
            return stream
        assert failure is not None  # noqa: S101 - answers is non-empty, so a failure was recorded
        raise failure

    async def connect_unix_socket(
        self, path: str, timeout: float | None = None, socket_options: Iterable[Any] | None = None
    ) -> httpcore2.AsyncNetworkStream:
        raise DestinationDenied("unix sockets are not an outbound destination")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)
