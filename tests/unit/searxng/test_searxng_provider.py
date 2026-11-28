"""The searxng search provider: configuration rules, request composition, result mapping and failures."""

from __future__ import annotations

import json
import time
from collections.abc import Iterator, Mapping
from typing import Any
from urllib.parse import parse_qs

import anyio
import pytest
from outbound_fixtures import FixtureServer, fixture_server

from grenslan.providers.contract import (
    LifecycleContext,
    Limits,
    ProviderExecutionContext,
    SearchRequest,
)
from grenslan.providers.registry import ConfigurationProblem, InstanceSettings
from grenslan.searxng import provider as searxng
from grenslan.searxng.provider import Reply, SearxngProvider, TransportFailure

LIMITS = {"timeout_ms": 10_000, "max_download_bytes": 1_000_000, "max_concurrency": 4}
DISCLOSURE = {
    "allow_query": True,
    "allow_document_content": False,
    "allow_images": False,
    "allow_credentials": False,
    "allow_external": True,
}
ENGINE_SCOPE = {
    "public_web": False,
    "allow_outbound_http": False,
    "destinations": [{"scheme": "https", "host": "en.wikipedia.org", "port": 443}],
}


def instance(
    *,
    deployment: str = "internal",
    engines: tuple[str, ...] = ("wikipedia", "duckduckgo"),
    adapter: Mapping[str, Any] | None = None,
    network_scope: Mapping[str, Any] | None = ENGINE_SCOPE,
    disclosure: Mapping[str, Any] | None = DISCLOSURE,
    extra: Mapping[str, Any] | None = None,
) -> InstanceSettings:
    if adapter is None:
        adapter = {"categories": ["general"], "engine_timeout_ms": 3000}
        if deployment == "internal":
            adapter = {**adapter, "install_prefix": "/opt/searxng", "startup_timeout_ms": 5000}
    settings: dict[str, Any] = {
        "family": "search",
        "implementation": "searxng",
        "enabled": True,
        "limits": {},
        "search": {"deployment": deployment, "upstream_engines": list(engines)},
        "adapter_settings": dict(adapter),
        **(extra or {}),
    }
    return InstanceSettings("searx", settings, network_scope, disclosure, LIMITS)


# Configuration


def test_a_valid_bundled_configuration_creates_a_provider() -> None:
    description = searxng.create(instance()).describe()
    assert description.implementation_id == "searxng"
    assert description.capabilities[0].categories == ("general",)


@pytest.mark.parametrize(
    ("kwargs", "location"),
    [
        pytest.param({"engines": ()}, "/search/upstream_engines", id="no-engines"),
        pytest.param({"engines": ("Wiki pedia\n",)}, "/search/upstream_engines", id="bad-engine-name"),
        pytest.param(
            {"adapter": {"categories": ["general"], "engine_timeout_ms": 10_000}},
            "/adapter_settings/engine_timeout_ms",
            id="engine-timeout-not-below-budget",
        ),
        pytest.param({"disclosure": None}, "/disclosure_scope", id="no-disclosure-scope"),
        pytest.param({"disclosure": {**DISCLOSURE, "allow_external": False}}, "/disclosure_scope", id="no-external"),
        pytest.param({"disclosure": {**DISCLOSURE, "allow_query": False}}, "/disclosure_scope", id="no-query"),
        pytest.param(
            {"adapter": {"categories": ["general"], "engine_timeout_ms": 3000}},
            "/adapter_settings/install_prefix",
            id="bundled-without-install-prefix",
        ),
        pytest.param({"network_scope": None}, "/network_scope", id="bundled-without-scope"),
        pytest.param({"network_scope": {**ENGINE_SCOPE, "public_web": True}}, "/network_scope", id="bundled-public"),
        pytest.param(
            {
                "network_scope": {
                    **ENGINE_SCOPE,
                    "allow_outbound_http": True,
                    "destinations": [{"scheme": "http", "host": "x.test", "port": 80}],
                }
            },
            "/network_scope",
            id="bundled-plain-http",
        ),
    ],
)
def test_invalid_configurations_are_reported_by_location(kwargs: dict[str, Any], location: str) -> None:
    with pytest.raises(ConfigurationProblem, match=f"^{location}: "):
        searxng.create(instance(**kwargs))


def test_a_missing_adapter_settings_section_is_reported() -> None:
    settings = instance()
    del settings.settings["adapter_settings"]  # type: ignore[attr-defined]
    with pytest.raises(ConfigurationProblem, match=r"^/adapter_settings: "):
        searxng.create(settings)


EXTERNAL = {"endpoint": {"url": "https://search.example.test/searxng"}}


def test_an_external_instance_rejects_bundled_only_settings() -> None:
    adapter = {"categories": ["general"], "engine_timeout_ms": 3000, "install_prefix": "/opt/searxng"}
    with pytest.raises(ConfigurationProblem, match=r"^/adapter_settings/install_prefix: "):
        searxng.create(instance(deployment="external", adapter=adapter, extra=EXTERNAL))


@pytest.mark.parametrize(
    ("extra", "location"),
    [
        ({"endpoint": {"url": "https://s.test/", "private_ca_ref": "corp_ca"}}, "/endpoint/private_ca_ref"),
        ({**EXTERNAL, "credential_ref": "searx_token"}, "/credential_ref"),
    ],
)
def test_unsupported_external_options_are_refused_explicitly(extra: dict[str, Any], location: str) -> None:
    with pytest.raises(ConfigurationProblem, match=f"^{location}: .*not yet supported"):
        searxng.create(instance(deployment="external", extra=extra))


def test_the_pinned_commit_matches_the_packaging_record() -> None:
    from pathlib import Path

    source = (Path(__file__).parents[3] / "packaging" / "searxng" / "SOURCE").read_text()
    assert f"commit={searxng.SEARXNG_COMMIT}\n" in source


# Requests and results, through a scripted transport


class ScriptedTransport:
    def __init__(self, reply: Reply | Exception | None = None, delay: float = 0) -> None:
        self.reply = reply
        self.delay = delay
        self.forms: list[dict[str, list[str]]] = []

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def healthy(self) -> bool:
        return True

    async def search(self, form: bytes, *, max_bytes: int) -> Reply:
        self.forms.append(parse_qs(form.decode()))
        await anyio.sleep(self.delay)
        if isinstance(self.reply, Exception):
            raise self.reply
        assert self.reply is not None
        return self.reply


def reply(results: list[Any], unresponsive: list[Any] | None = None, status: int = 200) -> Reply:
    body = {"query": "q", "results": results, "unresponsive_engines": unresponsive or []}
    return Reply(status, (), json.dumps(body).encode())


def result(url: str, *, engine: str = "wikipedia", category: str = "general", **extra: Any) -> dict[str, Any]:
    return {"url": url, "title": f"title {url}", "content": "snippet", "engine": engine, "category": category, **extra}


class _Cancellation:
    def __init__(self) -> None:
        self.event = anyio.Event()

    def requested(self) -> bool:
        return self.event.is_set()

    async def wait(self) -> None:
        await self.event.wait()


def context(timeout: float = 5.0, cancellation: _Cancellation | None = None) -> ProviderExecutionContext:
    limits = Limits(*(1_000_000,) * 10, max_redirects=0, max_retries=0)
    return ProviderExecutionContext(
        request_id="r1", operation_id=None, provider_id="searx", deadline_monotonic=time.monotonic() + timeout,
        limits=limits, budget_handle="b1", resource_scope=(), resources=None,  # type: ignore[arg-type]
        cancellation=cancellation or _Cancellation(), network_scope_id="engines", disclosure_scope_id="search_queries",
    )  # fmt: skip


def provider(transport: ScriptedTransport, categories: tuple[Any, ...] = ("general", "images")) -> SearxngProvider:
    return SearxngProvider(("wikipedia", "duckduckgo"), categories, transport, max_bytes=1_000_000)


def search(**kwargs: Any) -> SearchRequest:
    options: dict[str, Any] = {"query": "grenslan test", "category": "general", "max_results": 10}
    options.update(kwargs)
    return SearchRequest(**options)


async def test_the_query_goes_only_to_the_configured_engines() -> None:
    transport = ScriptedTransport(reply([]))
    await provider(transport).search(search(language="en-GB", safe_search="strict"), context())
    (form,) = transport.forms
    assert form == {
        "q": ["grenslan test"], "format": ["json"], "engines": ["wikipedia,duckduckgo"], "pageno": ["1"],
        "language": ["en-GB"], "safesearch": ["2"],
    }  # fmt: skip


async def test_results_keep_their_rank_and_upstream_attribution() -> None:
    results = [
        result("https://a.test/", engines=["wikipedia", "duckduckgo"], publishedDate="2026-01-02"),
        result("https://news.test/", category="news"),
        result("https://b.test/", engine="duckduckgo"),
    ]
    outcome = await provider(ScriptedTransport(reply(results))).search(search(), context())
    assert outcome.outcome == "completed"
    assert outcome.value is not None
    first, second = outcome.value.items
    assert (first.original_rank, first.url, first.upstream_engine) == (1, "https://a.test/", "wikipedia")
    assert dict(first.category_metadata) == {"upstream_engines": "duckduckgo,wikipedia", "published_date": "2026-01-02"}
    assert (second.original_rank, second.upstream_engine) == (3, "duckduckgo")


async def test_results_without_a_web_url_are_dropped() -> None:
    results = [result("javascript:alert(1)"), result("/relative"), result("https://ok.test/"), {"url": 5}, "junk"]
    outcome = await provider(ScriptedTransport(reply(results))).search(search(), context())
    assert outcome.value is not None
    assert [item.url for item in outcome.value.items] == ["https://ok.test/"]


async def test_results_are_limited_to_max_results() -> None:
    results = [result(f"https://{n}.test/") for n in range(5)]
    outcome = await provider(ScriptedTransport(reply(results))).search(search(max_results=2), context())
    assert outcome.value is not None
    assert len(outcome.value.items) == 2


async def test_image_results_carry_image_fields() -> None:
    image = result(
        "https://page.test/", category="images", img_src="https://img.test/a.jpg",
        thumbnail_src="https://img.test/t.jpg", resolution="1920 x 1080",
    )  # fmt: skip
    outcome = await provider(ScriptedTransport(reply([image]))).search(search(category="images"), context())
    assert outcome.value is not None
    (item,) = outcome.value.items
    assert (item.image_url, item.thumbnail_url, item.source_page_url) == (
        "https://img.test/a.jpg", "https://img.test/t.jpg", "https://page.test/",
    )  # fmt: skip
    assert (item.width, item.height) == (1920, 1080)


async def test_constraint_dispositions_are_reported() -> None:
    outcome = await provider(ScriptedTransport(reply([]))).search(
        search(language="not a tag", region="DE", include_domains=("a.test",)), context()
    )
    assert outcome.value is not None
    dispositions = {d.name: d.status for d in outcome.value.constraints}
    assert dispositions == {
        "category": "locally_applied",
        "language": "unsupported",
        "region": "unsupported",
        "include_domains": "unsupported",
    }


async def test_an_empty_result_with_responsive_engines_is_a_completed_empty_result() -> None:
    outcome = await provider(ScriptedTransport(reply([]))).search(search(), context())
    assert outcome.outcome == "completed"
    assert outcome.value is not None
    assert outcome.value.items == ()


async def test_some_unresponsive_engines_make_the_result_partial() -> None:
    transport = ScriptedTransport(reply([result("https://a.test/")], [["duckduckgo", "timeout"]]))
    outcome = await provider(transport).search(search(), context())
    assert outcome.outcome == "partial"
    assert [issue.code for issue in outcome.issues] == ["network_error"]
    assert "duckduckgo" in outcome.issues[0].message


async def test_all_engines_unresponsive_without_results_is_a_failure() -> None:
    unresponsive = [["wikipedia", "HTTP connection error"], ["duckduckgo", "timeout"]]
    outcome = await provider(ScriptedTransport(reply([], unresponsive))).search(search(), context())
    assert (outcome.outcome, outcome.value) == ("failed", None)
    assert len(outcome.issues) == 2


@pytest.mark.parametrize(
    ("status", "headers", "code"),
    [
        (429, (("Retry-After", "30"),), "rate_limited"),
        (403, (), "access_restricted"),
        (500, (), "provider_unavailable"),
    ],
)
async def test_http_failures_are_classified(status: int, headers: tuple[tuple[str, str], ...], code: str) -> None:
    transport = ScriptedTransport(Reply(status, headers, b""))
    outcome = await provider(transport).search(search(), context())
    assert outcome.outcome == "failed"
    assert outcome.issues[0].code == code
    if code == "rate_limited":
        assert outcome.issues[0].retry_after_ms == 30_000


@pytest.mark.parametrize("body", [b"not json", b"[]", b'{"results": 5}'])
async def test_malformed_responses_are_failures(body: bytes) -> None:
    outcome = await provider(ScriptedTransport(Reply(200, (), body))).search(search(), context())
    assert (outcome.outcome, outcome.issues[0].code) == ("failed", "provider_unavailable")


async def test_transport_failures_are_reported() -> None:
    failure = TransportFailure("network_error", "the SearXNG instance could not be reached", retryable=True)
    outcome = await provider(ScriptedTransport(failure)).search(search(), context())
    assert (outcome.outcome, outcome.issues[0].code) == ("failed", "network_error")


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"category": "news"}, "not configured"),
        ({"continuation": "c1"}, "continuation"),
        ({"freshness": "cache_only"}, "cache"),
    ],
)
async def test_unsupported_requests_are_refused_without_sending(kwargs: dict[str, Any], message: str) -> None:
    transport = ScriptedTransport(reply([]))
    outcome = await provider(transport).search(search(**kwargs), context())
    assert (outcome.outcome, outcome.issues[0].code) == ("failed", "unsupported_capability")
    assert message in outcome.issues[0].message
    assert transport.forms == []


async def test_the_deadline_bounds_the_search() -> None:
    outcome = await provider(ScriptedTransport(reply([]), delay=5)).search(search(), context(timeout=0.2))
    assert (outcome.outcome, outcome.issues[0].code) == ("timed_out", "timeout")


async def test_an_expired_deadline_sends_nothing() -> None:
    transport = ScriptedTransport(reply([]))
    outcome = await provider(transport).search(search(), context(timeout=-1))
    assert outcome.outcome == "timed_out"
    assert transport.forms == []


async def test_cancellation_stops_the_search() -> None:
    cancellation = _Cancellation()
    transport = ScriptedTransport(reply([]), delay=5)

    async def cancel_soon() -> None:
        await anyio.sleep(0.1)
        cancellation.event.set()

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(cancel_soon)
        outcome = await provider(transport).search(search(), context(cancellation=cancellation))
    assert (outcome.outcome, outcome.issues[0].code) == ("cancelled", "cancelled")


# External instance through outbound enforcement


@pytest.fixture
def instance_server() -> Iterator[FixtureServer]:
    with fixture_server() as running:
        running.routes.responses["/searxng/search"] = (
            200, [("Content-Type", "application/json")], json.dumps({"results": [result("https://a.test/")]}).encode(),
        )  # fmt: skip
        running.routes.responses["/searxng/healthz"] = (200, [], b"OK")
        yield running


def external(server: FixtureServer, host: str = "127.0.0.1") -> SearxngProvider:
    scope = {
        "public_web": False,
        "allow_outbound_http": True,
        "destinations": [{"scheme": "http", "host": "127.0.0.1", "port": server.port, "allow_private_address": True}],
    }
    endpoint = {"endpoint": {"url": f"http://{host}:{server.port}/searxng"}}
    return searxng.create(instance(deployment="external", network_scope=scope, extra=endpoint))


def lifecycle() -> LifecycleContext:
    return LifecycleContext(provider_id="searx", deadline_monotonic=time.monotonic() + 5, cancellation=_Cancellation())


async def test_an_external_instance_is_searched_by_post_through_outbound_enforcement(
    instance_server: FixtureServer,
) -> None:
    searx = external(instance_server)
    assert (await searx.initialize(lifecycle())).value.state == "ready"  # type: ignore[union-attr]
    try:
        outcome = await searx.search(search(), context())
    finally:
        await searx.shutdown(lifecycle())
    assert outcome.outcome == "completed"
    seen = instance_server.routes.seen[-1]
    assert (seen.method, seen.path) == ("POST", "/searxng/search")
    assert parse_qs(seen.body.decode())["q"] == ["grenslan test"]
    assert "grenslan" not in seen.path


async def test_an_external_endpoint_outside_its_scope_is_refused(instance_server: FixtureServer) -> None:
    searx = external(instance_server, host="localhost")
    await searx.initialize(lifecycle())
    try:
        outcome = await searx.search(search(), context())
    finally:
        await searx.shutdown(lifecycle())
    assert (outcome.outcome, outcome.issues[0].code) == ("failed", "access_restricted")
    assert instance_server.routes.seen == []


def test_the_provider_configuration_sample_passes_check_config() -> None:
    from pathlib import Path

    from grenslan.config.loader import load_provider_config_file
    from grenslan.providers.builtin import builtin_registry

    registry = builtin_registry()
    sample = Path(__file__).parents[3] / "examples" / "providers.yaml"
    config = load_provider_config_file(sample, registry.specs())
    registry.check(config)
    assert config.routes("search") == ("searxng_bundled",)
