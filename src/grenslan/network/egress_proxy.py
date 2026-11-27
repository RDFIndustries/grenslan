"""The egress proxy for confined processes, such as bundled SearXNG (SEARXNG-EGRESS.md S1, S3).

A confined process has no network of its own. Its only way out is this proxy,
which listens on a Unix socket and accepts only ``CONNECT host:port``. Each
tunnel is checked against the process's network scope as an https
destination. It is then opened through ``PolicyBackend``, with the same
resolution, address and peer checks as Grenslan's own requests. The tunnelled
bytes are relayed unchanged: TLS runs end to end between the confined process
and the destination, and the confined process verifies the certificate.

The proxy bounds the request head, the number of open tunnels, the time to
connect, and idle time on each tunnel. The socket is created owner-only, and
its directory must also be private to the service.
"""

from __future__ import annotations

import contextlib
import logging
import os
from pathlib import Path

import anyio
import httpcore2
from anyio.abc import SocketStream, TaskStatus

from grenslan.network.backend import PolicyBackend, Resolver, system_resolver
from grenslan.network.errors import DestinationDenied, OutboundError
from grenslan.network.policy import NetworkPolicy

logger = logging.getLogger(__name__)

MAX_HEAD_BYTES = 8192
READ_BYTES = 65536
REASONS = {
    400: "Bad Request",
    403: "Forbidden",
    405: "Method Not Allowed",
    408: "Request Timeout",
    431: "Request Header Fields Too Large",
    502: "Bad Gateway",
    503: "Service Unavailable",
    504: "Gateway Timeout",
}


class _Refused(Exception):
    def __init__(self, status: int) -> None:
        super().__init__(status)
        self.status = status


def _authority(line: bytes) -> tuple[str, int]:
    """Host and port from a ``CONNECT host:port HTTP/1.x`` request line."""
    try:
        method, authority, version = line.decode("ascii").split(" ")
    except (UnicodeDecodeError, ValueError):
        raise _Refused(400) from None
    if version not in ("HTTP/1.1", "HTTP/1.0"):
        raise _Refused(400)
    if method != "CONNECT":
        raise _Refused(405)
    if any(character in authority for character in "@/?#\\"):
        raise _Refused(400)
    host, separator, port = authority.rpartition(":")
    if not separator or not host or not port.isdigit() or not 0 < int(port) < 65536:
        raise _Refused(400)
    if host.startswith("[") and host.endswith("]"):
        host = host[1:-1]
    return host, int(port)


class EgressProxy:
    def __init__(
        self,
        policy: NetworkPolicy,
        *,
        resolver: Resolver = system_resolver,
        connect_timeout: float,
        idle_timeout: float,
        max_tunnels: int,
    ) -> None:
        self._policy = policy
        self._backend = PolicyBackend(policy, resolver)
        self._connect_timeout = connect_timeout
        self._idle_timeout = idle_timeout
        self._max_tunnels = max_tunnels
        self._active = 0

    async def serve(self, path: Path, *, task_status: TaskStatus[None] = anyio.TASK_STATUS_IGNORED) -> None:
        """Listen on a new Unix socket at ``path`` until cancelled; an existing file is never replaced."""
        if os.path.lexists(path):
            raise FileExistsError(f"{path} already exists")
        listener = await anyio.create_unix_listener(path)
        try:
            os.chmod(path, 0o600)
            task_status.started()
            await listener.serve(self._handle)
        finally:
            await listener.aclose()
            path.unlink(missing_ok=True)

    async def _handle(self, client: SocketStream) -> None:
        async with client:
            if self._active >= self._max_tunnels:
                await self._refuse(client, 503)
                return
            self._active += 1
            try:
                await self._tunnel(client)
            except _Refused as refusal:
                await self._refuse(client, refusal.status)
            except (anyio.EndOfStream, anyio.BrokenResourceError, anyio.ClosedResourceError):
                pass
            finally:
                self._active -= 1

    @staticmethod
    async def _refuse(client: SocketStream, status: int) -> None:
        reply = f"HTTP/1.1 {status} {REASONS[status]}\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        with contextlib.suppress(anyio.BrokenResourceError, anyio.ClosedResourceError):
            await client.send(reply.encode("ascii"))

    async def _read_head(self, client: SocketStream) -> tuple[bytes, bytes]:
        data = b""
        try:
            with anyio.fail_after(self._idle_timeout):
                while b"\r\n\r\n" not in data:
                    if len(data) > MAX_HEAD_BYTES:
                        raise _Refused(431)
                    data += await client.receive(READ_BYTES)
        except TimeoutError:
            raise _Refused(408) from None
        head, _, rest = data.partition(b"\r\n\r\n")
        if len(head) > MAX_HEAD_BYTES:
            raise _Refused(431)
        return head, rest

    async def _open(self, host: str, port: int) -> httpcore2.AsyncNetworkStream:
        try:
            self._policy.check_url(f"https://{f'[{host}]' if ':' in host else host}:{port}/")
            with anyio.fail_after(self._connect_timeout):
                return await self._backend.connect_tcp(host, port, timeout=self._connect_timeout)
        except DestinationDenied as denial:
            logger.warning("egress tunnel to %s:%d denied: %s", host, port, denial)
            raise _Refused(403) from None
        except TimeoutError:
            raise _Refused(504) from None
        except (OutboundError, httpcore2.ConnectError, httpcore2.ConnectTimeout):
            raise _Refused(502) from None

    async def _tunnel(self, client: SocketStream) -> None:
        head, rest = await self._read_head(client)
        host, port = _authority(head.split(b"\r\n", 1)[0])
        upstream = await self._open(host, port)
        try:
            await client.send(b"HTTP/1.1 200 Connection established\r\n\r\n")
            if rest:
                await upstream.write(rest)
            await self._relay(client, upstream)
        finally:
            await upstream.aclose()

    async def _relay(self, client: SocketStream, upstream: httpcore2.AsyncNetworkStream) -> None:
        """Copy both ways until either side closes or the tunnel is idle for ``idle_timeout``."""
        with anyio.CancelScope(deadline=anyio.current_time() + self._idle_timeout) as idle:

            def active() -> None:
                idle.deadline = anyio.current_time() + self._idle_timeout

            async def outward() -> None:
                while True:
                    try:
                        chunk = await client.receive(READ_BYTES)
                    except (anyio.EndOfStream, anyio.BrokenResourceError):
                        break
                    active()
                    await upstream.write(chunk)
                tasks.cancel_scope.cancel()

            async def inward() -> None:
                while chunk := await upstream.read(READ_BYTES):
                    active()
                    await client.send(chunk)
                tasks.cancel_scope.cancel()

            try:
                async with anyio.create_task_group() as tasks:
                    tasks.start_soon(outward)
                    tasks.start_soon(inward)
            except* (httpcore2.ReadError, httpcore2.WriteError, anyio.BrokenResourceError, anyio.ClosedResourceError):
                pass
