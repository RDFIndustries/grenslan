"""Server certificate validation by clients, and certificate replacement by restart (AD-428, F-G03)."""

from __future__ import annotations

import asyncio
import ssl
from pathlib import Path

import pytest

from ingress_fixtures import running_server
from tls_fixtures import TlsMaterial, make_tls_material

pytestmark = pytest.mark.integration


async def handshake(port: int, context: ssl.SSLContext, server_hostname: str = "localhost") -> bytes:
    """Complete a TLS handshake and return the server certificate in DER form."""
    _, writer = await asyncio.open_connection("127.0.0.1", port, ssl=context, server_hostname=server_hostname)
    try:
        certificate = writer.get_extra_info("ssl_object").getpeercert(binary_form=True)
    finally:
        writer.close()
    assert certificate is not None
    return bytes(certificate)


async def test_expired_server_certificate_is_rejected(tmp_path: Path) -> None:
    material = make_tls_material(tmp_path, expired=True)
    async with running_server(material) as server:
        with pytest.raises(ssl.SSLCertVerificationError, match="expired"):
            await handshake(server.port, material.client_context())


async def test_wrong_hostname_is_rejected(tmp_path: Path) -> None:
    material = make_tls_material(tmp_path)
    async with running_server(material) as server:
        with pytest.raises(ssl.SSLCertVerificationError, match="match"):
            await handshake(server.port, material.client_context(), server_hostname="other.example")


async def test_replaced_certificate_is_served_after_controlled_restart(tmp_path: Path) -> None:
    first = make_tls_material(tmp_path)
    old_ca = tmp_path / "old-ca.pem"
    old_ca.write_bytes(first.ca_file.read_bytes())
    async with running_server(first) as server:
        before = await handshake(server.port, first.client_context())

    # New material is written over the same mounted paths; only a restart follows.
    replacement = make_tls_material(tmp_path)
    assert (replacement.cert_file, replacement.key_file) == (first.cert_file, first.key_file)
    async with running_server(replacement) as server:
        after = await handshake(server.port, replacement.client_context())
        with pytest.raises(ssl.SSLCertVerificationError):
            await handshake(server.port, TlsMaterial(old_ca, first.cert_file, first.key_file).client_context())
    assert after != before
