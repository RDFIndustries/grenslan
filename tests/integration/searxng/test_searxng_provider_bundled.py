"""The searxng provider in bundled mode, configured and started as the service does.

The configuration is validated against the built-in registry, and
``ProviderSet`` starts the real pinned SearXNG. The scope approves only an
``.invalid`` host, so no engine is resolved or contacted. The search reports
each engine as unresponsive: a failure, not an empty success. Skipped when
SearXNG is not installed (see test_bundled_searxng_process).
"""

from __future__ import annotations

import copy
import os
import time
from pathlib import Path
from typing import Any

import anyio
import pytest

from grenslan.config.provider_config import validate_provider_config
from grenslan.providers.builtin import builtin_registry
from grenslan.providers.contract import Limits, ProviderExecutionContext, SearchRequest
from grenslan.providers.runtime import ProviderSet

from config_fixtures import connected_config

pytestmark = pytest.mark.integration

PREFIX = Path(__file__).parents[3] / "local" / "searxng"


class _NeverCancelled:
    def requested(self) -> bool:
        return False

    async def wait(self) -> None:
        await anyio.sleep_forever()


def configuration(prefix: Path) -> dict[str, Any]:
    config = copy.deepcopy(connected_config())
    config["providers"] = {
        "searx": {
            "family": "search",
            "implementation": "searxng",
            "enabled": True,
            "network_scope": "searxng_engines",
            "disclosure_scope": "search_queries",
            "limits": {"timeout_ms": 10_000},
            "search": {"deployment": "internal", "upstream_engines": ["wikipedia", "duckduckgo"]},
            "adapter_settings": {
                "categories": ["general"],
                "engine_timeout_ms": 3000,
                "install_prefix": str(prefix),
                "startup_timeout_ms": 9000,
            },
        }
    }
    config["network_scopes"]["searxng_engines"] = {
        "public_web": False,
        "allow_outbound_http": False,
        "destinations": [{"scheme": "https", "host": "engine.invalid", "port": 443}],
    }
    config["routing"] = {family: [] for family in config["routing"]}
    config["routing"]["search"] = ["searx"]
    return config


async def test_the_configured_provider_starts_searches_and_reports_unreachable_engines() -> None:
    prefix = Path(os.environ.get("GRENSLAN_TEST_SEARXNG_PREFIX", PREFIX))
    if not (prefix / "venv" / "bin" / "granian").is_file():
        pytest.skip(f"SearXNG is not installed at {prefix}")
    registry = builtin_registry()
    config = validate_provider_config(configuration(prefix), registry.specs())
    registry.check(config)
    providers = await ProviderSet.start(config, registry)
    try:
        assert providers.state("searx") == "ready", providers.health("searx")
        assert providers.eligible("search", "search.query") == ("searx",)
        context = ProviderExecutionContext(
            request_id="r1", operation_id=None, provider_id="searx", deadline_monotonic=time.monotonic() + 10,
            limits=Limits(*(1_000_000,) * 10, max_redirects=0, max_retries=0), budget_handle="b1",
            resource_scope=(), resources=None,  # type: ignore[arg-type]
            cancellation=_NeverCancelled(), network_scope_id="searxng_engines", disclosure_scope_id="search_queries",
        )  # fmt: skip
        request = SearchRequest(query="grenslan provider check", category="general", max_results=5)
        outcome = await providers.provider("searx").search(request, context)
    finally:
        await providers.shutdown()
    assert outcome.outcome == "failed"
    assert sorted(issue.message.split("'")[1] for issue in outcome.issues) == ["duckduckgo", "wikipedia"]
    assert {issue.code for issue in outcome.issues} == {"network_error"}
