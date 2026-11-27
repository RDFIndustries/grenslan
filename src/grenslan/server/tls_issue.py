"""Issue a private CA and a server certificate for deployments without their own issuer (AD-428).

Grenslan serves whatever certificate and key files the operator configures.
This module creates them when no other issuer is available: an ECDSA P-256 CA
(or an existing CA supplied by the operator) signs an ECDSA P-256 server
certificate for the given host names and IP addresses. Consumers trust the CA
certificate; nothing here weakens verification.

Validity is always stated by the caller, within fixed upper bounds. Existing
files are never overwritten, and private keys are created owner-only from the
start, never written to a world-readable file first.
"""

from __future__ import annotations

import datetime
import ipaddress
import os
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa
from cryptography.hazmat.primitives.asymmetric.types import CertificateIssuerPrivateKeyTypes
from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID

from grenslan.config.service_config import is_host

MAX_SERVER_DAYS = 825
MAX_CA_DAYS = 3650
# Tolerates small clock differences between Grenslan and its consumers.
_BACKDATE = datetime.timedelta(minutes=5)


class TlsIssueError(ValueError):
    """The request cannot be issued; nothing was written."""


@dataclass(frozen=True)
class IssuedFiles:
    certificate: Path
    private_key: Path
    ca_certificate: Path
    ca_key: Path | None  # None when an existing CA signed the certificate


def _general_names(names: Sequence[str]) -> list[x509.GeneralName]:
    if not names:
        raise TlsIssueError("at least one host name or IP address is required")
    result: list[x509.GeneralName] = []
    for name in dict.fromkeys(name.lower() for name in names):
        if not is_host(name):
            raise TlsIssueError("each name must be a host name or IP address without a port")
        try:
            result.append(x509.IPAddress(ipaddress.ip_address(name)))
        except ValueError:
            result.append(x509.DNSName(name))
    return result


def _check_days(days: int, maximum: int, what: str) -> datetime.timedelta:
    if not 1 <= days <= maximum:
        raise TlsIssueError(f"{what} validity must be 1 to {maximum} days")
    return datetime.timedelta(days=days)


def _name(common_name: str) -> x509.Name:
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])


def _key_usage(*, certificate_signing: bool) -> x509.KeyUsage:
    return x509.KeyUsage(
        digital_signature=True, content_commitment=False, key_encipherment=False, data_encipherment=False,
        key_agreement=False, key_cert_sign=certificate_signing, crl_sign=certificate_signing,
        encipher_only=False, decipher_only=False,
    )  # fmt: skip


def _new_ca(
    now: datetime.datetime, lifetime: datetime.timedelta
) -> tuple[ec.EllipticCurvePrivateKey, x509.Certificate]:
    key = ec.generate_private_key(ec.SECP256R1())
    subject = _name(f"Grenslan private CA {now:%Y-%m-%d} {secrets.token_hex(4)}")
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _BACKDATE)
        .not_valid_after(now + lifetime)
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .add_extension(_key_usage(certificate_signing=True), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .sign(key, hashes.SHA256())
    )
    return key, certificate


def _load_ca(certificate_path: Path, key_path: Path) -> tuple[CertificateIssuerPrivateKeyTypes, x509.Certificate]:
    try:
        certificate = x509.load_pem_x509_certificate(certificate_path.read_bytes())
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    except (OSError, ValueError, TypeError):
        raise TlsIssueError("the CA certificate or key cannot be read as unencrypted PEM") from None
    if not isinstance(key, ec.EllipticCurvePrivateKey | rsa.RSAPrivateKey):
        raise TlsIssueError("the CA key must be an EC or RSA key")
    try:
        constraints = certificate.extensions.get_extension_for_class(x509.BasicConstraints).value
    except x509.ExtensionNotFound:
        constraints = None
    if constraints is None or not constraints.ca:
        raise TlsIssueError("the supplied certificate is not a CA certificate")
    public = serialization.PublicFormat.SubjectPublicKeyInfo
    if key.public_key().public_bytes(serialization.Encoding.DER, public) != certificate.public_key().public_bytes(
        serialization.Encoding.DER, public
    ):
        raise TlsIssueError("the CA key does not match the CA certificate")
    return key, certificate


def _write_new(path: Path, data: bytes, mode: int) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(data)


def issue_certificate(
    output_dir: Path,
    *,
    names: Sequence[str],
    days: int,
    ca_days: int | None = None,
    ca_certificate: Path | None = None,
    ca_key: Path | None = None,
) -> IssuedFiles:
    """Write ``server.pem`` and ``server.key`` (and ``ca.pem``, ``ca.key`` for a new CA) into ``output_dir``."""
    alt_names = _general_names(names)
    lifetime = _check_days(days, MAX_SERVER_DAYS, "server certificate")
    now = datetime.datetime.now(datetime.UTC)
    issuer_key: CertificateIssuerPrivateKeyTypes
    new_ca_key: ec.EllipticCurvePrivateKey | None = None
    if ca_certificate is not None and ca_key is not None:
        if ca_days is not None:
            raise TlsIssueError("CA validity applies only when a new CA is created")
        issuer_key, issuer = _load_ca(ca_certificate, ca_key)
    elif ca_certificate is not None or ca_key is not None:
        raise TlsIssueError("an existing CA needs both its certificate and its key")
    elif ca_days is None:
        raise TlsIssueError("a new CA needs its validity in days")
    else:
        ca_lifetime = _check_days(ca_days, MAX_CA_DAYS, "CA")
        if lifetime > ca_lifetime:
            raise TlsIssueError("the server certificate cannot outlive its CA")
        new_ca_key, issuer = _new_ca(now, ca_lifetime)
        issuer_key = new_ca_key
    if now + lifetime > issuer.not_valid_after_utc:
        raise TlsIssueError("the server certificate cannot outlive its CA")

    key = ec.generate_private_key(ec.SECP256R1())
    first = alt_names[0].value
    certificate = (
        x509.CertificateBuilder()
        .subject_name(_name(str(first)))
        .issuer_name(issuer.subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - _BACKDATE)
        .not_valid_after(now + lifetime)
        .add_extension(x509.SubjectAlternativeName(alt_names), critical=False)
        .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .add_extension(_key_usage(certificate_signing=False), critical=True)
        .add_extension(x509.SubjectKeyIdentifier.from_public_key(key.public_key()), critical=False)
        .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer.public_key()), critical=False)  # type: ignore[arg-type]
        .sign(issuer_key, hashes.SHA256())
    )

    files = IssuedFiles(
        certificate=output_dir / "server.pem",
        private_key=output_dir / "server.key",
        ca_certificate=ca_certificate if ca_certificate is not None else output_dir / "ca.pem",
        ca_key=None if new_ca_key is None else output_dir / "ca.key",
    )
    pem = serialization.Encoding.PEM
    outputs: list[tuple[Path, bytes, int]] = [
        (files.certificate, certificate.public_bytes(pem), 0o644),
        (files.private_key, _private_pem(key), 0o600),
    ]
    if new_ca_key is not None and files.ca_key is not None:
        outputs += [
            (files.ca_certificate, issuer.public_bytes(pem), 0o644),
            (files.ca_key, _private_pem(new_ca_key), 0o600),
        ]
    existing = [path for path, _, _ in outputs if path.exists()]
    if existing:
        raise TlsIssueError(f"{existing[0]} already exists; nothing was written")
    output_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
    for path, data, mode in outputs:
        try:
            _write_new(path, data, mode)
        except FileExistsError:
            raise TlsIssueError(f"{path} was created by something else while writing; check the directory") from None
    return files


def _private_pem(key: ec.EllipticCurvePrivateKey) -> bytes:
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
