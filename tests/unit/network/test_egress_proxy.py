"""The CONNECT egress proxy that confined processes such as bundled SearXNG must use (S1, S3).

The proxy listens on a Unix socket and opens each tunnel through the same
connection-level checks as Grenslan's own requests. All traffic stays on
loopback.
"""

from __future__ import annotations

import stat
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import anyio
import pytest
from anyio.abc import SocketStream
from outbound_fixtures import FixtureServer, StaticResolver, fixture_server

from grenslan.network.egress_proxy import EgressProxy
from grenslan.network.policy import NetworkPolicy

LOOPBACK = ["127.0.0.1"]


def policy(*destinations: tuple[str, int, bool]) -> NetworkPolicy:
    return NetworkPolicy.from_scope(
        {
            "destinations": [
                {"scheme": "https", "host": host, "port": port, "allow_private_address": private}
                for host, port, private in destinations
            ],
            "public_web": False,
            "allow_outbound_http": False,
        }
    )


@pytest.fixture
def server() -> Iterator[FixtureServer]:
    with fixture_server() as running:
        yield running


@asynccontextmanager
async def running_proxy(tmp_path: Path, proxy: EgressProxy) -> AsyncIterator[Path]:
    path = tmp_path / "egress.sock"
    async with anyio.create_task_group() as tasks:
        await tasks.start(proxy.serve, path)
        try:
            yield path
        finally:
            tasks.cancel_scope.cancel()


async def read_head(stream: SocketStream) -> bytes:
    data = b""
    with anyio.fail_after(5):
        while b"\r\n\r\n" not in data:
            chunk = await stream.receive()
            data += chunk
    return data


async def read_all(stream: SocketStream) -> bytes:
    data = b""
    with anyio.fail_after(5):
        try:
            while True:
                data += await stream.receive()
        except (anyio.EndOfStream, anyio.BrokenResourceError):
            return data


def make_proxy(resolver: StaticResolver, *destinations: tuple[str, int, bool], **kwargs: Any) -> EgressProxy:
    kwargs.setdefault("connect_timeout", 2)
    kwargs.setdefault("idle_timeout", 2)
    kwargs.setdefault("max_tunnels", 4)
    return EgressProxy(policy(*destinations), resolver=resolver, **kwargs)


def get(port: int) -> bytes:
    return f"GET /through HTTP/1.1\r\nHost: fixture.test:{port}\r\nConnection: close\r\n\r\n".encode()


async def test_an_approved_tunnel_carries_bytes_both_ways(tmp_path: Path, server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with running_proxy(tmp_path, make_proxy(resolver, ("fixture.test", server.port, True))) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(f"CONNECT fixture.test:{server.port} HTTP/1.1\r\nHost: fixture.test\r\n\r\n".encode())
        assert (await read_head(stream)).startswith(b"HTTP/1.1 200")
        await stream.send(get(server.port))
        assert b"\r\n\r\nok" in await read_all(stream)
    assert [seen.path for seen in server.routes.seen] == ["/through"]


async def test_bytes_sent_with_the_connect_request_are_forwarded(tmp_path: Path, server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with running_proxy(tmp_path, make_proxy(resolver, ("fixture.test", server.port, True))) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(f"CONNECT fixture.test:{server.port} HTTP/1.1\r\n\r\n".encode() + get(server.port))
        response = await read_all(stream)
    assert response.startswith(b"HTTP/1.1 200")
    assert b"\r\n\r\nok" in response


@pytest.mark.parametrize(
    ("authority", "table"),
    [
        pytest.param("elsewhere.test:{port}", {"elsewhere.test": LOOPBACK}, id="unlisted-host"),
        pytest.param("fixture.test:1", {"fixture.test": LOOPBACK}, id="unlisted-port"),
        pytest.param("127.0.0.1:{port}", {}, id="ip-literal"),
        pytest.param("public.test:{port}", {"public.test": LOOPBACK}, id="listed-but-private-address"),
    ],
)
async def test_tunnels_outside_the_scope_are_refused_without_connecting(
    tmp_path: Path, server: FixtureServer, authority: str, table: dict[str, list[str]]
) -> None:
    resolver = StaticResolver(table)
    proxy = make_proxy(resolver, ("fixture.test", server.port, True), ("public.test", server.port, False))
    async with running_proxy(tmp_path, proxy) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(f"CONNECT {authority.format(port=server.port)} HTTP/1.1\r\n\r\n".encode())
        response = await read_all(stream)
    assert response.startswith(b"HTTP/1.1 403")
    assert server.routes.seen == []


@pytest.mark.parametrize(
    ("request_bytes", "status"),
    [
        pytest.param(b"GET http://fixture.test/ HTTP/1.1\r\nHost: fixture.test\r\n\r\n", b"405", id="absolute-form"),
        pytest.param(b"CONNECT fixture.test HTTP/1.1\r\n\r\n", b"400", id="no-port"),
        pytest.param(b"CONNECT fixture.test:https HTTP/1.1\r\n\r\n", b"400", id="named-port"),
        pytest.param(b"CONNECT user@fixture.test:443 HTTP/1.1\r\n\r\n", b"400", id="userinfo"),
        pytest.param(b"CONNECT fixture.test:443 HTTP/1.0 extra\r\n\r\n", b"400", id="malformed-line"),
        pytest.param(b"\x16\x03\x01\x02\x00garbage\r\n\r\n", b"400", id="not-http"),
        pytest.param(b"CONNECT fixture.test:443 HTTP/2.0\r\n\r\n", b"400", id="version"),
        pytest.param(b"CONNECT fixture.test:443 HTTP/1.1\r\nX: " + b"a" * 9000 + b"\r\n\r\n", b"431", id="oversized"),
    ],
)
async def test_requests_other_than_a_well_formed_connect_are_refused(
    tmp_path: Path, request_bytes: bytes, status: bytes
) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    async with running_proxy(tmp_path, make_proxy(resolver, ("fixture.test", 443, True))) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(request_bytes)
        response = await read_all(stream)
    assert response.startswith(b"HTTP/1.1 " + status)
    assert resolver.lookups == []


async def test_an_unresolvable_name_is_a_bad_gateway(tmp_path: Path) -> None:
    async with running_proxy(tmp_path, make_proxy(StaticResolver({}), ("missing.test", 443, False))) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(b"CONNECT missing.test:443 HTTP/1.1\r\n\r\n")
        assert (await read_all(stream)).startswith(b"HTTP/1.1 502")


async def test_a_request_head_that_never_completes_is_closed(tmp_path: Path) -> None:
    proxy = make_proxy(StaticResolver({}), ("fixture.test", 443, True), idle_timeout=0.3)
    async with running_proxy(tmp_path, proxy) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(b"CONNECT fixture.test:443 HTTP/1.1\r\n")
        assert (await read_all(stream)).startswith(b"HTTP/1.1 408")


async def test_idle_tunnels_are_closed(tmp_path: Path, server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    proxy = make_proxy(resolver, ("fixture.test", server.port, True), idle_timeout=0.3)
    async with running_proxy(tmp_path, proxy) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(f"CONNECT fixture.test:{server.port} HTTP/1.1\r\n\r\n".encode())
        await read_head(stream)
        with anyio.fail_after(3):
            assert await read_all(stream) == b""


async def test_the_number_of_tunnels_is_bounded(tmp_path: Path, server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    proxy = make_proxy(resolver, ("fixture.test", server.port, True), max_tunnels=1)
    async with running_proxy(tmp_path, proxy) as path:
        first = await anyio.connect_unix(path)
        await first.send(f"CONNECT fixture.test:{server.port} HTTP/1.1\r\n\r\n".encode())
        assert (await read_head(first)).startswith(b"HTTP/1.1 200")
        second = await anyio.connect_unix(path)
        await second.send(f"CONNECT fixture.test:{server.port} HTTP/1.1\r\n\r\n".encode())
        assert (await read_all(second)).startswith(b"HTTP/1.1 503")
        await first.aclose()


async def test_the_socket_is_accessible_to_its_owner_only(tmp_path: Path) -> None:
    async with running_proxy(tmp_path, make_proxy(StaticResolver({}))) as path:
        assert stat.S_IMODE(path.stat().st_mode) == 0o600


async def test_an_existing_file_at_the_socket_path_is_not_replaced(tmp_path: Path) -> None:
    path = tmp_path / "egress.sock"
    path.write_text("not a socket")
    with pytest.raises(FileExistsError):
        await make_proxy(StaticResolver({})).serve(path)
    assert path.read_text() == "not a socket"


async def test_tunnels_to_plain_http_destinations_are_refused(tmp_path: Path, server: FixtureServer) -> None:
    resolver = StaticResolver({"fixture.test": LOOPBACK})
    plain = NetworkPolicy.from_scope(
        {
            "destinations": [
                {"scheme": "http", "host": "fixture.test", "port": server.port, "allow_private_address": True}
            ],
            "public_web": False,
            "allow_outbound_http": True,
        }
    )
    proxy = EgressProxy(plain, resolver=resolver, connect_timeout=2, idle_timeout=2, max_tunnels=4)
    async with running_proxy(tmp_path, proxy) as path:
        stream = await anyio.connect_unix(path)
        await stream.send(f"CONNECT fixture.test:{server.port} HTTP/1.1\r\n\r\n".encode())
        assert (await read_all(stream)).startswith(b"HTTP/1.1 403")
    assert server.routes.seen == []


async def test_a_head_without_an_end_is_refused_once_it_exceeds_the_limit(tmp_path: Path) -> None:
    proxy = make_proxy(StaticResolver({}), ("fixture.test", 443, True), idle_timeout=5)
    async with running_proxy(tmp_path, proxy) as path:
        stream = await anyio.connect_unix(path)
        with anyio.fail_after(2):
            try:
                for _ in range(20):
                    await stream.send(b"X" * 1024)
            except anyio.BrokenResourceError:
                pass
            assert (await read_all(stream)).startswith(b"HTTP/1.1 431")


@asynccontextmanager
async def upstream(handler: Callable[[SocketStream], Awaitable[None]]) -> AsyncIterator[int]:
    listener = await anyio.create_tcp_listener(local_host="127.0.0.1")
    port = listener.extra(anyio.abc.SocketAttribute.local_port)  # noqa: S610 - anyio typed attribute, not Django
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(listener.serve, handler)
        try:
            yield port
        finally:
            tasks.cancel_scope.cancel()


async def open_tunnel(path: Path, port: int) -> SocketStream:
    stream = await anyio.connect_unix(path)
    await stream.send(f"CONNECT upstream.test:{port} HTTP/1.1\r\n\r\n".encode())
    assert (await read_head(stream)).startswith(b"HTTP/1.1 200")
    return stream


def tunnel_proxy(port: int) -> EgressProxy:
    return make_proxy(StaticResolver({"upstream.test": LOOPBACK}), ("upstream.test", port, True), idle_timeout=0.5)


async def test_a_tunnel_receiving_data_outlives_the_idle_timeout(tmp_path: Path) -> None:
    async def trickle(connection: SocketStream) -> None:
        async with connection:
            for _ in range(6):
                await anyio.sleep(0.2)
                await connection.send(b"x")

    async with upstream(trickle) as port, running_proxy(tmp_path, tunnel_proxy(port)) as path:
        stream = await open_tunnel(path, port)
        assert await read_all(stream) == b"x" * 6


async def test_a_tunnel_sending_data_outlives_the_idle_timeout(tmp_path: Path) -> None:
    received = bytearray()
    done = anyio.Event()

    async def sink(connection: SocketStream) -> None:
        async with connection:
            try:
                while True:
                    received.extend(await connection.receive())
            except (anyio.EndOfStream, anyio.BrokenResourceError):
                done.set()

    async with upstream(sink) as port, running_proxy(tmp_path, tunnel_proxy(port)) as path:
        stream = await open_tunnel(path, port)
        for _ in range(6):
            await anyio.sleep(0.2)
            await stream.send(b"x")
        await stream.aclose()
        with anyio.fail_after(3):
            await done.wait()
    assert bytes(received) == b"x" * 6
