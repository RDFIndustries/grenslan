"""The grenslan command (SERVICE-CONFIGURATION.md D2, D6)."""

from __future__ import annotations

import hashlib
import io
import re
from pathlib import Path

import pytest
import yaml

from grenslan.cli import check_config, credential_new, main

from fixture_providers import fixture_config
from service_fixtures import QOR_TOKEN, service_data, write_service_file
from tls_fixtures import make_tls_material


def test_credential_new_prints_a_token_and_its_digest() -> None:
    out, err = io.StringIO(), io.StringIO()
    assert credential_new(out, err) == 0
    token_line, digest_line = out.getvalue().splitlines()
    token = token_line.removeprefix("token: ")
    assert re.fullmatch(r"[A-Za-z0-9_-]{43}", token)
    assert digest_line == f"token_sha256: {hashlib.sha256(token.encode()).hexdigest()}"
    assert token not in err.getvalue()


def test_credential_new_tokens_differ() -> None:
    outputs = set()
    for _ in range(2):
        out = io.StringIO()
        credential_new(out, io.StringIO())
        outputs.add(out.getvalue())
    assert len(outputs) == 2


def environment(tmp_path: Path, data: dict[str, object] | None = None) -> dict[str, str]:
    material = make_tls_material(tmp_path)
    service = write_service_file(tmp_path / "service.yaml", data or service_data(), material)
    providers = tmp_path / "providers.yaml"
    providers.write_text(yaml.safe_dump(fixture_config()), encoding="utf-8")
    return {"GRENSLAN_SERVICE_CONFIG": str(service), "GRENSLAN_PROVIDER_CONFIG": str(providers)}


def test_check_config_accepts_a_valid_deployment(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    assert check_config(environment(tmp_path), out, err) == 0
    assert "valid" in out.getvalue()
    assert err.getvalue() == ""


def test_check_config_reports_every_problem_without_values(tmp_path: Path) -> None:
    data = service_data()
    data["credentials"]["qor"]["permissions"] = [QOR_TOKEN.replace("-", "_")]
    data["tools"]["profile"] = "absent"
    environ = environment(tmp_path, data) | {"GRENSLAN_LISTEN_PROT": "1"}
    out, err = io.StringIO(), io.StringIO()
    assert check_config(environ, out, err) == 1
    report = err.getvalue()
    assert f"{environ['GRENSLAN_SERVICE_CONFIG']}: GRENSLAN_LISTEN_PROT" in report
    assert "/credentials/qor/permissions/0" in report
    assert "/tools/profile" in report
    assert QOR_TOKEN.replace("-", "_") not in report
    assert data["credentials"]["qor"]["token_sha256"] not in report


def test_check_config_loads_the_tls_pair(tmp_path: Path) -> None:
    environ = environment(tmp_path)
    (tmp_path / "server.key").write_text("not a key", encoding="utf-8")
    service = yaml.safe_load(Path(environ["GRENSLAN_SERVICE_CONFIG"]).read_text())
    service["tls"]["private_key_file"] = str(tmp_path / "server.key")
    Path(environ["GRENSLAN_SERVICE_CONFIG"]).write_text(yaml.safe_dump(service), encoding="utf-8")
    err = io.StringIO()
    assert check_config(environ, io.StringIO(), err) == 1
    assert "TLS" in err.getvalue()


def test_check_config_rejects_unregistered_provider_implementations(tmp_path: Path) -> None:
    environ = environment(tmp_path)
    Path(environ["GRENSLAN_PROVIDER_CONFIG"]).write_text(yaml.safe_dump(fixture_config("primary")), encoding="utf-8")
    err = io.StringIO()
    assert check_config(environ, io.StringIO(), err) == 1
    assert f"{environ['GRENSLAN_PROVIDER_CONFIG']}: /providers/primary" in err.getvalue()


def test_main_requires_a_command() -> None:
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_extension_launcher_registers_the_extension(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    from example_launcher import run

    environ = environment(tmp_path)
    Path(environ["GRENSLAN_PROVIDER_CONFIG"]).write_text(yaml.safe_dump(fixture_config("primary")), encoding="utf-8")
    for name, value in environ.items():
        monkeypatch.setenv(name, value)
    assert run(["check-config"]) == 0
    assert main(["check-config"]) == 1
    assert "/providers/primary" in capsys.readouterr().err


def test_check_config_verifies_the_extension_manifest(tmp_path: Path) -> None:
    import json

    from grenslan.providers.registry import ImplementationRegistry

    from fixture_providers import FIXTURE_MANIFEST, FixtureSet

    environ = environment(tmp_path)
    Path(environ["GRENSLAN_PROVIDER_CONFIG"]).write_text(yaml.safe_dump(fixture_config("primary")), encoding="utf-8")
    manifest = tmp_path / "fixture.json"
    data = json.loads(FIXTURE_MANIFEST.read_text(encoding="utf-8"))
    manifest.write_text(json.dumps(data | {"supported_platforms": ["linux-aarch64"]}), encoding="utf-8")
    err = io.StringIO()
    registry = ImplementationRegistry([FixtureSet(manifest=manifest).implementation()])
    assert check_config(environ, io.StringIO(), err, registry) == 1
    assert "provider 'primary'" in err.getvalue()
