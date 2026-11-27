"""Disposable preflight spike: connection-level outbound destination enforcement.

Not Grenslan service code. Demonstrates that an httpcore2 network backend can
enforce destination policy on the address actually connected to, independent
of URL parsing, with pinned resolution, per-hop redirect checks and
credential stripping. Runs entirely on loopback with a scoped fixture
exception and a substitutable resolver; no external network access.

Usage: python egress_spike.py <ca.pem> <server.pem> <server.key>
"""
from __future__ import annotations

import ipaddress
import socket
import ssl
import sys
import threading
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urljoin, urlsplit

import anyio
import httpcore2

NAT64 = ipaddress.ip_network("64:ff9b::/96")
METADATA = {ipaddress.ip_address("169.254.169.254"), ipaddress.ip_address("fd00:ec2::254")}


class DestinationDenied(Exception):
    pass


def embedded_ipv4(addr: ipaddress.IPv6Address) -> ipaddress.IPv4Address | None:
    if addr.ipv4_mapped is not None:
        return addr.ipv4_mapped
    if addr in NAT64:
        return ipaddress.IPv4Address(int(addr) & 0xFFFFFFFF)
    if addr.sixtofour is not None:
        return addr.sixtofour
    if addr.teredo is not None:
        return addr.teredo[1]
    return None


def address_permitted(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    if addr in METADATA or addr.is_multicast or not addr.is_global:
        return False
    if isinstance(addr, ipaddress.IPv6Address):
        inner = embedded_ipv4(addr)
        if inner is not None and not address_permitted(inner):
            return False
    return True


@dataclass(frozen=True)
class ScopedException:
    """An explicitly approved non-global destination for one purpose."""

    address: ipaddress.IPv4Address | ipaddress.IPv6Address
    port: int


Resolver = Callable[[str, int], Awaitable[list[str]]]


async def system_resolver(host: str, port: int) -> list[str]:
    infos = await anyio.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    return sorted({info[4][0] for info in infos})


class PolicyBackend(httpcore2.AsyncNetworkBackend):
    """Resolve once, check every answer, connect to the checked literal, verify the peer."""

    def __init__(self, resolver: Resolver, exceptions: Iterable[ScopedException] = ()) -> None:
        self._inner = httpcore2.AnyIOBackend()
        self._resolver = resolver
        self._exceptions = set(exceptions)
        self.connections: list[tuple[str, int]] = []

    def _allowed(self, addr, port: int) -> bool:
        return address_permitted(addr) or ScopedException(addr, port) in self._exceptions

    async def connect_tcp(self, host, port, timeout=None, local_address=None, socket_options=None):
        answers = [ipaddress.ip_address(a.split("%")[0]) for a in await self._resolver(host, port)]
        if not answers:
            raise DestinationDenied(f"no address for {host!r}")
        denied = [str(a) for a in answers if not self._allowed(a, port)]
        if denied:
            # Reject the name outright if any answer is prohibited.
            raise DestinationDenied(f"{host!r} resolves to prohibited address(es) {denied}")
        target = answers[0]
        stream = await self._inner.connect_tcp(str(target), port, timeout, local_address, socket_options)
        peer = stream.get_extra_info("socket").getpeername()
        if ipaddress.ip_address(peer[0]) != target or peer[1] != port:
            await stream.aclose()
            raise DestinationDenied(f"connected peer {peer} differs from checked target {target}:{port}")
        self.connections.append((str(target), port))
        return stream

    async def connect_unix_socket(self, *args, **kwargs):
        raise DestinationDenied("unix sockets are not an outbound destination")

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


async def fetch(pool: httpcore2.AsyncConnectionPool, url: str, credential_origin: str | None,
                credential: str | None, max_hops: int = 3) -> tuple[int, list[str], list[bool]]:
    """GET with explicit redirect handling; returns status, visited URLs, credential-sent flags."""
    visited, sent = [], []
    for _ in range(max_hops + 1):
        parts = urlsplit(url)
        if parts.scheme not in ("http", "https"):
            raise DestinationDenied(f"scheme {parts.scheme!r} not permitted")
        origin = f"{parts.scheme}://{parts.hostname}:{parts.port or (443 if parts.scheme == 'https' else 80)}"
        headers = [(b"host", parts.netloc.encode())]
        with_cred = credential is not None and origin == credential_origin
        if with_cred:
            headers.append((b"authorization", f"Bearer {credential}".encode()))
        visited.append(url)
        sent.append(with_cred)
        resp = await pool.request("GET", url, headers=headers)
        if resp.status in (301, 302, 303, 307, 308):
            location = dict((k.lower(), v) for k, v in resp.headers).get(b"location")
            if location is None:
                return resp.status, visited, sent
            url = urljoin(url, location.decode())
            continue
        return resp.status, visited, sent
    raise DestinationDenied("redirect limit exceeded")


class FixtureHandler(BaseHTTPRequestHandler):
    seen_auth: list[str | None] = []
    redirect_target = ""

    def do_GET(self):  # noqa: N802
        FixtureHandler.seen_auth.append(self.headers.get("Authorization"))
        if self.path.startswith("/redirect"):
            self.send_response(302)
            self.send_header("Location", FixtureHandler.redirect_target)
            self.end_headers()
            return
        body = b"ok"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


def start_fixture(certfile: str | None = None, keyfile: str | None = None) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureHandler)
    if certfile:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(certfile, keyfile)
        server.socket = ctx.wrap_socket(server.socket, server_side=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


results: list[tuple[str, bool, str]] = []


def record(name: str, ok: bool, detail: str = "") -> None:
    results.append((name, ok, detail))
    print(f"{'PASS' if ok else 'FAIL'}  {name}  {detail}")


async def expect_denied(name: str, coro) -> None:
    try:
        await coro
        record(name, False, "not denied")
    except (DestinationDenied, httpcore2.ConnectError) as exc:
        detail = str(exc)
        cause = exc.__cause__ or exc.__context__
        ok = isinstance(exc, DestinationDenied) or isinstance(cause, DestinationDenied)
        record(name, ok, detail[:110])


async def main(ca: str, cert: str, key: str) -> None:
    plain = start_fixture()
    tls = start_fixture(cert, key)
    p_port, t_port = plain.server_address[1], tls.server_address[1]
    loop = ipaddress.ip_address("127.0.0.1")
    exceptions = [ScopedException(loop, p_port), ScopedException(loop, t_port)]

    # Classification of hostile address representations (resolved form is what is checked).
    hostile = ["127.0.0.1", "10.0.0.1", "172.16.0.1", "192.168.1.1", "100.64.0.1", "169.254.169.254",
               "0.0.0.0", "255.255.255.255", "224.0.0.1", "::1", "::", "fe80::1", "fc00::1",
               "::ffff:127.0.0.1", "::ffff:169.254.169.254", "64:ff9b::7f00:1", "64:ff9b::a9fe:a9fe",
               "2002:7f00:1::1", "2001:0:4136:e378:8000:63bf:80ff:fffe", "fd00:ec2::254", "198.18.0.1"]
    wrongly_allowed = [a for a in hostile if address_permitted(ipaddress.ip_address(a))]
    record("hostile address classes denied", not wrongly_allowed, f"{len(hostile)} cases; allowed={wrongly_allowed}")
    record("public example address permitted", address_permitted(ipaddress.ip_address("93.184.215.14")))

    # Alternate textual forms resolve to loopback and are denied on the resolved address.
    for form in ("127.1", "2130706433", "0x7f000001", "0177.0.0.1", "localhost"):
        backend = PolicyBackend(system_resolver)
        async with httpcore2.AsyncConnectionPool(network_backend=backend) as pool:
            await expect_denied(f"alternate form {form!r} denied on resolved address",
                                pool.request("GET", f"http://{form}:{p_port + 1}/"))

    # Scoped exception: only the approved port on loopback is reachable.
    backend = PolicyBackend(system_resolver, exceptions)
    async with httpcore2.AsyncConnectionPool(network_backend=backend) as pool:
        r = await pool.request("GET", f"http://127.0.0.1:{p_port}/")
        record("scoped fixture exception reachable", r.status == 200 and backend.connections == [("127.0.0.1", p_port)],
               str(backend.connections))
        await expect_denied("same host, unapproved port denied", pool.request("GET", f"http://127.0.0.1:{p_port + 7}/"))

    # Mixed answers: one public, one prohibited -> whole name rejected.
    async def mixed(host, port):
        return ["93.184.215.14", "127.0.0.1"]
    backend = PolicyBackend(mixed)
    async with httpcore2.AsyncConnectionPool(network_backend=backend) as pool:
        await expect_denied("mixed public/private DNS answer rejected", pool.request("GET", "http://mixed.test/"))
        record("no connection attempted for mixed answer", backend.connections == [])

    # DNS change between check and connect: resolution happens once and the literal is pinned.
    calls = {"n": 0}
    async def rebinding(host, port):
        calls["n"] += 1
        return ["127.0.0.1"] if calls["n"] == 1 else ["169.254.169.254"]
    backend = PolicyBackend(rebinding, exceptions)
    async with httpcore2.AsyncConnectionPool(network_backend=backend) as pool:
        r = await pool.request("GET", f"http://rebind.test:{p_port}/")
        record("rebinding resolver: one resolution, pinned connect target",
               r.status == 200 and calls["n"] == 1 and backend.connections == [("127.0.0.1", p_port)],
               f"resolutions={calls['n']} connections={backend.connections}")

    # Redirect to a prohibited destination is checked per hop and denied.
    FixtureHandler.redirect_target = "http://169.254.169.254/latest/meta-data/"
    backend = PolicyBackend(system_resolver, exceptions)
    async with httpcore2.AsyncConnectionPool(network_backend=backend) as pool:
        await expect_denied("redirect to metadata address denied",
                            fetch(pool, f"http://127.0.0.1:{p_port}/redirect", None, None))
        record("no connection to redirect target", ("169.254.169.254", 80) not in backend.connections,
               str(backend.connections))

    # Credential is sent only to its origin and dropped on cross-origin redirect.
    FixtureHandler.seen_auth.clear()
    FixtureHandler.redirect_target = f"https://localhost:{t_port}/final"
    tls_ctx = ssl.create_default_context(cafile=ca)
    async def local(host, port):
        return ["127.0.0.1"]
    backend = PolicyBackend(local, exceptions)
    async with httpcore2.AsyncConnectionPool(network_backend=backend, ssl_context=tls_ctx) as pool:
        status, visited, sent = await fetch(pool, f"http://127.0.0.1:{p_port}/redirect",
                                            f"http://127.0.0.1:{p_port}", "fixture-secret")
        record("cross-origin redirect followed under policy", status == 200 and len(visited) == 2, str(visited))
        record("credential sent to its origin only", sent == [True, False] and
               FixtureHandler.seen_auth == ["Bearer fixture-secret", None], str(FixtureHandler.seen_auth))

    # TLS still verifies the hostname even though the connection is pinned to a literal.
    async with httpcore2.AsyncConnectionPool(network_backend=PolicyBackend(local, exceptions), ssl_context=tls_ctx) as pool:
        r = await pool.request("GET", f"https://localhost:{t_port}/")
        record("pinned connection with valid hostname certificate", r.status == 200)
        try:
            await pool.request("GET", f"https://wrong.test:{t_port}/")
            record("pinned connection rejects certificate for other hostname", False, "accepted")
        except httpcore2.ConnectError as exc:
            record("pinned connection rejects certificate for other hostname", "CERTIFICATE_VERIFY_FAILED" in str(exc) or "hostname" in str(exc).lower(), str(exc)[:90])
    async with httpcore2.AsyncConnectionPool(network_backend=PolicyBackend(local, exceptions)) as pool:
        try:
            await pool.request("GET", f"https://localhost:{t_port}/")
            record("untrusted CA rejected by default context", False, "accepted")
        except httpcore2.ConnectError:
            record("untrusted CA rejected by default context", True)

    # Non-HTTP schemes never reach the network.
    backend = PolicyBackend(system_resolver, exceptions)
    async with httpcore2.AsyncConnectionPool(network_backend=backend) as pool:
        await expect_denied("file:// scheme denied before connect", fetch(pool, "file:///etc/passwd", None, None))

    plain.shutdown(); tls.shutdown()
    failed = [r for r in results if not r[1]]
    print(f"SUMMARY {len(results) - len(failed)}/{len(results)} passed")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    anyio.run(main, *sys.argv[1:4])
