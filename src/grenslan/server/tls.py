"""Directly served TLS for every consumer-facing listener (AD-428).

TLS 1.2 is the minimum and TLS 1.3 is preferred where both peers support it.
Compression and renegotiation are disabled. Certificate and key files are read
at startup; an unusable pair stops the service rather than admitting traffic.
"""

from __future__ import annotations

import ssl
from pathlib import Path


class TlsConfigError(ValueError):
    """The configured certificate or private key cannot be used."""


def server_ssl_context(cert_file: Path, key_file: Path) -> ssl.SSLContext:
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version = ssl.TLSVersion.TLSv1_2
    context.options |= ssl.OP_NO_COMPRESSION | ssl.OP_NO_RENEGOTIATION | ssl.OP_CIPHER_SERVER_PREFERENCE
    if not cert_file.is_file():
        raise TlsConfigError("TLS certificate file is not readable")
    if not key_file.is_file():
        raise TlsConfigError("TLS private key file is not readable")
    try:
        context.load_cert_chain(certfile=cert_file, keyfile=key_file)
    except (OSError, ssl.SSLError):
        raise TlsConfigError("TLS certificate and private key cannot be loaded as a matching pair") from None
    return context
