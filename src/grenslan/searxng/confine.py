"""Run a command with no network except a relay to an egress proxy socket (SEARXNG-EGRESS.md S1).

Invoked by the supervisor as ``python -m grenslan.searxng.confine``. The
process enters new user and network namespaces, mapping only its own user and
group IDs, so it gains no privilege outside them. It brings up loopback and
refuses to continue if any other interface exists. On ``127.0.0.1:PORT`` it
relays each connection, byte for byte, to the egress proxy's Unix socket,
which is reachable because the filesystem is shared. Then it runs the command
as a child. The command's only route off the host is therefore the proxy.
The launcher exits with the child's status, and passes SIGTERM and SIGINT to
it.

Standard library only. The namespaces are created first, before any thread
exists, because a multithreaded process cannot create a user namespace.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import fcntl
import os
import signal
import socket
import struct
import sys
from collections.abc import Sequence

SIOCGIFFLAGS = 0x8913
SIOCSIFFLAGS = 0x8914
IFF_UP = 0x1
NAMESPACE_UNAVAILABLE = 70
RELAY_BYTES = 65536


class ConfinementError(Exception):
    pass


def enter_namespaces() -> None:
    uid, gid = os.getuid(), os.getgid()
    try:
        os.unshare(os.CLONE_NEWUSER | os.CLONE_NEWNET)
    except OSError as error:
        raise ConfinementError(f"cannot create user and network namespaces: {error.strerror}") from error
    with open("/proc/self/setgroups", "w") as setgroups:
        setgroups.write("deny")
    with open("/proc/self/uid_map", "w") as uid_map:
        uid_map.write(f"{uid} {uid} 1")
    with open("/proc/self/gid_map", "w") as gid_map:
        gid_map.write(f"{gid} {gid} 1")


def bring_up_loopback() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as control:
        request = struct.pack("16sH14x", b"lo", 0)
        flags = struct.unpack("16sH14x", fcntl.ioctl(control, SIOCGIFFLAGS, request))[1]
        fcntl.ioctl(control, SIOCSIFFLAGS, struct.pack("16sH14x", b"lo", flags | IFF_UP))


def require_loopback_only() -> None:
    names = sorted(name for _, name in socket.if_nameindex())
    if names != ["lo"]:
        raise ConfinementError(f"the confined network has unexpected interfaces: {names}")


async def _pipe(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        while chunk := await reader.read(RELAY_BYTES):
            writer.write(chunk)
            await writer.drain()
    except (ConnectionError, OSError):
        pass
    finally:
        with contextlib.suppress(ConnectionError, OSError):
            writer.close()


async def _relay_connection(egress: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        upstream_reader, upstream_writer = await asyncio.open_unix_connection(egress)
    except OSError:
        writer.close()
        return
    await asyncio.gather(_pipe(reader, upstream_writer), _pipe(upstream_reader, writer))


async def _run(command: Sequence[str], relay_port: int, egress: str) -> int:
    server = await asyncio.start_server(lambda r, w: _relay_connection(egress, r, w), host="127.0.0.1", port=relay_port)
    child = await asyncio.create_subprocess_exec(*command)
    loop = asyncio.get_running_loop()
    for number in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(number, child.send_signal, number)
    try:
        return await child.wait()
    finally:
        server.close()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m grenslan.searxng.confine")
    parser.add_argument("--relay-port", type=int, required=True)
    parser.add_argument("--egress-socket", required=True)
    parser.add_argument("--probe", action="store_true", help="check that confinement works, then exit")
    parser.add_argument("command", nargs="*")
    arguments = parser.parse_args(argv)
    try:
        enter_namespaces()
        bring_up_loopback()
        require_loopback_only()
    except (ConfinementError, OSError) as error:
        print(f"confinement failed: {error}", file=sys.stderr)
        return NAMESPACE_UNAVAILABLE
    if arguments.probe:
        return 0
    if not arguments.command:
        parser.error("a command is required")
    status = asyncio.run(_run(arguments.command, arguments.relay_port, arguments.egress_socket))
    return status if status >= 0 else 128 - status


if __name__ == "__main__":
    sys.exit(main())
