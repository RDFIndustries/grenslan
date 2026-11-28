"""The real bundled SearXNG process, confined, with its traffic observed at the egress proxy.

Needs SearXNG installed by packaging/searxng/install.sh, at
``GRENSLAN_TEST_SEARXNG_PREFIX`` or ``local/searxng``, and unprivileged
namespaces. Otherwise the test is skipped and the behaviour is unverified in
that environment. Nothing reaches the internet: the resolver maps the one
approved engine host to loopback, where nothing serves port 443.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anyio
import httpcore2
import pytest
from outbound_fixtures import StaticResolver

from grenslan.network.policy import NetworkPolicy
from grenslan.searxng.bundled import BundledSearxng, BundledSettings

pytestmark = pytest.mark.integration

PREFIX = Path(os.environ.get("GRENSLAN_TEST_SEARXNG_PREFIX", Path(__file__).parents[3] / "local" / "searxng"))


@pytest.fixture
def prefix() -> Path:
    if not (PREFIX / "venv" / "bin" / "granian").is_file():
        pytest.skip(f"SearXNG is not installed at {PREFIX}")
    return PREFIX


async def test_searxng_reaches_only_approved_destinations_through_the_proxy(
    prefix: Path, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    policy = NetworkPolicy.from_scope(
        {
            "destinations": [
                {"scheme": "https", "host": "en.wikipedia.org", "port": 443, "allow_private_address": True}
            ],
            "public_web": False,
            "allow_outbound_http": False,
        }
    )
    resolver = StaticResolver({"en.wikipedia.org": ["127.0.0.1"], "html.duckduckgo.com": ["127.0.0.1"]})
    settings = BundledSettings(
        install_prefix=prefix, engines=("wikipedia", "duckduckgo"), request_timeout=2.0, max_request_timeout=4.0,
        threads=4, startup_timeout=60.0, tunnel_connect_timeout=2.0, tunnel_idle_timeout=5.0, max_tunnels=8,
        runtime_parent=tmp_path,
    )  # fmt: skip
    bundled = BundledSearxng(settings, policy, resolver=resolver)
    await bundled.start()
    try:
        runtime = bundled.socket_path.parent
        assert sorted(path.name for path in runtime.iterdir()) == ["egress.sock", "searxng.sock", "settings.yml"]
        assert oct(runtime.stat().st_mode & 0o777) == "0o700"
        async with httpcore2.AsyncConnectionPool(uds=str(bundled.socket_path)) as pool:
            with anyio.fail_after(30):
                response = await pool.request("GET", "http://searxng/search?q=grenslan+probe&format=json")
        body = json.loads(response.content)
        assert response.status == 200
        assert {name for name, _ in body["unresponsive_engines"]} == {"wikipedia", "duckduckgo"}
    finally:
        await bundled.stop()
    # The approved host was resolved by the proxy: the tunnel passed the policy.
    # The unapproved engine's host never was: its tunnel was refused first.
    assert "en.wikipedia.org" in resolver.lookups
    assert "html.duckduckgo.com" not in resolver.lookups
    assert "html.duckduckgo.com:443 denied" in caplog.text
    assert list(tmp_path.iterdir()) == []
