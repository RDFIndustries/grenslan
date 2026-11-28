"""The ``searxng`` search provider: bundled (``deployment: internal``) or an approved external instance.

Configuration (provider configuration schema, ``search`` and ``adapter_settings``):

- ``search.upstream_engines``: required, non-empty. These are the only engines
  queried. In bundled mode no other engine is even loaded (S3). For an
  external instance each request names them, so the instance's other engines
  are not used.
- ``adapter_settings.categories``: the Grenslan categories these engines serve.
  Results are kept only if SearXNG reports the requested category for them.
- ``adapter_settings.engine_timeout_ms``: SearXNG's per-engine timeout. It must
  be below the instance's ``timeout_ms``.
- ``adapter_settings.default_safe_search`` (``off``, ``moderate``, ``strict``)
  and ``default_language`` (``auto`` or a tag such as ``en`` or ``en-GB``):
  optional. When set, they are sent with every search that does not specify
  its own value. A value in the request takes precedence. When unset, the
  instance's own defaults apply.
- Bundled mode also needs ``adapter_settings.install_prefix`` (from
  ``packaging/searxng/install.sh``) and ``startup_timeout_ms``. It needs a
  network scope listing the engines' https destinations, without
  ``public_web``.

The disclosure scope must allow queries to external destinations, because
every search sends the query to upstream engines. The query is sent by POST,
so it does not appear in URLs or access logs. No user, agent or application
context is sent.
"""

from __future__ import annotations

import datetime
import json
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol
from urllib.parse import urlencode, urlsplit

import anyio
import httpcore2

from grenslan import __version__
from grenslan.network.client import OutboundClient, outbound_ssl_context
from grenslan.network.errors import OutboundError
from grenslan.network.policy import NetworkPolicy
from grenslan.providers.contract import (
    CapabilityDeclaration,
    Category,
    ConstraintDisposition,
    Discovery,
    Health,
    Issue,
    IssueCode,
    LifecycleContext,
    Outcome,
    ProviderDescription,
    ProviderExecutionContext,
    ProviderResult,
    SearchRequest,
    SearchResult,
)
from grenslan.providers.registry import ConfigurationProblem, Implementation, InstanceSettings
from grenslan.searxng.bundled import BundledSearxng, BundledSettings, SearxngUnavailable
from grenslan.searxng.settings import ENGINE_NAME

IMPLEMENTATION_ID = "searxng"
MANIFEST = Path(__file__).with_name("manifest.json")
# The SearXNG build this provider is written for; packaging/searxng/SOURCE.
SEARXNG_COMMIT = "df67eb6c2608c5b2f909ed7c42b0a4bd3823f78f"

# Grenslan category to the SearXNG category its results carry.
CATEGORIES: Mapping[str, str] = {
    "general": "general",
    "news": "news",
    "images": "images",
    "video": "videos",
    "academic": "science",
    "software": "it",
    "maps": "map",
}
LANGUAGE = re.compile(r"^[a-z]{2,3}(-[A-Z]{2})?$")
SafeSearch = Literal["off", "moderate", "strict"]
SAFE_SEARCH: Mapping[SafeSearch, str] = {"off": "0", "moderate": "1", "strict": "2"}
RESOLUTION = re.compile("^\\s*(\\d{1,6})\\s*[x\u00d7]\\s*(\\d{1,6})\\s*$")
MAX_URL_LENGTH = 8192
UNSUPPORTED_CONSTRAINTS = (
    "region",
    "date_from",
    "date_to",
    "include_domains",
    "exclude_domains",
    "file_types",
    "min_width",
    "min_height",
)
LIMITATIONS = (
    "Results come from the configured upstream engines; their availability, ranking and coverage vary.",
    "Category filtering keeps results SearXNG labels with the requested category; it is applied locally.",
    "Region, date, domain, file-type and image-size constraints are not supported.",
    "Continuation is not supported; each search returns the first page.",
)

SETTINGS_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["categories", "engine_timeout_ms"],
    "properties": {
        "categories": {
            "type": "array",
            "minItems": 1,
            "uniqueItems": True,
            "items": {"enum": sorted(CATEGORIES)},
        },
        "engine_timeout_ms": {"type": "integer", "minimum": 100},
        "install_prefix": {"type": "string", "pattern": "^/", "maxLength": 4096},
        "startup_timeout_ms": {"type": "integer", "minimum": 1000},
        "default_safe_search": {"enum": sorted(SAFE_SEARCH)},
        "default_language": {"type": "string", "pattern": "^(auto|[a-z]{2,3}(-[A-Z]{2})?)$"},
    },
}


@dataclass(frozen=True, slots=True)
class Reply:
    status: int
    headers: tuple[tuple[str, str], ...]
    body: bytes

    def header(self, name: str) -> str | None:
        return next((value for key, value in self.headers if key.lower() == name.lower()), None)


class TransportFailure(Exception):
    def __init__(self, code: IssueCode, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.issue = Issue(code=code, message=message, retryable=retryable)


class Transport(Protocol):
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def healthy(self) -> bool: ...
    async def search(self, form: bytes, *, max_bytes: int) -> Reply: ...


FORM_HEADERS = (("Content-Type", "application/x-www-form-urlencoded"), ("Accept", "application/json"))


class BundledTransport:
    """The bundled, confined SearXNG process, reached over its Unix socket."""

    def __init__(self, bundled: BundledSearxng) -> None:
        self._bundled = bundled
        self._pool: httpcore2.AsyncConnectionPool | None = None

    async def start(self) -> None:
        await self._bundled.start()
        self._pool = httpcore2.AsyncConnectionPool(uds=str(self._bundled.socket_path), retries=0)

    async def stop(self) -> None:
        if self._pool is not None:
            await self._pool.aclose()
            self._pool = None
        await self._bundled.stop()

    async def healthy(self) -> bool:
        return self._pool is not None and await self._bundled.healthy()

    async def search(self, form: bytes, *, max_bytes: int) -> Reply:
        if self._pool is None:
            raise TransportFailure("provider_unavailable", "bundled SearXNG is not running", retryable=True)
        headers = [(name.encode(), value.encode()) for name, value in FORM_HEADERS]
        try:
            async with self._pool.stream("POST", "http://searxng/search", headers=headers, content=form) as response:
                body = bytearray()
                async for chunk in response.aiter_stream():
                    body.extend(chunk)
                    if len(body) > max_bytes:
                        raise TransportFailure("resource_limit", "the SearXNG response is too large", retryable=False)
                return Reply(
                    response.status,
                    tuple((key.decode("latin-1"), value.decode("latin-1")) for key, value in response.headers),
                    bytes(body),
                )
        except (httpcore2.NetworkError, httpcore2.ProtocolError, httpcore2.TimeoutException) as error:
            raise TransportFailure("provider_unavailable", "bundled SearXNG did not answer", retryable=True) from error


class ExternalTransport:
    """An approved external SearXNG instance, reached through outbound enforcement."""

    def __init__(self, endpoint: str, policy: NetworkPolicy, *, timeout: float) -> None:
        self._base = endpoint.rstrip("/")
        self._policy = policy
        self._timeout = timeout
        self._client: OutboundClient | None = None

    async def start(self) -> None:
        self._client = OutboundClient(self._policy, ssl_context=outbound_ssl_context(), max_redirects=0)

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    def _require(self) -> OutboundClient:
        if self._client is None:
            raise TransportFailure("provider_unavailable", "the provider is not initialized", retryable=True)
        return self._client

    async def healthy(self) -> bool:
        try:
            response = await self._require().request("GET", f"{self._base}/healthz", timeout=self._timeout)
        except (OutboundError, TransportFailure):
            return False
        return response.status == 200

    async def search(self, form: bytes, *, max_bytes: int) -> Reply:
        client = self._require()
        try:
            client_reply = await client.request(
                "POST", f"{self._base}/search", headers=FORM_HEADERS, body=form, timeout=self._timeout
            )
        except OutboundError as error:
            raise _outbound_failure(error) from error
        if len(client_reply.body) > max_bytes:
            raise TransportFailure("resource_limit", "the SearXNG response is too large", retryable=False)
        return Reply(client_reply.status, client_reply.headers, client_reply.body)


def _outbound_failure(error: OutboundError) -> TransportFailure:
    if error.kind == "denied":
        return TransportFailure(
            "access_restricted", "the SearXNG endpoint is not an approved destination", retryable=False
        )
    if error.kind == "timeout":
        return TransportFailure("timeout", "the SearXNG instance did not respond in time", retryable=True)
    if error.kind == "too_large":
        return TransportFailure("resource_limit", "the SearXNG response is too large", retryable=False)
    if error.kind == "tls":
        return TransportFailure("network_error", "TLS verification of the SearXNG instance failed", retryable=False)
    return TransportFailure(
        "network_error", f"the SearXNG instance could not be reached ({error.kind})", retryable=True
    )


def _now() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def _http_url(value: Any) -> str | None:
    if not isinstance(value, str) or len(value) > MAX_URL_LENGTH:
        return None
    parts = urlsplit(value)
    return value if parts.scheme in ("http", "https") and parts.netloc else None


def _text(value: Any) -> str | None:
    return value if isinstance(value, str) and value.strip() else None


def _short(value: Any) -> str:
    text = value if isinstance(value, str) else "unknown reason"
    return "".join(character for character in text if character.isprintable())[:120]


def _discovery(rank: int, result: Mapping[str, Any], category: Category) -> Discovery | None:
    url = _http_url(result.get("url"))
    if url is None:
        return None
    engines = [name for name in result.get("engines", ()) if isinstance(name, str)]
    metadata: list[tuple[str, str | int | float | bool | None]] = []
    if len(engines) > 1:
        metadata.append(("upstream_engines", ",".join(sorted(engines))))
    published = _text(result.get("publishedDate"))
    if published is not None:
        metadata.append(("published_date", published))
    fields: dict[str, Any] = {
        "original_rank": rank,
        "url": url,
        "title": _text(result.get("title")),
        "snippet": _text(result.get("content")),
        "upstream_engine": _text(result.get("engine")),
        "category_metadata": tuple(metadata),
    }
    if category == "images":
        fields["image_url"] = _http_url(result.get("img_src"))
        fields["thumbnail_url"] = _http_url(result.get("thumbnail_src"))
        fields["source_page_url"] = url
        size = RESOLUTION.match(result["resolution"]) if isinstance(result.get("resolution"), str) else None
        if size is not None:
            fields["width"], fields["height"] = int(size.group(1)), int(size.group(2))
    return Discovery(**fields)


class SearxngProvider:
    def __init__(
        self,
        engines: tuple[str, ...],
        categories: tuple[Category, ...],
        transport: Transport,
        max_bytes: int,
        *,
        default_safe_search: SafeSearch | None = None,
        default_language: str | None = None,
    ) -> None:
        self._default_safe_search = default_safe_search
        self._default_language = default_language
        self._engines = engines
        self._categories = categories
        self._transport = transport
        self._max_bytes = max_bytes

    def describe(self) -> ProviderDescription:
        return ProviderDescription(
            implementation_id=IMPLEMENTATION_ID,
            family="search",
            contract_version="1.0",
            implementation_version=__version__,
            capabilities=(
                CapabilityDeclaration(
                    capability="search.query",
                    categories=self._categories,
                    constraints=("language", "safe_search"),
                    limitations=LIMITATIONS,
                ),
            ),
            supported_platforms=("linux-x86_64", "linux-aarch64"),
            dependency_manifest_id="searxng",
        )

    async def initialize(self, context: LifecycleContext) -> ProviderResult[Health]:
        try:
            await self._transport.start()
        except SearxngUnavailable as error:
            issue = Issue(code="provider_unavailable", message=str(error))
            return ProviderResult(outcome="failed", value=Health(state="unavailable", issues=(issue,)), issues=(issue,))
        return ProviderResult(outcome="completed", value=await self.health(context))

    async def health(self, context: LifecycleContext) -> Health:
        if await self._transport.healthy():
            return Health(state="ready")
        issue = Issue(code="provider_unavailable", message="SearXNG is not answering", retryable=True)
        return Health(state="unavailable", unavailable_capabilities=("search.query",), issues=(issue,))

    async def shutdown(self, context: LifecycleContext) -> ProviderResult[None]:
        await self._transport.stop()
        return ProviderResult(outcome="completed", value=None)

    def _form(self, request: SearchRequest) -> tuple[bytes, list[ConstraintDisposition]]:
        fields = [("q", request.query), ("format", "json"), ("engines", ",".join(self._engines)), ("pageno", "1")]
        dispositions = [ConstraintDisposition("category", "locally_applied", "results labelled with the category")]
        if request.language is not None:
            if LANGUAGE.fullmatch(request.language):
                fields.append(("language", request.language))
                dispositions.append(ConstraintDisposition("language", "provider_applied"))
            else:
                dispositions.append(ConstraintDisposition("language", "unsupported", "not a supported language tag"))
        elif self._default_language is not None:
            fields.append(("language", self._default_language))
            dispositions.append(ConstraintDisposition("language", "provider_applied", "operator default"))
        if request.safe_search is not None:
            fields.append(("safesearch", SAFE_SEARCH[request.safe_search]))
            dispositions.append(ConstraintDisposition("safe_search", "provider_applied"))
        elif self._default_safe_search is not None:
            fields.append(("safesearch", SAFE_SEARCH[self._default_safe_search]))
            dispositions.append(ConstraintDisposition("safe_search", "provider_applied", "operator default"))
        for name in UNSUPPORTED_CONSTRAINTS:
            if getattr(request, name) not in (None, ()):
                dispositions.append(ConstraintDisposition(name, "unsupported"))
        return urlencode(fields).encode("ascii"), dispositions

    @staticmethod
    def _failed(
        code: IssueCode, message: str, *, outcome: Outcome = "failed", retryable: bool = False
    ) -> ProviderResult[SearchResult]:
        return ProviderResult(
            outcome=outcome, value=None, issues=(Issue(code=code, message=message, retryable=retryable),)
        )

    async def search(self, request: SearchRequest, context: ProviderExecutionContext) -> ProviderResult[SearchResult]:
        if request.category not in self._categories:
            return self._failed("unsupported_capability", f"the category {request.category!r} is not configured")
        if request.continuation is not None:
            return self._failed("unsupported_capability", "continuation is not supported")
        if request.freshness == "cache_only":
            return self._failed("unsupported_capability", "the provider has no cache")
        remaining = context.deadline_monotonic - time.monotonic()
        if remaining <= 0:
            return self._failed("timeout", "the request deadline has passed", outcome="timed_out", retryable=True)
        if context.cancellation.requested():
            return self._failed("cancelled", "the request was cancelled", outcome="cancelled")
        form, dispositions = self._form(request)
        reply: Reply | None = None
        failure: TransportFailure | None = None
        cancelled = False
        async with anyio.create_task_group() as tasks:

            async def watch() -> None:
                nonlocal cancelled
                await context.cancellation.wait()
                cancelled = True
                tasks.cancel_scope.cancel()

            async def send() -> None:
                nonlocal reply, failure
                with anyio.move_on_after(remaining):
                    try:
                        reply = await self._transport.search(form, max_bytes=self._max_bytes)
                    except TransportFailure as error:
                        failure = error
                tasks.cancel_scope.cancel()

            tasks.start_soon(watch)
            tasks.start_soon(send)
        if failure is not None:
            outcome: Outcome = "timed_out" if failure.issue.code == "timeout" else "failed"
            return ProviderResult(outcome=outcome, value=None, issues=(failure.issue,))
        if cancelled:
            return self._failed("cancelled", "the request was cancelled", outcome="cancelled")
        if reply is None:
            return self._failed("timeout", "SearXNG did not respond in time", outcome="timed_out", retryable=True)
        return self._interpret(reply, request, dispositions)

    def _interpret(
        self, reply: Reply, request: SearchRequest, dispositions: Sequence[ConstraintDisposition]
    ) -> ProviderResult[SearchResult]:
        if reply.status == 429:
            retry_after = reply.header("Retry-After")
            delay = int(retry_after) * 1000 if retry_after is not None and retry_after.isdigit() else None
            issue = Issue(code="rate_limited", message="SearXNG is rate limiting", retryable=True, retry_after_ms=delay)
            return ProviderResult(outcome="failed", value=None, issues=(issue,))
        if reply.status == 403:
            return self._failed("access_restricted", "SearXNG refused the search; JSON output may be disabled")
        if reply.status != 200:
            return self._failed("provider_unavailable", f"SearXNG answered with status {reply.status}", retryable=True)
        try:
            data = json.loads(reply.body)
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self._failed("provider_unavailable", "SearXNG returned a response that is not JSON")
        if not isinstance(data, dict) or not isinstance(data.get("results"), list):
            return self._failed("provider_unavailable", "SearXNG returned an unexpected response")
        wanted = CATEGORIES[request.category]
        items: list[Discovery] = []
        for rank, result in enumerate(data["results"], start=1):
            if not isinstance(result, dict) or result.get("category") != wanted:
                continue
            discovery = _discovery(rank, result, request.category)
            if discovery is not None:
                items.append(discovery)
            if len(items) >= request.max_results:
                break
        unresponsive = [
            (entry[0], entry[1])
            for entry in data.get("unresponsive_engines", ())
            if isinstance(entry, list) and len(entry) == 2 and isinstance(entry[0], str)
        ]
        issues = tuple(
            Issue(
                code="network_error",
                message=f"upstream engine {_short(name)!r} did not respond: {_short(reason)}",
                retryable=True,
            )
            for name, reason in unresponsive
        )
        outcome: Outcome = "completed"
        if unresponsive:
            all_failed = {name for name, _ in unresponsive} >= set(self._engines)
            outcome = "failed" if all_failed and not items else "partial"
        result = SearchResult(
            items=tuple(items), constraints=tuple(dispositions), observed_at=_now(), upstream_cache_status="unknown"
        )
        return ProviderResult(outcome=outcome, value=result if outcome != "failed" else None, issues=issues)


def _problem(location: str, reason: str) -> ConfigurationProblem:
    return ConfigurationProblem(location, reason)


def create(instance: InstanceSettings) -> SearxngProvider:
    settings = instance.settings
    adapter = settings.get("adapter_settings")
    if adapter is None:
        raise _problem("/adapter_settings", "required for the searxng implementation")
    engines = tuple(settings["search"].get("upstream_engines", ()))
    if not engines:
        raise _problem("/search/upstream_engines", "at least one upstream engine is required")
    for engine in engines:
        if not ENGINE_NAME.fullmatch(engine):
            raise _problem(
                "/search/upstream_engines", "engine names are lower-case letters, digits, spaces, '.', '_' or '-'"
            )
    timeout_ms = int(instance.limits["timeout_ms"])
    engine_timeout_ms = int(adapter["engine_timeout_ms"])
    if engine_timeout_ms >= timeout_ms:
        raise _problem("/adapter_settings/engine_timeout_ms", "must be less than the effective timeout_ms")
    disclosure = instance.disclosure_scope
    if disclosure is None or not (disclosure["allow_query"] and disclosure["allow_external"]):
        raise _problem("/disclosure_scope", "must allow queries to external destinations")
    max_bytes = int(instance.limits["max_download_bytes"])
    categories: tuple[Category, ...] = tuple(adapter["categories"])
    deployment = settings["search"]["deployment"]
    transport: Transport
    if deployment == "internal":
        transport = _bundled_transport(instance, adapter, engines, engine_timeout_ms, timeout_ms)
    else:
        transport = _external_transport(instance, adapter, timeout_ms)
    return SearxngProvider(
        engines,
        categories,
        transport,
        max_bytes,
        default_safe_search=adapter.get("default_safe_search"),
        default_language=adapter.get("default_language"),
    )


def _bundled_transport(
    instance: InstanceSettings,
    adapter: Mapping[str, Any],
    engines: tuple[str, ...],
    engine_timeout_ms: int,
    timeout_ms: int,
) -> BundledTransport:
    for name in ("install_prefix", "startup_timeout_ms"):
        if name not in adapter:
            raise _problem(f"/adapter_settings/{name}", "required for a bundled (internal) deployment")
    scope = instance.network_scope
    if scope is None:
        raise _problem("/network_scope", "a bundled deployment needs a network scope listing its engines' destinations")
    if scope["public_web"]:
        raise _problem(
            "/network_scope", "a bundled deployment's scope must list destinations, not admit the public web"
        )
    if any(destination["scheme"] != "https" for destination in scope["destinations"]):
        raise _problem("/network_scope", "bundled SearXNG reaches https destinations only")
    concurrency = int(instance.limits["max_concurrency"])
    settings = BundledSettings(
        install_prefix=Path(adapter["install_prefix"]),
        engines=engines,
        request_timeout=engine_timeout_ms / 1000,
        max_request_timeout=timeout_ms / 1000,
        threads=concurrency,
        startup_timeout=int(adapter["startup_timeout_ms"]) / 1000,
        tunnel_connect_timeout=engine_timeout_ms / 1000,
        tunnel_idle_timeout=timeout_ms / 1000,
        max_tunnels=concurrency * len(engines),
        expected_commit=SEARXNG_COMMIT,
    )
    return BundledTransport(BundledSearxng(settings, NetworkPolicy.from_scope(scope)))


def _external_transport(instance: InstanceSettings, adapter: Mapping[str, Any], timeout_ms: int) -> ExternalTransport:
    for name in ("install_prefix", "startup_timeout_ms"):
        if name in adapter:
            raise _problem(f"/adapter_settings/{name}", "applies only to a bundled (internal) deployment")
    endpoint = instance.settings["endpoint"]
    if "private_ca_ref" in endpoint:
        raise _problem("/endpoint/private_ca_ref", "private CA references are not yet supported")
    if "credential_ref" in instance.settings:
        raise _problem("/credential_ref", "credentials for an external SearXNG instance are not yet supported")
    assert instance.network_scope is not None  # noqa: S101 - required with an endpoint by the configuration schema
    return ExternalTransport(
        endpoint["url"], NetworkPolicy.from_scope(instance.network_scope), timeout=timeout_ms / 1000
    )


def implementation() -> Implementation:
    return Implementation(
        implementation_id=IMPLEMENTATION_ID,
        family="search",
        factory=create,
        manifest=MANIFEST,
        settings_schema=SETTINGS_SCHEMA,
    )
