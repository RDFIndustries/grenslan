"""Supervisor failure paths: bundled SearXNG fails closed (SEARXNG-EGRESS.md S1)."""

from __future__ import annotations

import dataclasses
import json
import sys
from pathlib import Path

import pytest

from grenslan.network.policy import NetworkPolicy
from grenslan.searxng.bundled import BundledSearxng, BundledSettings, SearxngUnavailable

POLICY = NetworkPolicy.from_scope({"destinations": [], "public_web": False, "allow_outbound_http": False})


def settings(prefix: Path, runtime_parent: Path) -> BundledSettings:
    return BundledSettings(
        install_prefix=prefix, engines=("wikipedia",), request_timeout=2.0, max_request_timeout=4.0, threads=4,
        startup_timeout=30.0, tunnel_connect_timeout=2.0, tunnel_idle_timeout=5.0, max_tunnels=4,
        runtime_parent=runtime_parent,
    )  # fmt: skip


def fake_install(prefix: Path) -> Path:
    (prefix / "venv" / "bin").mkdir(parents=True)
    (prefix / "venv" / "bin" / "granian").write_text("")
    (prefix / "src" / "searx").mkdir(parents=True)
    (prefix / "src" / "searx" / "webapp.py").write_text("")
    return prefix


async def test_a_missing_installation_is_unavailable(tmp_path: Path) -> None:
    (tmp_path / "run").mkdir()
    with pytest.raises(SearxngUnavailable, match="not installed"):
        await BundledSearxng(settings(tmp_path / "absent", tmp_path / "run"), POLICY).start()
    assert list((tmp_path / "run").iterdir()) == []


async def test_without_confinement_searxng_is_not_started(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "run").mkdir()
    started = tmp_path / "started"
    failing_probe = [sys.executable, "-c", "import sys; sys.stderr.write('confinement failed: refused'); sys.exit(70)"]
    monkeypatch.setattr(BundledSearxng, "_confine", lambda self, runtime, *extra: failing_probe)
    bundled = BundledSearxng(settings(fake_install(tmp_path / "install"), tmp_path / "run"), POLICY)
    expected = "cannot be confined on this host: confinement failed: refused"
    with pytest.raises(SearxngUnavailable, match=expected) as raised:
        await bundled.start()
    assert "seccomp profile" in str(raised.value)
    assert not started.exists()
    assert list((tmp_path / "run").iterdir()) == []


async def test_a_process_that_exits_during_startup_is_reported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "run").mkdir()

    def command(self: BundledSearxng, runtime: Path, *extra: str) -> list[str]:
        if "--probe" in extra:
            return [sys.executable, "-c", "pass"]
        return [sys.executable, "-c", "print('startup problem'); raise SystemExit(3)"]

    monkeypatch.setattr(BundledSearxng, "_confine", command)
    bundled = BundledSearxng(settings(fake_install(tmp_path / "install"), tmp_path / "run"), POLICY)
    with pytest.raises(SearxngUnavailable, match="status 3: startup problem"):
        await bundled.start()
    assert list((tmp_path / "run").iterdir()) == []


async def test_the_child_receives_only_a_minimal_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "run").mkdir()
    seen = tmp_path / "environment.json"
    monkeypatch.setenv("GRENSLAN_FIXTURE_SECRET", "must-not-reach-searxng")
    dump = f"import json, os; open({str(seen)!r}, 'w').write(json.dumps(dict(os.environ))); raise SystemExit(1)"

    def command(self: BundledSearxng, runtime: Path, *extra: str) -> list[str]:
        return [sys.executable, "-c", "pass" if "--probe" in extra else dump]

    monkeypatch.setattr(BundledSearxng, "_confine", command)
    with pytest.raises(SearxngUnavailable):
        await BundledSearxng(settings(fake_install(tmp_path / "install"), tmp_path / "run"), POLICY).start()
    environment = json.loads(seen.read_text())
    environment.pop("LC_CTYPE", None)  # may be added by the interpreter itself
    assert sorted(environment) == ["HOME", "LANG", "PATH", "PYTHONDONTWRITEBYTECODE", "SEARXNG_SETTINGS_PATH", "TMPDIR"]
    # SearXNG's caches and other temporary files stay in the private runtime directory, removed on stop.
    runtime = Path(environment["SEARXNG_SETTINGS_PATH"]).parent
    assert environment["TMPDIR"] == environment["HOME"] == str(runtime)
    assert runtime.parent == tmp_path / "run"


@pytest.mark.parametrize("recorded", ["commit=0000000000000000000000000000000000000000\n", None])
async def test_an_installation_of_another_build_is_refused(tmp_path: Path, recorded: str | None) -> None:
    (tmp_path / "run").mkdir()
    prefix = fake_install(tmp_path / "install")
    if recorded is not None:
        (prefix / "SOURCE").write_text(recorded)
    expected = dataclasses.replace(settings(prefix, tmp_path / "run"), expected_commit="df67eb6c" + "0" * 32)
    with pytest.raises(SearxngUnavailable, match="not the expected build"):
        await BundledSearxng(expected, POLICY).start()
    assert list((tmp_path / "run").iterdir()) == []
