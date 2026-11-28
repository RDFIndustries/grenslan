"""SearXNG settings generated from Grenslan configuration; never edited by hand (SEARXNG-EGRESS.md S3).

The output is JSON, which SearXNG reads as YAML, so no configured value can
change the document's structure. It keeps only the configured engines
(``use_default_settings.engines.keep_only``: other engines are not loaded at
all), replaces the plugin list with an empty one (nothing downloads at
start), serves the JSON format only, turns off the limiter, image proxy and
metrics, and sends all outgoing requests to the confined process's relay.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence

ENGINE_NAME = re.compile(r"^[a-z0-9][a-z0-9 ._-]{0,63}$")


def render_settings(
    *, engines: Sequence[str], secret_key: str, relay_port: int, request_timeout: float, max_request_timeout: float
) -> str:
    if not engines:
        raise ValueError("at least one engine is required")
    for name in engines:
        if not ENGINE_NAME.fullmatch(name):
            raise ValueError(f"invalid engine name {name!r}")
    if len(set(engines)) != len(engines):
        raise ValueError("engine names must be unique")
    if not 0 < request_timeout <= max_request_timeout:
        raise ValueError("request_timeout must be positive and at most max_request_timeout")
    settings = {
        "use_default_settings": {"engines": {"keep_only": list(engines)}},
        "general": {"enable_metrics": False},
        "server": {
            "secret_key": secret_key,
            "limiter": False,
            "public_instance": False,
            "image_proxy": False,
            "method": "GET",
        },
        "search": {"formats": ["json"]},
        "plugins": {},
        "outgoing": {
            "request_timeout": request_timeout,
            "max_request_timeout": max_request_timeout,
            "enable_http2": False,
            "verify": True,
            "proxies": {"all://": [f"http://127.0.0.1:{relay_port}"]},
        },
    }
    return json.dumps(settings, indent=2) + "\n"
