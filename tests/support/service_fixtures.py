"""Service configuration fixtures. Tokens and keys here are throwaway test values."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import yaml

from grenslan.server.auth import token_digest

from jwt_fixtures import ISSUER, SigningKey
from tls_fixtures import TlsMaterial

QOR_TOKEN = "qor-test-token-" + "q" * 40
ZYGOS_TOKEN = "zygos-test-token-" + "z" * 40

_BASE: dict[str, Any] = {
    "config_version": "1.0",
    "listen": {"host": "127.0.0.1", "port": 8443},
    "tls": {"certificate_file": "/run/secrets/cert.pem", "private_key_file": "/run/secrets/key.pem"},
    "ingress": {
        "allowed_hosts": ["localhost", "127.0.0.1"],
        "allowed_origins": [],
        "max_request_bytes": 65536,
        "argument_limits": {"max_string_chars": 4096, "max_array_items": 100, "max_depth": 16},
    },
    "tools": {"profile": "full", "custom_profiles": {"search_only": ["web_search", "image_search"]}},
    "credentials": {
        "qor": {
            "application_id": "qor",
            "token_sha256": token_digest(QOR_TOKEN).hex(),
            "permissions": ["web_search", "image_search", "capabilities_get"],
            "delegation": True,
        },
        "zygos": {
            "application_id": "zygos",
            "token_sha256": token_digest(ZYGOS_TOKEN).hex(),
            "permissions": ["web_search", "image_search", "capabilities_get"],
            "delegation": False,
            "profile": "search_only",
            "identity": {"user_id": "zygos-owner"},
        },
    },
    "security_events": {"max_events_per_window": 100, "window_seconds": 60},
}


def service_data(**sections: Any) -> dict[str, Any]:
    """A valid service configuration; keyword arguments replace whole sections (``None`` removes one)."""
    data = copy.deepcopy(_BASE)
    for name, value in sections.items():
        if value is None:
            data.pop(name, None)
        else:
            data[name] = value
    return data


def oauth_section(jwks_file: Path, **issuer: Any) -> dict[str, Any]:
    return {
        "resource": "https://localhost/mcp",
        "leeway_seconds": 30,
        "max_token_lifetime_seconds": 3600,
        "issuers": {
            "idp": {
                "issuer": ISSUER,
                "application_id": "qor",
                "jwks_file": str(jwks_file),
                "scopes": {"grenslan.search": ["web_search"]},
                "user_claim": "sub",
            }
            | issuer
        },
    }


def write_jwks(path: Path, *keys: SigningKey) -> Path:
    path.write_text(json.dumps({"keys": [key.public_jwk() for key in keys]}), encoding="utf-8")
    return path


def write_service_file(path: Path, data: dict[str, Any], material: TlsMaterial | None = None) -> Path:
    data = copy.deepcopy(data)
    if material is not None:
        data["tls"] = {"certificate_file": str(material.cert_file), "private_key_file": str(material.key_file)}
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return path
