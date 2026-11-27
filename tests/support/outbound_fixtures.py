"""Loopback HTTP(S) servers and a substitutable resolver for outbound-enforcement tests.

Every server listens on 127.0.0.1 only. Tests reach them through destinations
that explicitly allow a private address, so nothing here touches a real
network.
"""

from __future__ import annotations

import ssl
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from tls_fixtures import TlsMaterial


@dataclass
class SeenRequest:
    method: str
    path: str
    headers: dict[str, str]
    body: bytes


@dataclass
class Routes:
    """Responses by path: (status, headers, body). Unknown paths return 200 "ok"."""

    responses: dict[str, tuple[int, list[tuple[str, str]], bytes]] = field(default_factory=dict)
    seen: list[SeenRequest] = field(default_factory=list)


class _Handler(BaseHTTPRequestHandler):
    routes: Routes

    def _serve(self) -> None:
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        self.routes.seen.append(
            SeenRequest(self.command, self.path, {k.lower(): v for k, v in self.headers.items()}, body)
        )
        status, headers, payload = self.routes.responses.get(self.path, (200, [], b"ok"))
        self.send_response(status)
        for name, value in headers:
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    do_GET = _serve
    do_POST = _serve

    def log_message(self, format: str, *args: object) -> None:
        pass


@dataclass
class FixtureServer:
    port: int
    routes: Routes


@contextmanager
def fixture_server(tls: TlsMaterial | None = None) -> Iterator[FixtureServer]:
    routes = Routes()
    handler = type("Handler", (_Handler,), {"routes": routes})
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    if tls is not None:
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        context.load_cert_chain(str(tls.cert_file), str(tls.key_file))
        server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield FixtureServer(server.server_address[1], routes)
    finally:
        server.shutdown()
        server.server_close()


class StaticResolver:
    """Answers from a fixed table and counts lookups; unknown names have no address."""

    def __init__(self, table: dict[str, list[str]]) -> None:
        self.table = table
        self.lookups: list[str] = []

    async def __call__(self, host: str, port: int) -> list[str]:
        self.lookups.append(host)
        return list(self.table.get(host, []))
