"""Supervision of the bundled SearXNG process (SEARXNG-EGRESS.md S1 to S4, AD-423).

``BundledSearxng.start`` does the following:
1. Creates a private runtime directory (mode 0700) and writes generated settings there.
2. Starts the egress proxy on a socket in that directory.
3. Checks that confinement works on this host. If it does not, it fails with
   ``SearxngUnavailable`` rather than run SearXNG unconfined.
4. Starts SearXNG under Granian through ``grenslan.searxng.confine``, bound to a
   second socket in the directory.
5. Waits until SearXNG's health endpoint answers.

SearXNG therefore has no TCP listener and no route out except the proxy.

The child gets a minimal environment, so no Grenslan configuration or secret
reaches it. Its output is kept, bounded, only until it is healthy, so that a
startup failure can be explained. After that it is discarded, because
SearXNG's diagnostics can contain query text. ``stop`` terminates the whole
process group and removes the runtime directory.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import os
import secrets
import shutil
import signal
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path

import anyio
import httpcore2

from grenslan.network.backend import Resolver, system_resolver
from grenslan.network.egress_proxy import EgressProxy
from grenslan.network.policy import NetworkPolicy
from grenslan.searxng.settings import render_settings

logger = logging.getLogger(__name__)

RELAY_PORT = 3128
STARTUP_OUTPUT_BYTES = 16384
HEALTH_POLL_SECONDS = 0.25
STOP_GRACE_SECONDS = 10.0


class SearxngUnavailable(Exception):
    """Bundled SearXNG could not be started; the message says why and contains no query data."""


@dataclass(frozen=True, slots=True)
class BundledSettings:
    install_prefix: Path
    engines: tuple[str, ...]
    request_timeout: float
    max_request_timeout: float
    threads: int
    startup_timeout: float
    tunnel_connect_timeout: float
    tunnel_idle_timeout: float
    max_tunnels: int
    runtime_parent: Path | None = None
    # When set, the installation's SOURCE file must record this commit.
    expected_commit: str | None = None


def _recorded_commit(source: Path) -> str | None:
    try:
        lines = source.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    return next((line.removeprefix("commit=") for line in lines if line.startswith("commit=")), None)


class BundledSearxng:
    def __init__(self, settings: BundledSettings, policy: NetworkPolicy, *, resolver: Resolver = system_resolver):
        self._settings = settings
        self._proxy = EgressProxy(
            policy,
            resolver=resolver,
            connect_timeout=settings.tunnel_connect_timeout,
            idle_timeout=settings.tunnel_idle_timeout,
            max_tunnels=settings.max_tunnels,
        )
        self._runtime: Path | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._process: asyncio.subprocess.Process | None = None
        self._startup_output = bytearray()
        self._healthy = False

    @property
    def socket_path(self) -> Path:
        if self._runtime is None:
            raise RuntimeError("bundled SearXNG is not running")
        return self._runtime / "searxng.sock"

    def _environment(self, runtime: Path) -> dict[str, str]:
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": str(runtime),
            "LANG": "C.UTF-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "SEARXNG_SETTINGS_PATH": str(runtime / "settings.yml"),
        }

    def _confine(self, runtime: Path, *extra: str) -> list[str]:
        return [
            sys.executable,
            "-m",
            "grenslan.searxng.confine",
            "--relay-port",
            str(RELAY_PORT),
            "--egress-socket",
            str(runtime / "egress.sock"),
            *extra,
        ]

    async def start(self) -> None:
        settings = self._settings
        granian = settings.install_prefix / "venv" / "bin" / "granian"
        source = settings.install_prefix / "src"
        if not granian.is_file() or not (source / "searx" / "webapp.py").is_file():
            raise SearxngUnavailable(f"SearXNG is not installed at {settings.install_prefix}")
        if settings.expected_commit is not None:
            recorded = _recorded_commit(settings.install_prefix / "SOURCE")
            if recorded != settings.expected_commit:
                raise SearxngUnavailable(
                    f"the SearXNG installation at {settings.install_prefix} is not the expected build "
                    f"(commit {recorded or 'unknown'}, expected {settings.expected_commit})"
                )
        runtime = Path(tempfile.mkdtemp(prefix="grenslan-searxng-", dir=settings.runtime_parent))
        self._runtime = runtime
        try:
            (runtime / "settings.yml").write_text(
                render_settings(
                    engines=settings.engines,
                    secret_key=secrets.token_hex(32),
                    relay_port=RELAY_PORT,
                    request_timeout=settings.request_timeout,
                    max_request_timeout=settings.max_request_timeout,
                ),
                encoding="utf-8",
            )
            await self._probe(runtime)
            await self._start_proxy(runtime / "egress.sock")
            command = self._confine(
                runtime,
                "--",
                str(granian),
                "--interface",
                "wsgi",
                "--uds",
                str(runtime / "searxng.sock"),
                "--uds-permissions",
                "0600",
                "--workers",
                "1",
                "--blocking-threads",
                str(settings.threads),
                "--no-ws",
                "searx.webapp:app",
            )
            self._process = await asyncio.create_subprocess_exec(
                *command,
                cwd=source,
                env=self._environment(runtime),
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.STDOUT,
                start_new_session=True,
            )
            assert self._process.stdout is not None  # noqa: S101 - requested as a pipe above
            self._tasks.append(asyncio.create_task(self._drain(self._process.stdout)))
            await self._wait_healthy(settings.startup_timeout)
        except BaseException:
            await self.stop()
            raise

    async def _probe(self, runtime: Path) -> None:
        probe = await asyncio.create_subprocess_exec(
            *self._confine(runtime, "--probe"),
            env=self._environment(runtime),
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
        _, error = await probe.communicate()
        if probe.returncode != 0:
            detail = error.decode("utf-8", "replace").strip()[-500:]
            raise SearxngUnavailable(f"SearXNG cannot be confined on this host: {detail}")

    async def _start_proxy(self, path: Path) -> None:
        ready = asyncio.Event()

        async def serve() -> None:
            async with anyio.create_task_group() as tasks:
                await tasks.start(self._proxy.serve, path)
                ready.set()

        serving = asyncio.create_task(serve())
        self._tasks.append(serving)
        waiting = asyncio.create_task(ready.wait())
        await asyncio.wait({serving, waiting}, return_when=asyncio.FIRST_COMPLETED)
        waiting.cancel()
        if serving.done():
            raise SearxngUnavailable(f"the egress proxy could not start: {serving.exception()!r}")

    async def _drain(self, stream: asyncio.StreamReader) -> None:
        while chunk := await stream.read(65536):
            if not self._healthy and len(self._startup_output) < STARTUP_OUTPUT_BYTES:
                self._startup_output.extend(chunk[: STARTUP_OUTPUT_BYTES - len(self._startup_output)])

    def _startup_detail(self) -> str:
        return self._startup_output.decode("utf-8", "replace").strip()[-1000:]

    async def _wait_healthy(self, timeout: float) -> None:
        deadline = anyio.current_time() + timeout
        process = self._process
        assert process is not None  # noqa: S101 - set by start before waiting
        while anyio.current_time() < deadline:
            if process.returncode is not None:
                await asyncio.sleep(0.1)  # let the drain task collect the last output
                raise SearxngUnavailable(
                    f"SearXNG exited during startup with status {process.returncode}: {self._startup_detail()}"
                )
            if await self.healthy():
                self._healthy = True
                self._startup_output.clear()
                return
            await asyncio.sleep(HEALTH_POLL_SECONDS)
        raise SearxngUnavailable(f"SearXNG did not become healthy within {timeout} seconds: {self._startup_detail()}")

    async def healthy(self) -> bool:
        """Whether the process is running and its health endpoint answers ``OK``."""
        if self._process is None or self._process.returncode is not None or not self.socket_path.exists():
            return False
        try:
            async with httpcore2.AsyncConnectionPool(uds=str(self.socket_path)) as pool:
                with anyio.fail_after(5):
                    response = await pool.request("GET", "http://searxng/healthz")
        except (httpcore2.NetworkError, httpcore2.ProtocolError, httpcore2.TimeoutException, TimeoutError, OSError):
            return False
        return response.status == 200

    async def stop(self) -> None:
        process, self._process = self._process, None
        if process is not None and process.returncode is None:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(process.wait(), STOP_GRACE_SECONDS)
            except TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await process.wait()
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        self._tasks.clear()
        runtime, self._runtime = self._runtime, None
        if runtime is not None:
            shutil.rmtree(runtime, ignore_errors=True)
        self._healthy = False
