"""Throwaway private CA and server certificates for HTTPS tests. Nothing here is a real credential."""

from __future__ import annotations

import datetime
import ipaddress
import ssl
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID


@dataclass(frozen=True)
class TlsMaterial:
    ca_file: Path
    cert_file: Path
    key_file: Path

    def client_context(self) -> ssl.SSLContext:
        """A verifying client context that trusts only the test CA."""
        context = ssl.create_default_context(cafile=str(self.ca_file))
        context.minimum_version = ssl.TLSVersion.TLSv1_2
        return context


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def make_tls_material(
    directory: Path, *, hostnames: tuple[str, ...] = ("localhost",), expired: bool = False
) -> TlsMaterial:
    """Write a CA, a server certificate for ``hostnames`` and 127.0.0.1, and its key.

    ``expired`` makes the server certificate's validity end an hour ago.
    """
    now = datetime.datetime.now(datetime.UTC)
    server_validity = (
        (now - datetime.timedelta(hours=2), now - datetime.timedelta(hours=1))
        if expired
        else (now - datetime.timedelta(minutes=5), now + datetime.timedelta(hours=1))
    )
    ca_key = ec.generate_private_key(ec.SECP256R1())
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(_name("Grenslan test CA"))
        .issuer_name(_name("Grenslan test CA"))
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(minutes=5))
        .not_valid_after(now + datetime.timedelta(hours=1))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(
            x509.KeyUsage(
                digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False,
                key_agreement=False, key_cert_sign=True, crl_sign=True, encipher_only=False, decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )  # fmt: skip
    server_key = ec.generate_private_key(ec.SECP256R1())
    alt_names: list[x509.GeneralName] = [x509.DNSName(name) for name in hostnames]
    alt_names.append(x509.IPAddress(ipaddress.ip_address("127.0.0.1")))
    server_cert = (
        x509.CertificateBuilder()
        .subject_name(_name(hostnames[0]))
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(server_validity[0])
        .not_valid_after(server_validity[1])
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    material = TlsMaterial(directory / "ca.pem", directory / "server.pem", directory / "server.key")
    material.ca_file.write_bytes(ca_cert.public_bytes(serialization.Encoding.PEM))
    material.cert_file.write_bytes(server_cert.public_bytes(serialization.Encoding.PEM))
    material.key_file.write_bytes(
        server_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    material.key_file.chmod(0o600)
    return material
