# Grenslan v0.1: Provider Contract

| Attribute | Value |
|---|---|
| Project | Grenslan |
| Owner | RDF Industries, Inc. |
| Architecture baseline | v0.1, Revision 12, Checkpoint 011 |
| Public Tool Contract | Revision 06, TC-001 through TC-057 accepted |
| Public wire contract | 1.0 |
| Provider Contract revision | 05 |
| Review round | PC-5 |
| Status | Adopted: PC-001 through PC-066 |
| Date | 2026-11-26 (Pacific) |

This is the adopted internal Provider Contract. It is an internal implementation contract, not a competing public API or replacement for the adopted architecture, decision register or Tool Contract. PC identifiers do not consume architecture decision IDs. The adopted Master PRP gates service implementation on finalized Tool and Provider Contracts, approved PRP-001 and resolved foundation-affecting implementation choices. Examples in PC-001 through PC-054 express accepted direction. Exact interface declarations in PROVIDER_INTERFACES.py, provider configuration in PROVIDER_CONFIG_SCHEMA.json and PC-5 semantic rules are normative. No service conformance is claimed.

## PC-001: Lightweight capability-specific provider interfaces

**Status:** Accepted. **Authority:** AD-367, AD-418–422.

Use six versioned, capability-specific typed Python interfaces: SearchProvider, RetrievalProvider, BrowserProvider, ContentProcessor, OCRProvider and IntelligenceProvider. Use lightweight structural typing through Python Protocol where appropriate rather than a complex common inheritance hierarchy. A provider is not an agent, orchestration runtime or mandatory independently deployed service. Providers may communicate across isolated process boundaries as necessary. Keep browser controller and engine separable.

Common interface direction: describe() returns implementation identity and capabilities; initialize() initializes configured resources; health() reports bounded operational state; shutdown() releases resources safely. Each family defines its own execution methods. Exact types, method signatures and lifecycle details are reconciled in PC-5.

Illustrative interface:

```python
class SearchProvider(Protocol):
    async def search(
        self,
        request: SearchRequest,
        context: ProviderExecutionContext,
    ) -> SearchResult:
        ...
```

## PC-002: Separate implementation and configured provider identity

**Status:** Accepted. **Authority:** AD-370, AD-416, AD-418–419, AD-422.

Distinguish provider family/interface, implementation identity and operator-configured instance identity. For example SearchProvider, SearXNGProvider, searxng_local or searxng_enterprise. Multiple independently configured instances may use the same installed implementation with distinct endpoints, credentials, limits and authorization. Optional intelligence may configure several model endpoints without requiring a new adapter for each model.

## PC-003: Provider capability declarations

**Status:** Accepted. **Authority:** AD-368, AD-370–371, AD-416, AD-418, AD-429, TC-042–043.

Declare supported capabilities, categories, formats and constraints appropriate to the family. Distinguish technically supported, operator-configured, operational and consumer-authorized capabilities. The core determines effective public capability reporting; a provider declaration does not grant authority. Providers need not implement every operation in their family.

Illustrative declaration:

```json
{
  "provider_id": "searxng_local",
  "family": "search",
  "implementation": "searxng",
  "contract_version": "1.0",
  "status": "enabled",
  "capabilities": ["search.general", "search.news", "search.images"],
  "constraints": ["language", "region"]
}
```

## PC-004: Operator-controlled registration

**Status:** Accepted. **Authority:** AD-404, AD-419, AD-422, AD-425.

Ship approved reference implementations and document how operator-authorized compatible extensions can be developed and installed. Operators may configure approved installed implementations for specialized services, private repositories, government sources and other permitted capabilities. Ordinary research consumers cannot install packages, load arbitrary modules, download executable plugins, activate unapproved providers, modify endpoints/credentials or alter network policy. Configuration is not an arbitrary execution mechanism. A distributed marketplace or plugin framework is unnecessary.

## PC-005: Minimal scoped provider execution context

**Status:** Accepted. **Authority:** AD-396–405, AD-412, AD-421.

Provide only necessary authorized invocation context: request ID, applicable operation ID, effective deadline, scoped authorized resources, effective limits, cooperative cancellation, destination scope, approved credential reference where necessary, and disclosure scope. The core retains complete authenticated consumer context. Do not automatically pass application credentials, unrelated identities, conversation history, other users' data, database credentials, administrative privileges or unrestricted access. Restriction descriptions are not themselves enforcement; implement actual network, filesystem, resource and process controls. Exact context transport and typed resource access are reconciled in PC-5.

## PC-006: Deterministic provider selection and routing

**Status:** Accepted. **Authority:** AD-374, AD-416, AD-420–422, AD-429.

The service core determines eligible providers using requested capability, detected resource format, installed and configured implementations, consumer authorization, operational state, destination and disclosure constraints, remaining budget and explicit authorized provider preferences. Use operator-configured priorities rather than AI-driven selection. Provider preferences are requests, not authority. Selection should be attributable and explainable.

## PC-007: Authorization-preserving fallback

**Status:** Accepted. **Authority:** AD-378–379, AD-398–405, AD-412, AD-420–421.

Fallback only to authorized configured compatible alternatives, retaining original scope, independent-observation requirements, budgets and disclosure restrictions. Attribute the provider actually producing each result. Examples: alternative discovery when available, compatible HTML or PDF extractor, native to layout/OCR when appropriate, original artifact fallback, deterministic outputs when optional inference unavailable. Do not bypass destination/access restrictions or revoked credentials. Do not silently replace a failed browser session with another session state. Preserve distinct partial results and report failures.

## PC-008: Provider-independent result normalization

**Status:** Accepted. **Authority:** AD-390–394, AD-418, AD-421, AD-428–430.

Providers return typed capability-specific internal results with available source metadata, original ranking, processing methods, actual observed content and limitations. The core owns public response envelopes, source/capture identity, artifact publication, citations, access enforcement, public error normalization and request/operation attribution. Providers cannot independently publish consumer-accessible references or grant access. Raw upstream objects are not the public Tool Contract.

## PC-009: Capability-appropriate execution isolation

**Status:** Accepted. **Authority:** AD-399–403, AD-410–414, AD-421, AD-423.

Use bounded asynchronous I/O for search and direct HTTP; isolated processes for browser execution and restricted workers for untrusted parsing, image processing and OCR; authorized scoped endpoint communication for optional inference. CPU-heavy work must not indefinitely starve lightweight research. Worker reuse requires clean scoped state and safe isolation. Enforce resource, process, network and filesystem boundaries, including for work within the same primary container. No external scheduler, broker or distributed workflow engine is required. Exact enforcement mechanisms require security and implementation validation.

## PC-010: Lifecycle and health reporting

**Status:** Accepted. **Authority:** AD-410–416, AD-418, AD-423.

Use bounded internal provider states: uninitialized, initializing, ready, degraded, unavailable, disabled, stopping and stopped. Translate them to the public capability vocabulary (enabled, disabled, unavailable, unsupported) according to requested capability and authorization. Optional provider unavailability must not unnecessarily prevent core startup or unrelated research. Initialization and shutdown obey applicable budgets, cancellation and resource cleanup.

## PC-011: Dependency, licensing and distribution controls

**Status:** Accepted. **Authority:** AD-404, AD-419, AD-422–427.

For distributed implementations, record pinned dependency versions, licenses, applicable third-party binaries and model weights, integrity information, platform compatibility, redistribution obligations and known limitations. Include accessible applicable license notices and documentation within the container and repository documentation/README references. Validate alternative browser compatibility, sandboxing, security and licensing before enabling/distributing. Actual versions and dependency selection remain subject to validation. No unapproved executable replacement, mandatory hosted inference, proprietary browser licensing or runtime downloads are introduced.

## PC-012: Normalized search execution interface

**Status:** Accepted. **Authority:** AD-370–371, AD-390, AD-418, TC-010–015.

SearchProvider.search(request: SearchRequest, context: ProviderExecutionContext) is an asynchronous typed operation returning SearchResult. Request carries applicable query, category, language, region, date range, inclusion/exclusion domains, file types, safe-search preference, result limit and provider continuation state under effective context limits. Return available URLs, titles, snippets, provider order, publication date, author/organization, content type, identifiers, image and licensing metadata, attribution, continuation and limitations. Normalize available facts; missing metadata stays unknown. Provider-specific authentication/query translation stays internal and material transformations are attributable. Exact types are finalized in PC-5.

## PC-013: SearXNG reference and external integration

**Status:** Accepted. **Authority:** AD-370, AD-419, AD-423, AD-425.

Use SearXNG as the primary general discovery provider. Bundle a separately supervised internal SearXNG process with protected endpoint in the primary container; do not incorporate its source into Grenslan modules. Support an operator-authorized existing external instance as an alternative. Neither external consumers nor untrusted browser/document workers may access the internal endpoint. Preserve both configured Grenslan provider identity and available upstream engine attribution. Upstream engines and disclosure settings are operator-controlled. No separate mandatory search container or central hosted service.

## PC-014: Required specialized discovery adapters

**Status:** Accepted. **Authority:** AD-419, AD-422.

Implement arXiv (scientific/technical preprints), Crossref (publication/DOI), PubMed (medical/biological), OpenAlex (scholarly) and GitHub (software/technical) adapters for v0.1 through SearchProvider. Each is independently configurable and disableable. Validate actual API versions, credentials, pagination, supported constraints and rate limits during implementation. No mandatory credentials for every provider as a startup prerequisite.

## PC-015: Operator-authorized custom discovery

**Status:** Accepted. **Authority:** AD-404, AD-419, AD-422, AD-425.

Support deployment-specific government API, private repository and optional commercial discovery providers through documented SearchProvider integrations. No fixed government endpoint or mandatory repository/commercial service. An authorized operator installs/approves the adapter, configures scoped endpoint and credential reference, and enables it under applicable disclosure rules. No runtime arbitrary executable installation or public contract changes required.

## PC-016: Category and constraint disposition

**Status:** Accepted. **Authority:** AD-371, AD-429, TC-010–011.

Preserve all 14 adopted public discovery categories: general, news, images, video, academic, software, patents, government, documents, technical, local, enterprise, products and maps. Individual providers declare their supported categories and constraints. Report provider_applied, locally_applied, partially_applied and unsupported per requested constraint. No unreported substitution of category or ignored filter. Bounded local filtering of returned metadata is not a comprehensive provider search.

## PC-017: Deterministic ranking and aggregation

**Status:** Accepted. **Authority:** AD-372–373, TC-012–013.

Default to original provider order for one provider and transparent deterministic relevance aggregation for multiple providers. Evaluate reciprocal rank fusion (RRF) as the initial candidate, not a pinned algorithm or parameter choice. Preserve original rank, provider attribution and explicit consumer ranking/filter preferences. No embedding, LLM, generalized source-trust, ideological or political ranking. Ranking is not factual reliability.

## PC-018: Conservative duplicate handling

**Status:** Accepted. **Authority:** AD-373, AD-391, TC-012.

Conservatively normalize URLs without discarding query parameters that may alter content. Preserve original source/provenance and distinguish duplicate URL, redirect relationship, identical bytes, possible syndication and related content where detectable. Aggregate attribution without claiming independent corroboration. Different observations remain distinguishable even where byte storage can be deduplicated.

## PC-019: Direct HTTP retrieval interface

**Status:** Accepted. **Authority:** AD-374, AD-378–380, AD-390, AD-418–419.

HTTPX is the reference RetrievalProvider implementation. Asynchronous retrieve(request: RetrievalRequest, context: ProviderExecutionContext) returns RetrievalResult. Request carries authorized URL, freshness, applicable scoped credential reference/request profile, deadline and effective download limit. Result returns available requested/final URL, redirect history, HTTP status, capture time, reported media type, safe response metadata, bytes or scoped staged handle, retrieval conditions, completion state and limitations. No arbitrary credentials or network overrides. Suppress sensitive headers, tokens and cookies from public results. Exact signatures/types in PC-5.

## PC-020: Separation of retrieval and processing

**Status:** Accepted. **Authority:** AD-380–381, AD-391–395, AD-420, TC-023–034.

Acquisition obtains original bytes; actual format detection and content processing are separate. The core hashes and validates retained bytes before publishing authorized references. Preserve authorized original artifact when parser/processor fails or is unavailable, with available metadata, limitations and partial results. Never present a discovery snippet as acquired evidence or a truncated download as complete.

## PC-021: Automatic and explicit retrieval routes

**Status:** Accepted. **Authority:** AD-374, AD-377–378, TC-016.

Use the least resource-intensive authorized route satisfying the request. Auto normally prefers direct HTTP for static HTML, documents, images and structured data, and escalates to browser when dynamic rendering is needed. Respect explicitly requested authorized HTTP/browser routes and explicit browser interaction/screenshots. Report actual route and limitations. Do not escalate to bypass access controls.

## PC-022: Destination, credential and disclosure enforcement

**Status:** Accepted. **Authority:** AD-398–405, AD-421, AD-428.

Enforce destination policy independently of content and provider selection: scheme, hostname, resolved IP, actual connection target, redirects, DNS changes, scoped credentials and disclosure controls. Default to denying unintended host/private/management access. An approved initial URL does not authorize an unapproved redirect. Authorized outbound HTTP-only sources are permitted under policy, without relaxing consumer HTTPS-only ingress or TLS validation for HTTPS destinations.

## PC-023: Shared limits, bounded retries and failure classification

**Status:** Accepted. **Authority:** AD-378, AD-410–413.

Enforce provider rate limits across concurrent requests, honor applicable Retry-After, bound retries by deadline, cancellation and enclosing budget, and retry only appropriate operations. Fallback cannot circumvent provider limits or access restrictions. Distinguish successful empty results, provider unavailability, rate limits, access restrictions, policy denials, resource limits, interrupted network/retrieval and extraction failures. Preserve authorized partial outcomes and attribution.

## PC-024: Freshness and independent observations

**Status:** Accepted. **Authority:** AD-379, AD-391, AD-408–409, AD-413, TC-015, TC-039.

Preserve default, cache_only, revalidate and fresh_independent policies. Respect cache eligibility and authorization. Distinguish actual observation time from cached access time. Revalidation of unchanged content is not a new download of original bytes. Independent execution bypasses incompatible retained/coalesced observations. Never silently replace a requested retained capture or represent one observation as multiple independent observations.

## PC-025: Browser controller and engine separation

**Status:** Accepted. **Authority:** AD-374–375, AD-418–419.

Keep the browser controller and engine contracts separate. Playwright is the reference controller. The common BrowserProvider adapts controller and compatible engine without duplicating service session management, research tools or authorization. The core owns public resource identities and policy.

## PC-026: Reference and alternative browser implementations

**Status:** Accepted. **Authority:** AD-375, AD-419, AD-422, AD-424.

Chromium is the reference engine; Clearcote Open and Brave Origin are alternative integration targets subject to compatibility, licensing, redistribution, platform and security validation. Firefox is outside initial scope. Chromium must remain independent of alternatives. Do not automatically select a licensed Clearcote edition or require a proprietary licensing service. Report unavailable platform-specific capabilities.

## PC-027: Common typed BrowserProvider interface

**Status:** Accepted. **Authority:** AD-374–376, AD-418, TC-019–022, TC-053.

Support create_session, navigate, observe, interact, screenshot and close_session through bounded asynchronous internal Python methods and internal browser-based retrieval. Public explicit browser tools remain synchronous; independent sessions may run concurrently. The core owns authorization, public handles, resource and artifact publication. Exact typed signatures and lifecycle in PC-5.

## PC-028: Session-consistent browser identity profiles

**Status:** Accepted. **Authority:** AD-375, AD-399–401, TC-019.

Use operator-defined, internally consistent, validated profiles including applicable engine, user agent, viewport and screen, device scale factor, language, locale, time zone and supported device characteristics. Default or specifically requested authorized profile; optionally select randomly from an operator-approved set of compatible profiles once at creation. Preserve the chosen profile for the session lifetime; no independent per-request randomization. Identity settings confer no authority and cannot override access restrictions or network rules. Unsupported settings are reported, not fabricated.

## PC-029: Transient and explicit browser sessions

**Status:** Accepted. **Authority:** AD-374, AD-376, AD-399, TC-016, TC-019.

Transient sessions support single authorized browser retrieval/rendering and close after capture; explicit sessions retain scoped session-local state across multiple authorized tool operations until closed, expired or revoked. No persistent profile requirement or dependence on MCP transport sessions. Retained authorized artifacts have independent lifetimes.

## PC-030: Browser isolation and private state

**Status:** Accepted. **Authority:** AD-396–405, AD-421, TC-019, TC-053.

Isolate browser cookies, authentication, storage, history, downloads, files, open pages and element handles by authorized context. Identically named agents in unrelated contexts cannot share state. Reuse engine processes only if isolation permits and prior state cannot leak. Browser contexts alone are insufficient for mutually untrusted environments; use appropriate process/OS boundaries and keep browser protections enabled.

## PC-031: Page state and element validation

**Status:** Accepted. **Authority:** AD-376, AD-397, TC-020–021, TC-053.

Identify observations by browser_session_id and page_state_id. Bind element handles to the specific session and relevant page state; reject stale or mismatched handles, never silently remap to another element. Serialize or explicitly reject conflicting concurrent actions within a session.

## PC-032: Bounded rendering completion

**Status:** Accepted. **Authority:** AD-377–378, AD-412, TC-016, TC-019.

Support dom_ready, load and approved selector readiness conditions under effective request deadlines. Continuous background activity cannot block indefinitely. Explicitly report incomplete rendering and return available authorized observations and limitations. Do not claim completeness solely because an event fired.

## PC-033: Structured browser observations

**Status:** Accepted. **Authority:** AD-376, AD-390–392, TC-020.

Return available title, current URL, rendered text, headings, links, accessibility-oriented elements, interaction handles, selected DOM representations, screenshot references, capture time, completion and limitations. Bounded output enables clients without visual model capability. Separate observation metadata and original/derived representations.

## PC-034: Typed interactions and authorization of effects

**Status:** Accepted. **Authority:** AD-376, AD-396–405, AD-412, TC-021.

Support typed scroll, click, fill, select and press actions. No arbitrary consumer-supplied script. Authorize the actual effect and data disclosure, not action name or HTTP method alone. Ordinary research may scroll, expand or perform authorized searches; authentication, purchase, publication, messaging, upload and other external state changes require distinct authority. When effect cannot reasonably be established within granted authorization, deny or request expanded authorization.

## PC-035: Browser screenshots and acquired artifacts

**Status:** Accepted. **Authority:** AD-376, AD-387, AD-391–395, AD-420, TC-022.

Support viewport, bounded full page, region and element screenshots. Retain authorized capture with applicable session/page-state, time and source attribution. Cropping, OCR and visual interpretation use processing providers. Browser downloads enter the same staged, bounded validation/hash/format and artifact publication pipeline as direct retrieval. Closing a session does not automatically destroy separately retained authorized artifacts.

## PC-036: Independent browser network enforcement

**Status:** Accepted. **Authority:** AD-398–403, AD-421, AD-423.

Apply destination and disclosure policy to initial navigation, redirects, embedded subresources, script traffic, frames, websockets, downloads, DNS and actual connection targets. Browser interception alone is insufficient. Underlying independent enforcement must prevent unauthorized host/private/management access and inherited privileges to internal search/inference endpoints. Fail closed if required isolation is unavailable; no browser sandbox bypass.

## PC-037: Browser resource limits and lifecycle

**Status:** Accepted. **Authority:** AD-399, AD-405, AD-410–414, TC-053.

Configure concurrent sessions, per-application limits, lifetimes, navigation time, CPU, memory, page counts, download/screenshot size, temporary storage and interaction bounds. Release resources on transient completion, closure, expiry, revocation, cancellation or failure as applicable. Crash/interruption or unavailable state is explicit; do not silently recreate an active session and claim it retains state.

## PC-038: Browser compatibility, failures and fallback

**Status:** Accepted. **Authority:** AD-378, AD-419–422, AD-424.

Allow authorized configured fallback at session creation only where requested selection and policy permit; explicit unavailable engine reports unavailability. Do not replace crashed active session state. Disable implementations failing applicable licensing or security validation; disclose platform limits. Respect source access restrictions. Acceptance testing maps static and JS retrieval, profile consistency, isolation, stale handles, observations, limits, expiry, network enforcement, compatible engines and failure cleanup to existing T-criteria; no test claimed passed.

## PC-039: Capability-specific ContentProcessor

**Status:** Accepted. **Authority:** AD-380–389, AD-418, TC-026–032.

Declare format-specific supported operations rather than requiring every implementation to perform all operations. Support inspect, read, find, extract_tables, render, extract_media and transform at the capability-family level. The core selects bounded compatible combinations. Exact typed capability interfaces and signatures in PC-5.

## PC-040: Minimum format-specific capabilities

**Status:** Accepted. **Authority:** AD-381–388, AD-419, TC-026–034.

The following are minimum v0.1 service capabilities across approved processors, not obligations of every processor. All formats support acquisition/authorized original delivery and available metadata; unsupported sub-capabilities are explicit. Selective access, bounded inspection and fidelity apply where relevant.

| Format | Minimum processing |
|---|---|
| HTML/XHTML | Text, headings, links, lists, tables, code, metadata |
| Plain text | Inspect, read, literal find, bounded ranges |
| Markdown | Text, headings, sections, links, code, structure |
| JSON | Safe parse, inspect hierarchy, selected path access |
| XML | Restricted parse, inspect hierarchy, selected path access |
| CSV/TSV | Columns, records, tables, record ranges |
| PDF | Page inspection, native/layout-aware text, tables, render pages/regions, scan OCR |
| DOCX | Paragraphs, headings, sections, tables, images, hyperlinks, metadata |
| XLSX | Sheets/ranges/cells, types/formulas/cached values, merges, tables, metadata |
| PPTX | Slides, text, object relationships, images, tables, metadata |
| PNG/JPEG/WebP | Inspect, transform, region access, OCR |
| TIFF/GIF | Inspect, applicable frame access, transform, OCR |
| SVG | Safe inspect, restricted rendering, region access, OCR of rendered content |

Report optional Office rendering, charts, comments, speaker notes and hidden structures where supported. Audio/video and specialized engineering formats remain optional extensions.

## PC-041: Format detection and deterministic selection

**Status:** Accepted. **Authority:** AD-380, AD-389, AD-420, TC-025.

Select processing by actual signatures and validated structure, requested capability, format, provider, scope and remaining budget. Report mismatches and limitations. No filename-only assumptions. Prefer suitable deterministic extraction; format detection is distinct from acquiring original bytes.

## PC-042: Selective progressive processing

**Status:** Accepted. **Authority:** AD-384–385, AD-412, AD-420, TC-027–028.

Inspect before expensive work; select pages, sections, cells, slides, regions or frames as applicable. Use bounded find, read and continuation under stable capture/representation locators. Avoid full-document expensive processing where selective processing is supported. No mandatory embeddings or generative LLM.

## PC-043: Native, layout-aware and complex PDF processing

**Status:** Accepted. **Authority:** AD-385–386, AD-420, TC-029–030.

Support native text, layout-aware reading order/columns, tables, page/region rendering and scanned-page OCR. Select appropriate methods per page/region and request. pypdf and pypdfium2 are recommended native/render candidates; Docling is an initial layout candidate. Complex processing capability required; a specific third-party model is not. Preserve original PDF and deterministic representations separately from optional model interpretation.

## PC-044: Technical material and table fidelity

**Status:** Accepted. **Authority:** AD-383, AD-386, TC-029.

Preserve table structure, headers, rows/columns, merged cells, units, mathematical notation, symbols, code and source locators as available. Mark uncertain/inferred structures and missing values; never invent cells. Internal table representations map to adopted public schema, which remains authoritative.

## PC-045: Office processing

**Status:** Accepted. **Authority:** AD-388–389, TC-026–030.

DOCX preserves headings, sections, paragraphs, tables, images, hyperlinks and metadata. XLSX preserves worksheet/cell addresses, types, formulas, cached results, merges, named tables and metadata; cached formula values are not recalculated values. PPTX preserves slides, text, shapes/object relationships, images, tables and metadata. Report notes, charts, hidden structures, comments and rendering where supported. No macro execution, automatic external references or automatic external formula recalculation.

## PC-046: Deterministic image transformations

**Status:** Accepted. **Authority:** AD-387, AD-391–394, TC-031–032.

Provide format/dimension/metadata inspection, bounded crop/resize/thumbnail/rotate/convert, region and applicable frame access. Each new image is immutable derived content with parent, geometry/orientation and transformation attribution. Preserve original image, including embedded media; separate OCR and visual interpretation.

## PC-047: Replaceable OCRProvider

**Status:** Accepted. **Authority:** AD-369, AD-385, AD-387, AD-418, TC-033.

Use asynchronous recognize(request: OCRRequest, context: ProviderExecutionContext) -> OCRResult. Request identifies authorized image/region/frame, language preferences, bounds and applicable provider selection. Return original-language recognized text, locations, reading order, applicable language, method, provider confidence and limitations. Confidence is provider-specific, not directly comparable. Tesseract is recommended; evaluate compatible alternatives.

## PC-048: Optional IntelligenceProvider

**Status:** Accepted. **Authority:** AD-369, AD-383, AD-385, AD-387, AD-418, AD-422, TC-033.

Use asynchronous interpret(request: IntelligenceRequest, context: ProviderExecutionContext) -> IntelligenceResult for optional vision, document_interpretation, summarization, model-assisted OCR and translation. Preserve source-language text and original/deterministic representations. Reconcile optional model-assisted OCR and translation invocation against exact adopted Tool Schemas in PC-5; no silent expansion of public contract.

## PC-049: Native Ollama and OpenAI-compatible adapters

**Status:** Accepted. **Authority:** AD-369, AD-421–422.

Support native Ollama and OpenAI-compatible adapters for operator-authorized endpoints (e.g. Ollama, vLLM, llama.cpp where compatible) and documented custom integrations. Configure instance endpoint, model, capabilities, credential reference, timeout and concurrency limits. Multiple endpoints optional; inference may be entirely disabled. Local or remote inference requires authorization; no hosted AI service, bundled runtime or model weights required.

## PC-050: CPU baseline and optional acceleration

**Status:** Accepted. **Authority:** AD-369, AD-418–420, AD-424.

CPU-only core, native extraction and basic OCR required. Compatible optional acceleration or external inference may use operator-managed NVIDIA, AMD, Intel or Apple Silicon hardware; Grenslan does not mandate a particular GPU vendor or runtime inside the core container. Validate platform availability and maintain deterministic operation without optional inference.

## PC-051: Intelligence attribution and disclosure

**Status:** Accepted. **Authority:** AD-369, AD-383, AD-390–392, AD-401, AD-421, TC-033.

Attribute optional generated outputs to actual model, provider, material configuration, processing method and source artifact/locator. Distinguish from original bytes, source text, native extraction, conventional OCR and deterministic tables. Only send authorized necessary content to approved destinations under disclosure policy, including local inference. Never turn model output into execution authority.

## PC-052: Untrusted processing and resource safeguards

**Status:** Accepted. **Authority:** AD-389, AD-400–403, AD-412, AD-421.

Restrict filesystem/network access, CPU, memory, deadlines, expansion, pixels, recursion, output, temporary storage and cancellation. Disable macros, automatic external references and active content; harden XML/SVG. Parser inputs cannot grant access to other files or network resources. Release resources safely and report stage-specific limitations.

## PC-053: Original-artifact fallback and partial results

**Status:** Accepted. **Authority:** AD-380, AD-389, AD-394–395, AD-420, TC-034.

On unsupported/partial extraction, OCR/inference failure, budget exhaustion or incompatible licensing, preserve available authorized valid completed portions and deliver authorized original artifact where safe and permitted. Distinguish acquisition from processing failure. Do not claim uninspected content exists. Fallback does not waive required compatible capabilities or security, access, disclosure and resource limits.

## PC-054: Processor evaluation, licensing and portability

**Status:** Accepted. **Authority:** AD-419–420, AD-422, AD-424, AD-426–427.

Reference candidates: Trafilatura and lxml for HTML; native Python text, Markdown/compatible parser, JSON, CSV/TSV; restricted lxml/defusedxml; pypdf/pypdfium2 and Docling for PDF; Pillow/restricted SVG renderer; Tesseract; python-docx/openpyxl/python-pptx. Marker, MinerU, Surya and PaddleOCR remain evaluation candidates, not distribution requirements. Validate versions, fidelity (including tables, reading order, symbols), selective processing, CPU/memory/latency, optional acceleration, licensing, redistribution, platform/security and offline compatibility before pinning. No license-incompatible dependency or mandatory startup download.

## PC-055: Canonical provider interface version and types

**Status:** Accepted. **Authority:** AD-367, AD-418–422; PC-001–003.

Use internal provider contract version 1.0, independent of public wire, product and MCP versions. The companion PROVIDER_INTERFACES.py contains declaration-only Python dataclasses, aliases and structural Protocol signatures. It is a specification, not runtime code or an instruction to introduce new dependencies. Actual implementation may use equivalent validated types, but must preserve all fields, union discrimination, signatures, invariants and behavior. Use immutable typed request/response records; no untyped upstream payload crosses the boundary. Breaking provider contract changes require explicit review/version change. Adapter registration verifies supported contract version before execution.

All provider execution methods are asynchronous internally, including worker dispatch for blocking operations. Public browser actions remain synchronous at the public contract boundary. Common lifecycle methods: synchronous describe() for static metadata, asynchronous initialize(), health(), shutdown() with bounded LifecycleContext. Registration validates implementation identity, declared family, contract version, capability-to-method compatibility, approved build/dependency manifest and platform. ProviderDescription describes an installed implementation; the registry assigns the configured provider_id and applies effective configuration/authorization separately.

## PC-056: Capability declarations, lifecycle and dispatch

**Status:** Accepted. **Authority:** AD-368, AD-370–371, AD-416, AD-418–422; PC-003–010.

Use the typed CapabilityDeclaration vocabulary. Search categories and filters are dimensions of search.query, not separately required implementation methods. Format and method dimensions qualify content/OCR capabilities; support flags and limitations identify selective work and model-assisted processing. A declared unsupported or disabled capability cannot be invoked merely through a different method. Providers implement only applicable content subprotocols; validate registry declarations against their callable methods at startup. The six family contracts and browser controller/engine component protocols are:

| Interface | Execution methods | Result types |
|---|---|---|
| SearchProvider | search | SearchResult |
| RetrievalProvider | retrieve | RetrievalResult |
| BrowserProvider | create_session, navigate, observe, interact, screenshot, close_session | BrowserSession, BrowserPage, Observation, InteractionResult, Screenshot |
| BrowserEngine (internal component) | launch, terminate | EngineHandle |
| BrowserController (internal component) | attach, navigate, observe, interact, screenshot, detach | BrowserSession, BrowserPage, Observation, InteractionResult, Screenshot |
| ContentProcessor and optional subprotocols | inspect, read, find, extract_tables, render, extract_media, transform | Inspection, ReadResult, FindResult, TableResult, DerivedResult, Derived |
| OCRProvider | recognize | OCRResult |
| IntelligenceProvider | interpret | IntelligenceResult |

Use operator-configured ordered route lists filtered for actual requested capability, format, deployed health, authorization, disclosure and budget. Explicit provider preference does not authorize an instance and unavailable explicit selection cannot be silently substituted if it would change requested observation. Core may coordinate bounded authorized fallback and deterministic composition; providers do not invoke arbitrary tools. Lifecycle state: uninitialized -> initializing -> ready/degraded/unavailable; configured disabled never admits work; operational transitions are allowed where health changes; stopping -> stopped. Reconfiguration and controlled restart are sufficient. Probe health within bounded operator-approved destinations, not arbitrary request-supplied URLs. Required failure is explicit; optional provider failure must not prevent unrelated startup or core operation. Map per-capability state to public enabled/disabled/unavailable/unsupported only for authorized consumers.

## PC-057: Scoped execution context, budgets and resource access

**Status:** Accepted. **Authority:** AD-396–405, AD-408–414, AD-421; PC-005, PC-009, PC-030, PC-036, PC-052.

ProviderExecutionContext includes only request/operation identity, configured provider identity, effective monotonic deadline, Limits, scoped budget handle, permitted input resources, ResourceAccess, cooperative Cancellation, network/disclosure scope IDs and approved credential reference when applicable. Full authenticated consumer context stays in the core. Limits is immutable but budget_handle refers to a core-enforced shared budget; copies cannot create more capacity. Nested/parallel work reserves and consumes the same enclosing allocations. Deadline is monotonic within its clock domain; when crossing process boundaries convert to remaining bounded duration using trusted runtime, not wall-clock estimates. All provider calls, IPC, subprocess work, retries, staging and transfer count toward effective budget. Cancellation is cooperative plus enforceable termination when necessary; no provider may independently extend time, permissions or allocation.

InputResource handles refer to authorized immutable byte representations with known size/digest. ResourceAccess.read streams scoped bytes; stage accepts bounded asynchronous byte chunks for a new output. Handles are not filesystem paths, URL credentials or public artifact IDs. Core enforces ownership, revocation, integrity, byte/temporary storage limits and read protection. Staging is never public; validate content, digest and authorization atomically before public reference. Close/discard failed staging safely. Provider-declared digest is not authoritative until verified. Worker-local temporary files are permissible only in isolated scoped storage, not arbitrary caller paths. Cross-process adapters serialize validated records and use scoped authenticated IPC/capability handles; do not transmit executable objects or use untrusted deserialization. Cancellation and ResourceAccess Protocols are trusted runtime interfaces, not serialized Python callables from consumers. Actual process, independent egress and filesystem protection must be demonstrated.

## PC-058: Typed results, failures and attribution

**Status:** Accepted. **Authority:** AD-378, AD-383–394, AD-408–414, AD-418–421; PC-007–008, PC-023–024, PC-053.

ProviderResult[T] has outcome, typed value (optional where failure or no-payload shutdown), and issues. Completed requires an applicable valid typed result (except explicitly no-value operations); partial requires valid partial payload and at least one issue; failed/cancelled/timed_out/interrupted require issues, may preserve valid partial payload and never claim completion. Provider-specific exceptions are contained and mapped to IssueCode; issue messages must be safe, bounded and free from secrets or unrelated state. Public status, provider attribution and request ID derive from the core, not untrusted result declarations. A provider may not publish a public source/capture/artifact/citation/operation ID or make authoritative truth/trust claims. Core validates incoming records, resource handles, coverage, artifact lineage, identity, enums, timestamps and bounded fields. Actual source and capture identity, requested/final URLs, observed UTC timestamp, actual route/cache, method and representation are assigned/preserved in public normalization. Provider state does not equal invocation outcome.

Discovery requires a valid URL for web results or an image/source-page URL for image results; source-provided snippets are not captured evidence. ScalarFields allows unique named bounded scalar metadata only, mapped to accepted public schema fields; private/unknown fields are not automatically exposed. Preserve source order and upstream attribution. SearchResult includes actual observation time and known upstream cache condition (unknown is valid); core records its own caching independently. Provider continuation tokens are scoped to the configured instance and translated to opaque core continuations; a provider lacking snapshot-stable results must report material pagination limitations, not claim immutable search snapshot. Cache-only work uses eligible core-retained data without live adapter invocation. Revalidation and independent fresh retrieval retain separate timestamps/conditions; if upstream caching is not controllable, report that limitation, never claim independent observation of origin bytes without evidence.

RetrievalResult.not_modified requires conditional validation and no new original, not a fabricated byte download. Incomplete body must not be published as a complete original; explicitly labeled partial bytes, if safe and useful, may be delivered under a distinct representation and limitations. BrowserDownload records requested/final URL and observation time separately from enclosing page. Core assigns page/capture IDs, verifies staged outputs and prevents stale element interactions. Find/quotation mismatch only with complete inspected scope. Validate selection, coordinate and locator conventions against TC-051; original/cached spreadsheet values remain distinct, uncertain values marked, model outputs separately attributed. The provider family operation and actual declared capability determine result validation; no generic arbitrary JSON return or silent source rewriting.

## PC-059: Operator configuration schema and ownership

**Status:** Accepted. **Authority:** AD-404, AD-416, AD-422–427; PC-002–004, PC-010–011.

PROVIDER_CONFIG_SCHEMA.json defines the provider/execution portion of versioned operator YAML in JSON Schema Draft 2020-12. It is not the entire service-deployment schema (TLS ingress, consumer credentials, logging and unrelated deployment controls remain implementation/PRP specifications). Validate before admission or controlled restart, reject unknown core keys, enable URI format checks, reject duplicate YAML keys and unsafe/custom executable tags, and fail clearly on invalid mandatory configuration. Apply documented environment overrides through the same validation; never load arbitrary code or use model-retrieved content as configuration.

Required top-level fields: config_version, deployment_mode, limits, providers, routing, network_scopes, disclosure_scopes, credential_refs, browser_profiles, optional_intelligence_enabled, cache. Each provider instance is keyed by configured ID and has family, approved implementation ID, enabled flag and limit overrides. Optional endpoint, credential reference, network/disclosure policy and family-specific settings are schema-validated. adapter_settings is additionally validated against an approved adapter-specific closed schema; unrecognized fields are rejected there. No raw secret values in ordinary configuration or schema diagnostics. Credentials refer to protected operator-managed secret sources, not arbitrary caller paths; restrict use to approved provider purpose and destination scope. A private CA reference is a protected deployment reference. Endpoint URL must not contain userinfo or secret query parameters. Numeric default and load targets remain implementation validation choices; required global limits are explicit, provider overrides can only reduce effective global/parent limits.

Cross-field checks are normative in addition to JSON Schema: provider IDs uniquely resolve approved installed implementations of matching family/version; routing entries exist, are family-compatible, and only enabled/authorized instances execute; all scope references exist; credential purpose and destination scope agree; every enabled network-capable provider has applicable approved network/disclosure policy (including bundled SearXNG upstream); local/offline modes deny prohibited egress regardless of configured route; approved external endpoints require policy match; actual network connections independently enforced; configured profile exists and is compatible with engine; default and allowed profiles agree; model-assisted OCR references an enabled compatible intelligence provider with model_ocr support, plus optional-intelligence master switch; disabled optional components cannot invoke inference. Empty routing allowed in restricted/offline profiles, but connected reference distribution includes adopted required provider implementations and ordinary research capability; disabled/unavailable capabilities reported. Limits are positive where applicable, retries/redirects may be zero, with sane operator maximums and resource validation. No auto-download to fix missing providers.

## PC-060: Registration, dependency and release validation

**Status:** Accepted. **Authority:** AD-404, AD-419, AD-422–427; PC-004, PC-011, PC-054.

Use an explicit operator-controlled registry of built-in implementations and approved installed extension registrations. Configuration selects implementation IDs, not executable path/module expressions. Extension registration requires documented package/adapter entrypoint, declared provider family, contract/version and capability inventory, platform support, approved settings schema, actual integrity and license evidence, tests and operator approval; no runtime marketplace, executable download, arbitrary reflection or unreviewed replacement. Keep dependency manifest identifier in ProviderDescription; core records actual pinned versions/digests, applicable transitive notices, binaries, model weights if distributed, source/license references, allowed platforms and known limitations. Include applicable license information as accessible container documents and README/repository links. Test offline installation with approved included dependencies. Alternative browsers or processors failing applicable compatibility, licensing, sandboxing or resource validation remain unavailable; reference-required capability must be satisfied through a compatible implementation. Pin actual dependency versions in milestone-specific reproducible release records, not from speculative examples.

## PC-061: Browser runtime boundary and validation

**Status:** Accepted. **Authority:** AD-375–377, AD-399–405, AD-412, AD-419, AD-424; PC-025–038.

BrowserProvider composes a BrowserEngine and BrowserController only through registered compatible components. EngineLaunch carries approved engine, isolated worker handle and validated profile, never raw launch flags from public consumer. Controller attach establishes internal session handle. Core owns public browser_session_id/page_state_id mapping, per-context session resource scope and effect authorization handle. Interact requires validated current session/page state plus typed action and independently granted effect scope; authorized effect handle is core-generated and not consumer-controlled. Invalidate handles when relevant state changes, confirm before action and reject uncertain effect outside scope. Provider execution may not bypass sandbox, network policy, browser security or source restrictions. Transient sessions close after capture; explicit sessions have bounded state and lifetime. Separate downloads preserve source and actual bytes. Screenshots include captured page state and immutable staged image. Do not replay or silently replace failed active sessions. Validate Chromium/Playwright and Clearcote Open/Brave Origin separately by supported platform, headless behavior, isolation, license, profile consistency, dynamic rendering and bounded cleanup; no conformance claim before actual fixtures.

## PC-062: Processing capability and format conformance

**Status:** Accepted. **Authority:** AD-380–389, AD-420–421; PC-039–054.

PC-040 format matrix remains minimum service capability inventory; registry must declare the applicable inspect/read/find/table/render/media/transform and OCR operations across enabled implementations, not force each implementation to support formats it cannot process. Use validated actual format and selector; route by operation and available method. A caller requests an operation, not a parser executable. Core can implement deterministic find over available normalized bounded text rather than require every adapter to implement it. Core may compose rendering + OCR, layout + tables or native extraction + optional interpretation under a shared budget. Native methods preserve source language, structure, locators and fidelity even when optional model processing is disabled. Processing outputs must describe their actual source representation and method. Missing/unavailable content is explicit; no imaginary cells, inferred native text or claims of exact search coverage from incomplete observations. Model-assisted OCR is optional and explicitly opted in; deterministic OCR is the default and available without inference. Model-based interpretation/translation is attributed and does not overwrite original or deterministic passages. Format, operation and platform minimums are not waived by optional fallback. Original authorized bytes delivered under existing policy on failure where safe.

## PC-063: Inference and cross-contract reconciliation (TC-057 adopted)

**Status:** Accepted. **Authority:** AD-369, AD-383, AD-385, AD-387, AD-401–402, AD-421–422; PC-047–051.

The adopted architecture allows optional translation and model-assisted OCR. Review of the adopted TC-5 registry identified a narrow gap: the public interpretation option only lists vision, document_interpretation and summarization, and OCR has no explicit opt-in for model-assisted processing. Accepted TC-057 amends only the following three definitions in active TOOL_SCHEMAS.json. The original 56 decisions remain in force.

| Definition | Adopted refinement |
|---|---|
| document_read_input | Add interpretation capability translation with required nonempty target_language; add optional allow_model_assisted_ocr (default false) and ocr_provider, with explicit method=ocr required for opt-in or provider selection. |
| image_ocr_input | Add optional allow_model_assisted (default false); provider preference remains available. |
| Processing | Add optional model_assisted, target_language and bounded safe material_configuration name/value list; require provider/model/material_configuration for generated outputs or model-assisted OCR. Model-assisted OCR has kind=ocr; translations have kind=generated. |

Translation operates on the authorized selected content through document_read, returns source-language and separate attributed translated representation (bounded or referenced), and requires explicit target language and authorized enabled provider. No automatic translation or silent editing. A consumer wishing to translate text obtained from an image can submit the recognized text as an authorized supplied text artifact through the existing upload interface, then request translation of that artifact. No additional image_ocr result fields are introduced. Model-assisted OCR may be routed through an OCRProvider wrapping an approved IntelligenceProvider model_ocr operation; explicit opt-in, applicable capability, provider authorization and disclosure are required, including for local endpoints. If it is unavailable, report limitation and preserve ordinary OCR/native/original availability; no hidden model invocation.

For generated text and model-assisted OCR, material_configuration contains only actual material non-secret values, e.g. target language, model settings and documented provenance; omit secrets/endpoint internals and unrelated identities. Empty list only if no safely disclosable material settings beyond already attributed fields; restrictions disclosed as appropriate. Validate safe scalar types and bound lengths/counts. Material configuration and actual provider/model attribution preserved on every derived result. Model output untrusted data, not execution authority. Optional inference remains disabled by default in reference deployment.

No new tool or architecture decision: TC-057 is an adopted pre-implementation refinement of the initial wire contract 1.0. No released v1.0 client compatibility relied upon. All other schema definitions and 32-tool registry records remain unchanged.

## PC-064: Cross-interface mapping and mandatory validation

**Status:** Accepted. **Authority:** AD-367, AD-390–395, AD-417–421, AD-428–432.

Provider contracts are internal, not MCP tools. Each public operation invokes the core, which maps typed public request to the relevant provider operation or core composition, and validates public result schema before returning.

| Public tool(s) | Primary provider / core composition |
|---|---|
| web_search, image_search | SearchProvider.search; core constraint disposition, normalization, ranking, cursor, optional bounded retrieve composition |
| web_open | RetrievalProvider.retrieve or transient BrowserProvider; ContentProcessor as requested |
| web_read, web_find, web_links | Core on retained content; Read/Find/InspectProcessor and structured links |
| web_traverse | Core bounded traversal over retrieval/browser and link processing |
| browser_session_create/navigate/observe/interact/screenshot/session_close | BrowserProvider six methods and core authorization/lifetime/handle mapping |
| document_open, image_open | Core ingest/retrieve, actual format detection, InspectProcessor as applicable |
| document_inspect, image_inspect | InspectProcessor; image optional interpretation via IntelligenceProvider |
| document_read, document_find, document_tables | Read/Find/TableProcessor; OCR/layout/intelligence composition as explicitly allowed |
| document_render, document_media, image_transform | Render/Media/TransformProcessor |
| image_ocr | OCRProvider.recognize; optional approved model-assisted adapter |
| artifact_get, citation_get | Core authorized resource/citation resolution; no provider recapture |
| source_verify, quotation_verify | Core independent acquisition/integrity/deterministic quotation composition |
| capabilities_get | Core registry/configured health/effective authorized capability projection |
| operation_status/results/cancel | Core execution lifecycle |

## PC-065: Architecture traceability and provider conformance

**Status:** Accepted. **Authority:** AD-417–427.

The following review-level mapping identifies primary architecture and acceptance criteria. It does not add or renumber tests or waive cross-cutting obligations.

| PC decisions | Primary ADs | Primary existing T criteria |
|---|---|---|
| PC-001–004, PC-055–056, PC-059–060 | AD-368, AD-404, AD-416, AD-418–419, AD-422–427 | T-386, T-433, T-449, T-451–452, T-459–462, T-464 |
| PC-005–010, PC-057–058 | AD-396–405, AD-408–414, AD-421 | T-419–433, T-437–446, T-458 |
| PC-011, PC-054, PC-060 | AD-419, AD-422–427 | T-460, T-462; architecture packaging/platform/license suite |
| PC-012–018 | AD-370–373, AD-418–419, AD-423, AD-425 | T-388–391, T-397–398, T-451–452, T-461, T-485–486 |
| PC-019–024 | AD-374, AD-377–380, AD-398–401, AD-408–409, AD-412 | T-392, T-396–399, T-411–413, T-426–430, T-438, T-453 |
| PC-025–038, PC-061 | AD-375–377, AD-399–405, AD-419, AD-424 | T-392–396, T-424–428, T-432, T-444, T-454, T-462, T-472 |
| PC-039–046, PC-052–054, PC-062 | AD-380–389, AD-420 | T-400–410, T-455–456, T-463 |
| PC-047–051, PC-063 | AD-369, AD-383, AD-385, AD-387, AD-401, AD-421–422 | T-384, T-387, T-403, T-407, T-430, T-457, T-464, T-494 |
| PC-064 | AD-367, AD-390–395, AD-428–432 | T-385, T-411–418, T-450, T-481–503 |

Provider conformance fixtures must include compatible/unsupported constraints, successful empty and unavailable results, rate limits, redirect/DNS/private-destination denial, revoked scope, independent fresh retrieval, stale browser state, process/worker isolation, format-specific representative fixtures, malicious macros/XML/SVG, decompression and resource limits, partial extraction and original fallback, optional inference disabled, disclosure restrictions, licensed alternatives and offline operation. All architecture tests remain applicable and unexecuted. Validate pinned external API versions/rate limits, actual dependencies/license notices, resource ceilings, platform availability and security mechanisms in the appropriate milestone; never claim test success from declaration/schema checks.

## PC-066: Acceptance and implementation gate

**Status:** Accepted. **Authority:** AD-417, AD-432; Master PRP.

Design checks performed: typed interface declaration file compiled and loaded under Python 3.12; six family protocols and two browser component protocols present. Provider configuration meta-schema validation passed; two structurally valid representative configurations and six invalid configurations exercised. Accepted TC-057 schema changes limited to three definitions, inventory unchanged; changed definitions validated and eleven targeted request/attribution checks passed. These are design checks, not runtime security, provider, parser or transport conformance. No production implementation, actual upstream API validation or release dependency pinning occurred. Cross-field configuration and execution enforcement remain implementation requirements, not checked merely by the JSON Schema.

PC-055 through PC-066 and TC-057 are accepted. The Provider Contract, interface declarations, config schema, amended Tool Contract and Tool Schemas are active specifications. Historical review revisions are preserved. The adopted canonical repository layout is docs/contracts/ for both contracts and companions; AGENTS.md and Master PRP point to those files. Architecture and decision register remain in docs/. This is an editorial location reconciliation, not a code change. PRP-001-FOUNDATION must be reviewed and foundation-affecting implementation choices resolved before service coding. No architecture decision ID or T criterion is newly adopted.

## Review plan

| Round | Scope | Status |
|---|---|---|
| PC-1 | Common interfaces, registration and execution boundaries | Accepted |
| PC-2 | Search and HTTP retrieval providers | Accepted |
| PC-3 | Browser providers and session management | Accepted |
| PC-4 | Document processing, OCR and optional intelligence | Accepted |
| PC-5 | Configuration, provider specifications and conformance | Accepted |

Architecture Revision 12, Checkpoint 011 and adopted public Tool Contract remain unchanged. No runtime conformance tests have been executed.
