"""Sanitized provider configuration fixtures. No real endpoints or secrets."""

from __future__ import annotations

import copy
from typing import Any

from grenslan.config.provider_config import ImplementationSpec

LIMITS: dict[str, int] = {
    "max_input_bytes": 1_048_576,
    "max_download_bytes": 52_428_800,
    "max_output_bytes": 1_048_576,
    "max_temp_bytes": 268_435_456,
    "max_memory_bytes": 536_870_912,
    "max_cpu_ms": 60_000,
    "max_pixels": 50_000_000,
    "max_expansion_bytes": 104_857_600,
    "max_recursion": 16,
    "max_items": 100,
    "timeout_ms": 30_000,
    "max_concurrency": 8,
    "max_redirects": 5,
    "max_retries": 2,
}

_CONNECTED: dict[str, Any] = {
    "config_version": "1.0",
    "deployment_mode": "connected",
    "limits": LIMITS,
    "providers": {
        "searxng_local": {
            "family": "search",
            "implementation": "searxng",
            "enabled": True,
            "network_scope": "public_web",
            "disclosure_scope": "search_queries",
            "limits": {"timeout_ms": 10_000},
            "search": {"deployment": "internal"},
        },
        "http_direct": {
            "family": "retrieval",
            "implementation": "http",
            "enabled": True,
            "network_scope": "public_web",
            "disclosure_scope": "search_queries",
            "limits": {},
        },
    },
    "routing": {
        "search": ["searxng_local"],
        "retrieval": ["http_direct"],
        "browser": [],
        "content": [],
        "ocr": [],
        "intelligence": [],
    },
    "network_scopes": {
        "public_web": {"public_web": True, "allow_outbound_http": False, "destinations": []},
        "academic_api": {
            "public_web": False,
            "allow_outbound_http": False,
            "destinations": [{"scheme": "https", "host": "api.example.org", "port": 443}],
        },
        "local_inference": {
            "public_web": False,
            "allow_outbound_http": True,
            "destinations": [
                {"scheme": "http", "host": "inference.internal", "port": 11434, "allow_private_address": True}
            ],
        },
    },
    "disclosure_scopes": {
        "search_queries": {
            "allow_query": True,
            "allow_document_content": False,
            "allow_images": False,
            "allow_credentials": False,
            "allow_external": True,
        },
        "local_only": {
            "allow_query": True,
            "allow_document_content": True,
            "allow_images": True,
            "allow_credentials": False,
            "allow_external": False,
        },
    },
    "credential_refs": {},
    "browser_profiles": {},
    "optional_intelligence_enabled": False,
    "cache": {
        "max_bytes": 1_073_741_824,
        "artifact_lifetime_ms": 3_600_000,
        "operation_lifetime_ms": 3_600_000,
        "cursor_lifetime_ms": 900_000,
        "default_freshness_ms": 0,
        "share_eligible_public_content": False,
    },
}

IMPLEMENTATIONS: dict[str, ImplementationSpec] = {
    "searxng": ImplementationSpec(family="search"),
    "academic": ImplementationSpec(
        family="search",
        settings_schema={
            "type": "object",
            "properties": {"contact_email": {"type": "string", "minLength": 3}},
            "required": [],
            "additionalProperties": False,
        },
    ),
    "http": ImplementationSpec(family="retrieval"),
    "chromium": ImplementationSpec(family="browser"),
    "ollama": ImplementationSpec(family="intelligence"),
    "tesseract": ImplementationSpec(family="ocr"),
}


def connected_config() -> dict[str, Any]:
    """A fresh, valid connected-mode configuration that tests may mutate."""
    return copy.deepcopy(_CONNECTED)
