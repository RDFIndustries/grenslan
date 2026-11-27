"""Directly served TLS configuration (AD-428, F03)."""

from __future__ import annotations

import ssl
from pathlib import Path

import pytest

from grenslan.server.tls import TlsConfigError, server_ssl_context

from tls_fixtures import make_tls_material


def test_context_requires_tls_1_2_or_later(tmp_path: Path) -> None:
    material = make_tls_material(tmp_path)
    context = server_ssl_context(material.cert_file, material.key_file)
    assert context.minimum_version == ssl.TLSVersion.TLSv1_2
    assert context.maximum_version in (ssl.TLSVersion.MAXIMUM_SUPPORTED, ssl.TLSVersion.TLSv1_3)


def test_context_disables_compression_and_renegotiation(tmp_path: Path) -> None:
    material = make_tls_material(tmp_path)
    context = server_ssl_context(material.cert_file, material.key_file)
    assert context.options & ssl.OP_NO_COMPRESSION
    assert context.options & ssl.OP_NO_RENEGOTIATION


def test_missing_certificate_fails_startup(tmp_path: Path) -> None:
    material = make_tls_material(tmp_path)
    with pytest.raises(TlsConfigError, match="certificate"):
        server_ssl_context(tmp_path / "absent.pem", material.key_file)


def test_mismatched_key_fails_startup(tmp_path: Path) -> None:
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first = make_tls_material(tmp_path / "a")
    second = make_tls_material(tmp_path / "b")
    with pytest.raises(TlsConfigError):
        server_ssl_context(first.cert_file, second.key_file)
