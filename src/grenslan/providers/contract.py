"""Internal Provider Contract 1.0: runtime types (PC-055 to PC-058).

Fields, field order, annotations, defaults and protocol signatures reproduce
``docs/contracts/PROVIDER_INTERFACES.py`` exactly; a conformance test compares
them. This module adds construction-time validation of the invariants the
Provider Contract states for these records, so an invalid provider result
fails at the boundary instead of reaching public normalization.

Only the common types and the search family are defined here. The remaining
families are added with the milestones that implement them.

All identifiers are opaque internal handles, never public authorization.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Generic, Literal, Protocol, TypeAlias, TypeVar, get_args

CONTRACT_VERSION = "1.0"
MAX_ISSUE_MESSAGE_CHARS = 1000

Identifier: TypeAlias = str
Scalar: TypeAlias = str | int | float | bool | None
ScalarFields: TypeAlias = tuple[tuple[str, Scalar], ...]
Family: TypeAlias = Literal["search", "retrieval", "browser", "content", "ocr", "intelligence"]
ProviderState: TypeAlias = Literal[
    "uninitialized", "initializing", "ready", "degraded", "unavailable", "disabled", "stopping", "stopped"
]
Outcome: TypeAlias = Literal["completed", "partial", "failed", "cancelled", "timed_out", "interrupted"]
Format: TypeAlias = Literal[
    "html", "xhtml", "text", "markdown", "json", "xml", "pdf", "docx", "xlsx", "pptx", "csv", "tsv",
    "png", "jpeg", "webp", "tiff", "gif", "svg",
]  # fmt: skip
Category: TypeAlias = Literal[
    "general", "news", "images", "video", "academic", "software", "patents", "government", "documents",
    "technical", "local", "enterprise", "products", "maps",
]  # fmt: skip
Freshness: TypeAlias = Literal["default", "cache_only", "revalidate", "fresh_independent"]
Method: TypeAlias = Literal["auto", "native", "layout", "ocr"]
Capability: TypeAlias = Literal[
    "search.query", "retrieval.http", "browser.session", "browser.navigate",
    "browser.observe", "browser.interact", "browser.screenshot", "content.inspect",
    "content.read", "content.find", "content.tables", "content.render",
    "content.media", "content.transform", "ocr.recognize", "intelligence.vision",
    "intelligence.document_interpretation", "intelligence.summarization",
    "intelligence.translation", "intelligence.model_ocr",
]  # fmt: skip
IssueCode: TypeAlias = Literal[
    "invalid_request", "unsupported_capability", "unauthorized", "access_restricted",
    "provider_unavailable", "rate_limited", "network_error", "retrieval_failed",
    "extraction_failed", "resource_limit", "artifact_expired", "artifact_unavailable",
    "integrity_error", "timeout", "cancelled", "interrupted", "internal_error",
    "stale_handle", "cursor_expired", "conflict", "not_found",
]  # fmt: skip
T = TypeVar("T")

_ISSUE_CODES = frozenset(get_args(IssueCode))
_OUTCOMES = frozenset(get_args(Outcome))
_UNSUCCESSFUL = frozenset({"failed", "cancelled", "timed_out", "interrupted"})
_DISPOSITIONS = frozenset({"provider_applied", "locally_applied", "partially_applied", "unsupported"})


def _require_tuple_of(value: object, kind: type, field: str) -> None:
    if not isinstance(value, tuple) or not all(isinstance(item, kind) for item in value):
        raise TypeError(f"{field} must be a tuple of {kind.__name__}")


@dataclass(frozen=True, slots=True)
class Issue:
    code: IssueCode
    message: str
    retryable: bool = False
    retry_after_ms: int | None = None
    item_index: int | None = None

    def __post_init__(self) -> None:
        if self.code not in _ISSUE_CODES:
            raise ValueError("issue code is not in the contract vocabulary")
        if not self.message or len(self.message) > MAX_ISSUE_MESSAGE_CHARS:
            raise ValueError(f"issue message must be 1 to {MAX_ISSUE_MESSAGE_CHARS} characters")
        if self.retry_after_ms is not None and self.retry_after_ms < 0:
            raise ValueError("retry_after_ms must be nonnegative")
        if self.item_index is not None and self.item_index < 0:
            raise ValueError("item_index must be nonnegative")


@dataclass(frozen=True, slots=True)
class ProviderResult(Generic[T]):  # noqa: UP046 - mirrors the adopted declaration
    outcome: Outcome
    value: T | None
    issues: tuple[Issue, ...] = ()

    def __post_init__(self) -> None:
        if self.outcome not in _OUTCOMES:
            raise ValueError("outcome is not in the contract vocabulary")
        _require_tuple_of(self.issues, Issue, "issues")
        if self.outcome == "partial":
            if self.value is None:
                raise ValueError("a partial outcome requires a partial value")
            if not self.issues:
                raise ValueError("a partial outcome requires at least one issue")
        if self.outcome in _UNSUCCESSFUL and not self.issues:
            raise ValueError(f"a {self.outcome} outcome requires at least one issue")


@dataclass(frozen=True, slots=True)
class CapabilityDeclaration:
    capability: Capability
    formats: tuple[Format, ...] = ()
    categories: tuple[Category, ...] = ()
    constraints: tuple[str, ...] = ()
    methods: tuple[Method, ...] = ()
    supports_selection: bool = False
    model_assisted: bool = False
    limitations: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderDescription:
    implementation_id: Identifier
    family: Family
    contract_version: Literal["1.0"]
    implementation_version: str
    capabilities: tuple[CapabilityDeclaration, ...]
    supported_platforms: tuple[str, ...]
    dependency_manifest_id: Identifier


@dataclass(frozen=True, slots=True)
class Health:
    state: ProviderState
    unavailable_capabilities: tuple[Capability, ...] = ()
    issues: tuple[Issue, ...] = ()


@dataclass(frozen=True, slots=True)
class Limits:
    max_input_bytes: int
    max_download_bytes: int
    max_output_bytes: int
    max_temp_bytes: int
    max_memory_bytes: int
    max_cpu_ms: int
    max_pixels: int
    max_expansion_bytes: int
    max_recursion: int
    max_items: int
    max_redirects: int
    max_retries: int

    def __post_init__(self) -> None:
        for name in self.__slots__:
            minimum = 0 if name in ("max_redirects", "max_retries") else 1
            if getattr(self, name) < minimum:
                raise ValueError(f"{name} must be at least {minimum}")


class Cancellation(Protocol):
    def requested(self) -> bool: ...
    async def wait(self) -> None: ...


@dataclass(frozen=True, slots=True)
class InputResource:
    handle: Identifier
    media_type: str
    size_bytes: int
    sha256: str
    format: Format | None = None


@dataclass(frozen=True, slots=True)
class StagedResource:
    handle: Identifier
    media_type: str
    size_bytes: int
    # The digest is only an observation; the core verifies it before publication.
    sha256: str | None = None


class ResourceAccess(Protocol):
    def read(self, resource: InputResource) -> AsyncIterator[bytes]: ...
    async def stage(self, chunks: AsyncIterator[bytes], media_type: str) -> StagedResource: ...


@dataclass(frozen=True, slots=True)
class ProviderExecutionContext:
    request_id: Identifier
    operation_id: Identifier | None
    provider_id: Identifier
    deadline_monotonic: float
    limits: Limits
    budget_handle: Identifier
    resource_scope: tuple[InputResource, ...]
    resources: ResourceAccess
    cancellation: Cancellation
    network_scope_id: Identifier
    disclosure_scope_id: Identifier
    credential_ref: Identifier | None = None


@dataclass(frozen=True, slots=True)
class LifecycleContext:
    provider_id: Identifier
    deadline_monotonic: float
    cancellation: Cancellation


class Provider(Protocol):
    def describe(self) -> ProviderDescription: ...
    async def initialize(self, context: LifecycleContext) -> ProviderResult[Health]: ...
    async def health(self, context: LifecycleContext) -> Health: ...
    async def shutdown(self, context: LifecycleContext) -> ProviderResult[None]: ...


@dataclass(frozen=True, slots=True)
class Range:
    start: int
    end: int


@dataclass(frozen=True, slots=True)
class Region:
    coordinate_space: Literal["normalized", "pixels", "points"]
    x: float
    y: float
    width: float
    height: float
    reference: InputResource | None = None


@dataclass(frozen=True, slots=True)
class Locator:
    type: Literal[
        "page",
        "section",
        "paragraph",
        "sheet",
        "slide",
        "region",
        "frame",
        "path",
        "record",
        "offset",
        "element",
        "whole",
    ]
    page: int | None = None
    section: str | None = None
    heading: str | None = None
    paragraph: int | None = None
    sheet: str | None = None
    cells: str | None = None
    slide: int | None = None
    object: str | None = None
    region: Region | None = None
    frame: int | None = None
    path: str | None = None
    record: int | None = None
    character_range: Range | None = None
    element: Identifier | None = None


@dataclass(frozen=True, slots=True)
class Heading:
    title: str
    locator: Locator
    level: int | None = None


@dataclass(frozen=True, slots=True)
class Metadata:
    title: str | None = None
    authors: tuple[str, ...] = ()
    published_at: str | None = None
    language: str | None = None
    filename: str | None = None
    abstract: str | None = None
    description: str | None = None
    table_of_contents: tuple[Heading, ...] = ()
    page_count: int | None = None
    sheet_count: int | None = None
    slide_count: int | None = None


@dataclass(frozen=True, slots=True)
class SearchRequest:
    query: str
    category: Category
    max_results: int
    freshness: Freshness = "default"
    language: str | None = None
    region: str | None = None
    date_from: str | None = None
    date_to: str | None = None
    include_domains: tuple[str, ...] = ()
    exclude_domains: tuple[str, ...] = ()
    file_types: tuple[str, ...] = ()
    safe_search: Literal["off", "moderate", "strict"] | None = None
    min_width: int | None = None
    min_height: int | None = None
    continuation: Identifier | None = None

    def __post_init__(self) -> None:
        if not self.query:
            raise ValueError("query must be nonempty")
        if self.max_results < 1:
            raise ValueError("max_results must be at least 1")


@dataclass(frozen=True, slots=True)
class ConstraintDisposition:
    name: str
    status: Literal["provider_applied", "locally_applied", "partially_applied", "unsupported"]
    detail: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _DISPOSITIONS:
            raise ValueError("constraint status is not in the contract vocabulary")


@dataclass(frozen=True, slots=True)
class Discovery:
    original_rank: int
    url: str | None = None
    title: str | None = None
    snippet: str | None = None
    upstream_engine: str | None = None
    image_url: str | None = None
    source_page_url: str | None = None
    thumbnail_url: str | None = None
    caption: str | None = None
    thumbnail: StagedResource | None = None
    width: int | None = None
    height: int | None = None
    media_type: str | None = None
    license: str | None = None
    metadata: Metadata | None = None
    category_metadata: ScalarFields = ()
    organization: str | None = None

    def __post_init__(self) -> None:
        if self.original_rank < 1:
            raise ValueError("original_rank must be at least 1")
        if not (self.url or self.image_url or self.source_page_url):
            raise ValueError("a discovery requires a url, image_url or source_page_url")
        names = [name for name, _ in self.category_metadata]
        if len(names) != len(set(names)):
            raise ValueError("category_metadata names must be unique")


@dataclass(frozen=True, slots=True)
class SearchResult:
    items: tuple[Discovery, ...]
    constraints: tuple[ConstraintDisposition, ...]
    observed_at: str
    upstream_cache_status: Literal["live", "cached", "unknown"] = "unknown"
    continuation: Identifier | None = None
    query_transformations: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_tuple_of(self.items, Discovery, "items")
        _require_tuple_of(self.constraints, ConstraintDisposition, "constraints")


class SearchProvider(Provider, Protocol):
    async def search(
        self, request: SearchRequest, context: ProviderExecutionContext
    ) -> ProviderResult[SearchResult]: ...
