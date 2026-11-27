"""grenslan tls new: a private CA and server certificate for deployments without their own issuer."""

from __future__ import annotations

import asyncio
import datetime
import io
import ssl
import stat
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.x509.oid import ExtendedKeyUsageOID

from grenslan.cli import main, tls_new
from grenslan.server.tls import server_ssl_context
from grenslan.server.tls_issue import IssuedFiles, TlsIssueError, issue_certificate

from tls_fixtures import make_tls_material


def issued(tmp_path: Path, **kwargs: object) -> IssuedFiles:
    options: dict[str, object] = {"names": ["grenslan", "localhost", "127.0.0.1"], "days": 30, "ca_days": 365}
    options.update(kwargs)
    return issue_certificate(tmp_path / "tls", **options)  # type: ignore[arg-type]


async def handshake(files: IssuedFiles, server_hostname: str) -> None:
    context = server_ssl_context(files.certificate, files.private_key)
    server = await asyncio.start_server(lambda r, w: w.close(), "127.0.0.1", 0, ssl=context)
    port = server.sockets[0].getsockname()[1]
    client = ssl.create_default_context(cafile=str(files.ca_certificate))
    try:
        _, writer = await asyncio.open_connection("127.0.0.1", port, ssl=client, server_hostname=server_hostname)
        writer.close()
    finally:
        server.close()
        await server.wait_closed()


def load(path: Path) -> x509.Certificate:
    return x509.load_pem_x509_certificate(path.read_bytes())


async def test_issued_certificate_is_trusted_through_the_new_ca(tmp_path: Path) -> None:
    files = issued(tmp_path)
    await handshake(files, "grenslan")
    await handshake(files, "localhost")


async def test_other_host_names_are_rejected(tmp_path: Path) -> None:
    files = issued(tmp_path)
    with pytest.raises(ssl.SSLCertVerificationError):
        await handshake(files, "elsewhere")


def test_certificate_profile(tmp_path: Path) -> None:
    files = issued(tmp_path)
    server = load(files.certificate)
    ca = load(files.ca_certificate)
    names = server.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    assert names.get_values_for_type(x509.DNSName) == ["grenslan", "localhost"]
    assert [str(ip) for ip in names.get_values_for_type(x509.IPAddress)] == ["127.0.0.1"]
    assert server.extensions.get_extension_for_class(x509.ExtendedKeyUsage).value == x509.ExtendedKeyUsage(
        [ExtendedKeyUsageOID.SERVER_AUTH]
    )
    assert server.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is False
    assert ca.extensions.get_extension_for_class(x509.BasicConstraints).value.ca is True
    lifetime = server.not_valid_after_utc - datetime.datetime.now(datetime.UTC)
    assert datetime.timedelta(days=29) < lifetime <= datetime.timedelta(days=30)


def test_private_keys_are_owner_only(tmp_path: Path) -> None:
    files = issued(tmp_path)
    assert files.ca_key is not None
    for path in (files.private_key, files.ca_key):
        assert stat.S_IMODE(path.stat().st_mode) == 0o600
    assert stat.S_IMODE((tmp_path / "tls").stat().st_mode) == 0o700


def test_existing_files_are_never_overwritten(tmp_path: Path) -> None:
    files = issued(tmp_path)
    assert files.ca_key is not None
    before = files.ca_key.read_bytes()
    with pytest.raises(TlsIssueError, match="already exists"):
        issued(tmp_path)
    assert files.ca_key.read_bytes() == before
    assert sorted(path.name for path in (tmp_path / "tls").iterdir()) == [
        "ca.key",
        "ca.pem",
        "server.key",
        "server.pem",
    ]


async def test_existing_ca_issues_a_replacement_without_redistributing_trust(tmp_path: Path) -> None:
    first = issued(tmp_path)
    renewed = issue_certificate(
        tmp_path / "renewed",
        names=["grenslan"],
        days=30,
        ca_certificate=first.ca_certificate,
        ca_key=first.ca_key,
    )
    assert renewed.ca_key is None
    assert renewed.ca_certificate == first.ca_certificate
    await handshake(renewed, "grenslan")


def test_mismatched_ca_key_is_refused(tmp_path: Path) -> None:
    first = issued(tmp_path)
    other = make_tls_material(tmp_path)
    with pytest.raises(TlsIssueError, match="does not match"):
        issue_certificate(
            tmp_path / "renewed", names=["grenslan"], days=30,
            ca_certificate=first.ca_certificate, ca_key=other.key_file,
        )  # fmt: skip


def test_server_certificate_cannot_outlive_its_ca(tmp_path: Path) -> None:
    with pytest.raises(TlsIssueError, match="outlive"):
        issued(tmp_path, days=400, ca_days=100)


def test_non_ca_certificate_cannot_issue(tmp_path: Path) -> None:
    material = make_tls_material(tmp_path)
    with pytest.raises(TlsIssueError, match="not a CA"):
        issue_certificate(
            tmp_path / "out", names=["grenslan"], days=1, ca_certificate=material.cert_file, ca_key=material.key_file
        )


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"names": []}, id="no-names"),
        pytest.param({"names": ["bad name"]}, id="bad-name"),
        pytest.param({"names": ["grenslan:8443"]}, id="port"),
        pytest.param({"days": 0}, id="zero-days"),
        pytest.param({"days": 826}, id="too-many-days"),
        pytest.param({"ca_days": 3651}, id="too-many-ca-days"),
        pytest.param({"ca_days": None}, id="new-ca-needs-lifetime"),
    ],
)
def test_invalid_requests_are_refused_before_writing(tmp_path: Path, kwargs: dict[str, object]) -> None:
    with pytest.raises(TlsIssueError):
        issued(tmp_path, **kwargs)
    assert not (tmp_path / "tls").exists() or not any((tmp_path / "tls").iterdir())


def test_command_prints_configuration_but_never_key_material(tmp_path: Path) -> None:
    out, err = io.StringIO(), io.StringIO()
    code = tls_new(
        ["--name", "grenslan", "--days", "30", "--ca-days", "365", "--output-dir", str(tmp_path / "tls")], out, err
    )
    assert code == 0
    text = out.getvalue() + err.getvalue()
    assert f"certificate_file: {tmp_path / 'tls' / 'server.pem'}" in text
    assert "ca.pem" in text
    assert "PRIVATE KEY" not in text


def test_command_reports_problems(tmp_path: Path) -> None:
    err = io.StringIO()
    assert (
        tls_new(
            ["--name", "bad name", "--days", "30", "--ca-days", "365", "--output-dir", str(tmp_path)],
            io.StringIO(),
            err,
        )
        == 1
    )
    assert "error:" in err.getvalue()


def test_tls_new_requires_days(tmp_path: Path) -> None:
    with pytest.raises(SystemExit):
        main(["tls", "new", "--name", "grenslan", "--output-dir", str(tmp_path)])


def test_file_appearing_during_writing_is_never_overwritten(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    directory = tmp_path / "tls"
    directory.mkdir()
    (directory / "server.key").write_bytes(b"someone else's key")
    monkeypatch.setattr(Path, "exists", lambda _self: False)
    with pytest.raises(TlsIssueError, match=r"server\.key"):
        issued(tmp_path)
    assert (directory / "server.key").read_bytes() == b"someone else's key"


def test_reused_ca_must_outlive_the_certificate(tmp_path: Path) -> None:
    first = issued(tmp_path, days=5, ca_days=10)
    assert first.ca_key is not None
    with pytest.raises(TlsIssueError, match="outlive"):
        issue_certificate(
            tmp_path / "renewed",
            names=["grenslan"],
            days=30,
            ca_certificate=first.ca_certificate,
            ca_key=first.ca_key,
        )
