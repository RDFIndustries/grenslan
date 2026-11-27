"""Grenslan internal Provider Contract 1.0, PC-5 adopted specification.

Declaration-only reference. Not service implementation. No external dependencies.
All identifiers below are opaque internal handles, not public authorization.
The companion Provider Contract specifies validation, lifetime and enforcement.
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import AsyncIterator, Generic, Literal, Protocol, TypeAlias, TypeVar

Identifier: TypeAlias = str
Scalar: TypeAlias = str | int | float | bool | None
ScalarFields: TypeAlias = tuple[tuple[str, Scalar], ...]
Family: TypeAlias = Literal["search", "retrieval", "browser", "content", "ocr", "intelligence"]
ProviderState: TypeAlias = Literal["uninitialized", "initializing", "ready", "degraded", "unavailable", "disabled", "stopping", "stopped"]
Outcome: TypeAlias = Literal["completed", "partial", "failed", "cancelled", "timed_out", "interrupted"]
Format: TypeAlias = Literal["html", "xhtml", "text", "markdown", "json", "xml", "pdf", "docx", "xlsx", "pptx", "csv", "tsv", "png", "jpeg", "webp", "tiff", "gif", "svg"]
Category: TypeAlias = Literal["general", "news", "images", "video", "academic", "software", "patents", "government", "documents", "technical", "local", "enterprise", "products", "maps"]
Freshness: TypeAlias = Literal["default", "cache_only", "revalidate", "fresh_independent"]
Method: TypeAlias = Literal["auto", "native", "layout", "ocr"]
Capability: TypeAlias = Literal[
    "search.query", "retrieval.http", "browser.session", "browser.navigate",
    "browser.observe", "browser.interact", "browser.screenshot", "content.inspect",
    "content.read", "content.find", "content.tables", "content.render",
    "content.media", "content.transform", "ocr.recognize", "intelligence.vision",
    "intelligence.document_interpretation", "intelligence.summarization",
    "intelligence.translation", "intelligence.model_ocr"
]
IssueCode: TypeAlias = Literal[
    "invalid_request", "unsupported_capability", "unauthorized", "access_restricted",
    "provider_unavailable", "rate_limited", "network_error", "retrieval_failed",
    "extraction_failed", "resource_limit", "artifact_expired", "artifact_unavailable",
    "integrity_error", "timeout", "cancelled", "interrupted", "internal_error",
    "stale_handle", "cursor_expired", "conflict", "not_found"
]
T = TypeVar("T")

@dataclass(frozen=True, slots=True)
class Issue:
    code: IssueCode
    message: str
    retryable: bool = False
    retry_after_ms: int | None = None
    item_index: int | None = None

@dataclass(frozen=True, slots=True)
class ProviderResult(Generic[T]):
    outcome: Outcome
    value: T | None
    issues: tuple[Issue, ...] = ()

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
    # Digest is only an observation; core verifies before publication.
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
class Selection:
    pages: tuple[int, ...] = ()
    section: str | None = None
    heading: str | None = None
    paragraphs: Range | None = None
    sheet: str | None = None
    cells: str | None = None
    slides: tuple[int, ...] = ()
    path: str | None = None
    records: Range | None = None
    region: Region | None = None
    frames: tuple[int, ...] = ()
    character_range: Range | None = None

@dataclass(frozen=True, slots=True)
class Locator:
    type: Literal["page", "section", "paragraph", "sheet", "slide", "region", "frame", "path", "record", "offset", "element", "whole"]
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
class Coverage:
    complete: bool
    inspected: tuple[Locator, ...] = ()
    omitted: tuple[Locator, ...] = ()
    description: str | None = None

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
class Processing:
    method: str
    kind: Literal["deterministic", "ocr", "generated", "source_supplied"]
    implementation_id: Identifier
    model: str | None = None
    model_version: str | None = None
    material_configuration: ScalarFields = ()
    target_language: str | None = None
    model_assisted: bool = False

@dataclass(frozen=True, slots=True)
class Passage:
    locator: Locator
    processing: Processing
    text: str | None = None
    staged: StagedResource | None = None
    token_estimate: int | None = None

@dataclass(frozen=True, slots=True)
class Link:
    original_url: str
    resolved_url: str | None
    relation: Literal["internal", "external", "unknown"]
    anchor_text: str | None = None
    locator: Locator | None = None

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

@dataclass(frozen=True, slots=True)
class ConstraintDisposition:
    name: str
    status: Literal["provider_applied", "locally_applied", "partially_applied", "unsupported"]
    detail: str | None = None

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

@dataclass(frozen=True, slots=True)
class SearchResult:
    items: tuple[Discovery, ...]
    constraints: tuple[ConstraintDisposition, ...]
    observed_at: str
    upstream_cache_status: Literal["live", "cached", "unknown"] = "unknown"
    continuation: Identifier | None = None
    query_transformations: tuple[str, ...] = ()

class SearchProvider(Provider, Protocol):
    async def search(self, request: SearchRequest, context: ProviderExecutionContext) -> ProviderResult[SearchResult]: ...

@dataclass(frozen=True, slots=True)
class RetrievalRequest:
    url: str
    freshness: Freshness
    request_profile: Identifier | None = None
    conditional_etag: str | None = None
    conditional_modified_since: str | None = None

@dataclass(frozen=True, slots=True)
class RetrievalResult:
    requested_url: str
    final_url: str | None
    observed_at: str
    http_status: int | None
    complete: bool
    redirects: tuple[str, ...] = ()
    reported_media_type: str | None = None
    safe_metadata: ScalarFields = ()
    original: StagedResource | None = None
    not_modified: bool = False
    retrieval_conditions: tuple[str, ...] = ()

class RetrievalProvider(Provider, Protocol):
    async def retrieve(self, request: RetrievalRequest, context: ProviderExecutionContext) -> ProviderResult[RetrievalResult]: ...

@dataclass(frozen=True, slots=True)
class BrowserProfile:
    profile_id: Identifier
    engine: Identifier
    viewport: tuple[int, int]
    screen: tuple[int, int] | None = None
    user_agent: str | None = None
    locale: str | None = None
    timezone: str | None = None
    device_scale_factor: float | None = None

@dataclass(frozen=True, slots=True)
class BrowserSessionRequest:
    profile: BrowserProfile
    lifetime_ms: int
    transient: bool

@dataclass(frozen=True, slots=True)
class BrowserSession:
    handle: Identifier
    state: Literal["open", "closed", "expired", "interrupted"]
    profile_id: Identifier

@dataclass(frozen=True, slots=True)
class Navigation:
    session: Identifier
    url: str
    wait_until: Literal["dom_ready", "load", "selector"]
    selector: str | None = None

@dataclass(frozen=True, slots=True)
class BrowserDownload:
    requested_url: str
    final_url: str | None
    observed_at: str
    original: StagedResource
    complete: bool
    safe_metadata: ScalarFields = ()

@dataclass(frozen=True, slots=True)
class BrowserPage:
    session: Identifier
    page_state: Identifier
    url: str
    observed_at: str
    complete: bool
    title: str | None = None
    downloads: tuple[BrowserDownload, ...] = ()

@dataclass(frozen=True, slots=True)
class ObservationRequest:
    session: Identifier
    include: tuple[Literal["text", "headings", "links", "elements", "dom", "screenshot"], ...]
    max_chars: int
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class Element:
    handle: Identifier
    role: str | None = None
    name: str | None = None
    text: str | None = None
    actions: tuple[Literal["click", "fill", "select", "press"], ...] = ()

@dataclass(frozen=True, slots=True)
class BrowserRepresentation:
    representation: Literal["html", "text", "image"]
    staged: StagedResource

@dataclass(frozen=True, slots=True)
class Observation:
    page: BrowserPage
    text: str | None = None
    headings: tuple[Heading, ...] = ()
    links: tuple[Link, ...] = ()
    elements: tuple[Element, ...] = ()
    staged: tuple[BrowserRepresentation, ...] = ()
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class Scroll:
    direction: Literal["up", "down", "left", "right"]
    pixels: int
@dataclass(frozen=True, slots=True)
class Click:
    element: Identifier
@dataclass(frozen=True, slots=True)
class Fill:
    element: Identifier
    value: str
@dataclass(frozen=True, slots=True)
class Select:
    element: Identifier
    value: str
@dataclass(frozen=True, slots=True)
class Press:
    key: str
    element: Identifier | None = None
Action: TypeAlias = Scroll | Click | Fill | Select | Press

@dataclass(frozen=True, slots=True)
class InteractionRequest:
    session: Identifier
    page_state: Identifier
    action: Action
    authorized_effect_handle: Identifier

@dataclass(frozen=True, slots=True)
class InteractionResult:
    page: BrowserPage
    effect: Literal["observed", "uncertain", "none"]
    irreversible: bool

@dataclass(frozen=True, slots=True)
class ScreenshotRequest:
    session: Identifier
    page_state: Identifier
    target: Literal["viewport", "full_page", "region", "element"]
    region: Region | None = None
    element: Identifier | None = None

@dataclass(frozen=True, slots=True)
class Screenshot:
    page: BrowserPage
    image: StagedResource

class BrowserProvider(Provider, Protocol):
    async def create_session(self, request: BrowserSessionRequest, context: ProviderExecutionContext) -> ProviderResult[BrowserSession]: ...
    async def navigate(self, request: Navigation, context: ProviderExecutionContext) -> ProviderResult[BrowserPage]: ...
    async def observe(self, request: ObservationRequest, context: ProviderExecutionContext) -> ProviderResult[Observation]: ...
    async def interact(self, request: InteractionRequest, context: ProviderExecutionContext) -> ProviderResult[InteractionResult]: ...
    async def screenshot(self, request: ScreenshotRequest, context: ProviderExecutionContext) -> ProviderResult[Screenshot]: ...
    async def close_session(self, session: Identifier, context: ProviderExecutionContext) -> ProviderResult[BrowserSession]: ...

@dataclass(frozen=True, slots=True)
class EngineLaunch:
    engine_id: Identifier
    worker_handle: Identifier
    validated_profile: BrowserProfile

@dataclass(frozen=True, slots=True)
class EngineHandle:
    handle: Identifier

class BrowserEngine(Protocol):
    async def launch(self, request: EngineLaunch, context: ProviderExecutionContext) -> ProviderResult[EngineHandle]: ...
    async def terminate(self, handle: EngineHandle, context: ProviderExecutionContext) -> ProviderResult[None]: ...

class BrowserController(Protocol):
    async def attach(self, engine: EngineHandle, request: BrowserSessionRequest, context: ProviderExecutionContext) -> ProviderResult[BrowserSession]: ...
    async def navigate(self, request: Navigation, context: ProviderExecutionContext) -> ProviderResult[BrowserPage]: ...
    async def observe(self, request: ObservationRequest, context: ProviderExecutionContext) -> ProviderResult[Observation]: ...
    async def interact(self, request: InteractionRequest, context: ProviderExecutionContext) -> ProviderResult[InteractionResult]: ...
    async def screenshot(self, request: ScreenshotRequest, context: ProviderExecutionContext) -> ProviderResult[Screenshot]: ...
    async def detach(self, session: Identifier, context: ProviderExecutionContext) -> ProviderResult[None]: ...

@dataclass(frozen=True, slots=True)
class ContentRequest:
    resource: InputResource
    selection: Selection | None = None
    method: Method = "auto"
    continuation: Identifier | None = None
    max_items: int | None = None

@dataclass(frozen=True, slots=True)
class StructureNode:
    type: Literal["page", "bookmark", "section", "heading", "paragraph", "table", "sheet", "named_range", "slide", "note", "object", "column", "record", "path", "code", "link"]
    locator: Locator
    label: str | None = None
    count: int | None = None
    value_type: str | None = None

@dataclass(frozen=True, slots=True)
class ImageInfo:
    width: int | None = None
    height: int | None = None
    color_space: str | None = None
    transparency: bool | None = None
    orientation: str | None = None
    dpi_x: float | None = None
    dpi_y: float | None = None
    frame_count: int | None = None
    embedded_metadata: ScalarFields = ()

@dataclass(frozen=True, slots=True)
class Inspection:
    detected_format: Format | None
    metadata: Metadata
    coverage: Coverage
    structure: tuple[StructureNode, ...] = ()
    image: ImageInfo | None = None
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class ReadRequest:
    content: ContentRequest
    representation: Literal["original", "text", "structured", "image", "html", "metadata"]
    max_chars: int | None = None

@dataclass(frozen=True, slots=True)
class ReadResult:
    passages: tuple[Passage, ...]
    coverage: Coverage
    links: tuple[Link, ...] = ()
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class FindRequest:
    content: ContentRequest
    query: str
    case_sensitive: bool
    match_mode: Literal["literal", "regex"]
    max_matches: int
    context_chars: int

@dataclass(frozen=True, slots=True)
class Match:
    text: str
    locator: Locator
    context_before: str | None = None
    context_after: str | None = None

@dataclass(frozen=True, slots=True)
class FindResult:
    matches: tuple[Match, ...]
    coverage: Coverage
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class Cell:
    row: int
    column: int
    locator: Locator
    value: Scalar = None
    value_type: Literal["text", "number", "boolean", "date", "error", "blank", "unknown"] = "unknown"
    formula: str | None = None
    cached_value: Scalar = None
    has_cached_value: bool = False
    unit: str | None = None
    row_span: int = 1
    column_span: int = 1
    header: bool = False
    uncertain: bool = False

@dataclass(frozen=True, slots=True)
class Table:
    locator: Locator
    cells: tuple[Cell, ...]
    processing: Processing
    title: str | None = None
    row_count: int | None = None
    column_count: int | None = None

@dataclass(frozen=True, slots=True)
class TableResult:
    tables: tuple[Table, ...]
    coverage: Coverage
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class RenderRequest:
    content: ContentRequest
    format: Literal["png", "jpeg", "webp"]
    dpi: int | None = None
    max_width: int | None = None
    max_height: int | None = None

@dataclass(frozen=True, slots=True)
class Derived:
    staged: StagedResource
    locator: Locator
    processing: Processing
    parents: tuple[InputResource, ...]
    name: str | None = None

@dataclass(frozen=True, slots=True)
class DerivedResult:
    items: tuple[Derived, ...]
    coverage: Coverage
    continuation: Identifier | None = None

@dataclass(frozen=True, slots=True)
class MediaRequest:
    content: ContentRequest
    media_types: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class TransformRequest:
    resource: InputResource
    operation: Literal["crop", "resize", "thumbnail", "rotate", "convert"]
    region: Region | None = None
    width: int | None = None
    height: int | None = None
    max_width: int | None = None
    max_height: int | None = None
    preserve_aspect_ratio: bool = True
    degrees: float | None = None
    format: Literal["png", "jpeg", "webp", "tiff", "gif"] | None = None
    frame: int | None = None

# Optional execution subprotocols: a provider implements only declared operations.
class ContentProcessor(Provider, Protocol): ...
class InspectProcessor(ContentProcessor, Protocol):
    async def inspect(self, request: ContentRequest, context: ProviderExecutionContext) -> ProviderResult[Inspection]: ...
class ReadProcessor(ContentProcessor, Protocol):
    async def read(self, request: ReadRequest, context: ProviderExecutionContext) -> ProviderResult[ReadResult]: ...
class FindProcessor(ContentProcessor, Protocol):
    async def find(self, request: FindRequest, context: ProviderExecutionContext) -> ProviderResult[FindResult]: ...
class TableProcessor(ContentProcessor, Protocol):
    async def extract_tables(self, request: ContentRequest, context: ProviderExecutionContext) -> ProviderResult[TableResult]: ...
class RenderProcessor(ContentProcessor, Protocol):
    async def render(self, request: RenderRequest, context: ProviderExecutionContext) -> ProviderResult[DerivedResult]: ...
class MediaProcessor(ContentProcessor, Protocol):
    async def extract_media(self, request: MediaRequest, context: ProviderExecutionContext) -> ProviderResult[DerivedResult]: ...
class TransformProcessor(ContentProcessor, Protocol):
    async def transform(self, request: TransformRequest, context: ProviderExecutionContext) -> ProviderResult[Derived]: ...

@dataclass(frozen=True, slots=True)
class OCRRequest:
    resource: InputResource
    selection: Selection | None = None
    languages: tuple[str, ...] = ()
    continuation: Identifier | None = None
    allow_model_assisted: bool = False

@dataclass(frozen=True, slots=True)
class OCRBlock:
    text: str
    locator: Locator
    reading_order: int | None = None
    language: str | None = None
    confidence: float | None = None
    confidence_method: str | None = None

@dataclass(frozen=True, slots=True)
class OCRResult:
    blocks: tuple[OCRBlock, ...]
    processing: Processing
    coverage: Coverage
    continuation: Identifier | None = None

class OCRProvider(Provider, Protocol):
    async def recognize(self, request: OCRRequest, context: ProviderExecutionContext) -> ProviderResult[OCRResult]: ...

@dataclass(frozen=True, slots=True)
class IntelligenceRequest:
    capability: Literal["vision", "document_interpretation", "summarization", "translation", "model_ocr"]
    resources: tuple[InputResource, ...]
    selection: Selection | None = None
    prompt: str | None = None
    target_language: str | None = None
    languages: tuple[str, ...] = ()

@dataclass(frozen=True, slots=True)
class IntelligenceResult:
    passages: tuple[Passage, ...]
    coverage: Coverage
    ocr: OCRResult | None = None

class IntelligenceProvider(Provider, Protocol):
    async def interpret(self, request: IntelligenceRequest, context: ProviderExecutionContext) -> ProviderResult[IntelligenceResult]: ...
