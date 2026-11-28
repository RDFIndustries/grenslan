"""The launcher that confines bundled SearXNG to a relay (SEARXNG-EGRESS.md S1).

These tests start real namespaces. Where unprivileged user namespaces are
unavailable they are skipped; the supervisor then reports SearXNG as
unavailable, which test_bundled_searxng covers.
"""

from __future__ import annotations

import socket
import subprocess
import sys
from pathlib import Path

import anyio
import pytest
from anyio.abc import SocketStream


def launch(egress: Path, *command: str, probe: bool = False) -> subprocess.CompletedProcess[str]:
    arguments = [
        sys.executable,
        "-m",
        "grenslan.searxng.confine",
        "--relay-port",
        "3128",
        "--egress-socket",
        str(egress),
    ]
    arguments += ["--probe"] if probe else ["--", *command]
    return subprocess.run(arguments, capture_output=True, text=True, timeout=30, check=False)  # noqa: S603


@pytest.fixture(autouse=True)
def namespaces_available(tmp_path: Path) -> None:
    if launch(tmp_path / "none", probe=True).returncode != 0:
        pytest.skip("unprivileged user and network namespaces are not available here")


CHILD = """
import socket, sys
print(sorted(name for _, name in socket.if_nameindex()))
try:
    socket.create_connection(("192.0.2.1", 9), timeout=1)
    print("direct: connected")
except OSError as error:
    print("direct:", error.errno)
"""


def test_the_child_sees_only_loopback_and_cannot_connect_out(tmp_path: Path) -> None:
    result = launch(tmp_path / "none", sys.executable, "-c", CHILD)
    assert result.returncode == 0, result.stderr
    interfaces, direct = result.stdout.splitlines()
    assert interfaces == "['lo']"
    assert direct == "direct: 101"  # ENETUNREACH


def test_the_child_keeps_the_callers_user_and_group(tmp_path: Path) -> None:
    import os

    result = launch(tmp_path / "none", sys.executable, "-c", "import os; print(os.getuid(), os.getgid())")
    assert result.stdout.split() == [str(os.getuid()), str(os.getgid())]


def test_the_exit_status_is_the_childs(tmp_path: Path) -> None:
    assert launch(tmp_path / "none", sys.executable, "-c", "raise SystemExit(7)").returncode == 7


async def test_the_relay_reaches_the_egress_socket(tmp_path: Path) -> None:
    egress = tmp_path / "egress.sock"

    async def echo(connection: SocketStream) -> None:
        async with connection:
            await connection.send(b"echo:" + await connection.receive())

    listener = await anyio.create_unix_listener(egress)
    child = "import socket; s = socket.create_connection(('127.0.0.1', 3128)); s.sendall(b'hello'); print(s.recv(100))"
    async with anyio.create_task_group() as tasks:
        tasks.start_soon(listener.serve, echo)
        result = await anyio.to_thread.run_sync(lambda: launch(egress, sys.executable, "-c", child))
        tasks.cancel_scope.cancel()
    assert result.stdout.strip() == "b'echo:hello'", result.stderr


def test_any_interface_besides_loopback_stops_confinement(monkeypatch: pytest.MonkeyPatch) -> None:
    from grenslan.searxng import confine

    monkeypatch.setattr(socket, "if_nameindex", lambda: [(1, "lo"), (2, "eth0")])
    with pytest.raises(confine.ConfinementError, match="unexpected interfaces"):
        confine.require_loopback_only()
    monkeypatch.setattr(socket, "if_nameindex", lambda: [(1, "lo")])
    confine.require_loopback_only()


def test_the_launcher_refuses_to_run_with_another_interface(monkeypatch: pytest.MonkeyPatch) -> None:
    from grenslan.searxng import confine

    monkeypatch.setattr(confine, "enter_namespaces", lambda: None)
    monkeypatch.setattr(confine, "bring_up_loopback", lambda: None)
    monkeypatch.setattr(socket, "if_nameindex", lambda: [(1, "lo"), (2, "eth0")])
    arguments = ["--relay-port", "3128", "--egress-socket", "/nonexistent", "--probe"]
    assert confine.main(arguments) == confine.NAMESPACE_UNAVAILABLE
