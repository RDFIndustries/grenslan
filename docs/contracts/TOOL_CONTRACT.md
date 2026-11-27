# Grenslan v0.1: Tool Contract

| Attribute | Value |
|---|---|
| Project | Grenslan |
| Owner | RDF Industries, Inc. |
| Architecture baseline | v0.1, Revision 12, Checkpoint 011 |
| Contract revision | 06 |
| Review round | TC-5 and TC-057 amendment |
| Status | Adopted: TC-001 through TC-057 |
| Date | 2026-11-26 (Pacific) |

This is the adopted public Tool Contract. It consolidates the accepted common, discovery, web retrieval, browser, document, image, delivery, verification and operation decisions. It does not replace the adopted architecture or decision register or claim conformance. TC identifiers track contract refinements; they do not consume architecture decision IDs. Examples in TC-001 through TC-046 are historical illustrations of accepted direction; the companion machine-readable registry TOOL_SCHEMAS.json and TC-5 and TC-057 semantic rules govern exact wire details. Service implementation remains gated by the adopted Master PRP, including Provider Contract and PRP-001 approval.

## TC-001: MCP protocol and transport

**Status:** Accepted. **Authority:** AD-367, AD-428, AD-431.

Implement only the stable MCP revision current at implementation/release time; pin and document the exact supported protocol and compatible Python MCP SDK. At review, the official current revision is 2026-07-28 (see [specification](https://modelcontextprotocol.io/specification/2026-07-28) and [Streamable HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)). This is a review reference, not a permanent version pin. Use Streamable HTTP exclusively over HTTPS for consumer-facing MCP network communication. No legacy transport or insecure fallback. Follow the pinned protocol's request metadata, negotiation, error and cancellation rules.

Grenslan-managed browser sessions, operations and artifacts are explicit authorized application resources, not MCP protocol sessions. Core asynchronous research uses Grenslan operation references and does not require the optional MCP Tasks extension. The architecture's TLS, certificate, authorization, Origin and network requirements remain in force.

## TC-002: Common public service contract

**Status:** Accepted. **Authority:** AD-367, AD-428, AD-429.

MCP, REST, Python SDK and CLI express one typed service contract. SDK and CLI are clients of authorized public service interfaces; they do not replicate service execution or bypass authorization.

Accepted routing direction:

- `POST /mcp`: standards-compatible MCP endpoint.
- `POST /api/v1/tools/{tool_name}`: equivalent REST tool invocation.
- `GET /api/v1/artifacts/{artifact_id}`: authenticated binary artifact delivery.

TC-047 through TC-056 and the companion registry reconcile tool names, routes and typed schemas. All consumer-facing network interfaces require HTTPS.

## TC-003: Authenticated consumer context

**Status:** Accepted. **Authority:** AD-396–398, AD-405, AD-428, AD-431.

Establish the authorized context independently for each protected request, not from an MCP connection or model-supplied claims. The server derives application identity and effective permissions from authenticated credentials and validated trusted context. A trusted consuming application may assert users, agents and instances within its authorized namespace. Scope object access and execution to the appropriate context. Credentials, application identity and authorization fields are not ordinary model-controlled tool arguments.

| Context field | Meaning |
|---|---|
| application_id | Authenticated application namespace |
| user_id | User identity within the namespace |
| agent_id | Optional agent identity |
| instance_id | Optional agent or application instance identity |
| permissions | Server-established effective permissions |
| request_id | Server-assigned invocation identifier |

Support lightweight authorized application credentials and standards-compatible MCP authorization. External authorization-server integration is configurable but not mandatory for all deployments. Credentials for clients without delegated identities establish an operator-defined context; missing identity information cannot broaden access. TC-048 defines the authenticated context transport/binding and authorization profiles. Identically named agents in different contexts remain isolated.

## TC-004: Request arguments and execution options

**Status:** Accepted. **Authority:** AD-368, AD-410–412, AD-429.

Simple invocations require only tool-specific necessary parameters. Applicable tools may expose shared optional execution controls. Supported options include `mode` (sync or explicitly async), `timeout_ms`, `max_output_bytes`, and `max_download_bytes` where applicable. All requested limits are constrained by server/operator policy, capability, enclosing budget and authorization. Defaults and numerical caps require implementation validation. A consumer cannot enlarge its permissions or multiply enclosing budgets through nested work.

Illustrative request:

```json
{
  "query": "titanium alloy fatigue characteristics",
  "category": "academic",
  "max_results": 20,
  "execution": {
    "mode": "sync",
    "timeout_ms": 30000
  }
}
```

## TC-005: Common response envelope

**Status:** Accepted. **Authority:** AD-390, AD-411, AD-428–430.

The typed application result carries `schema_version`, `request_id`, `status`, an applicable tool-specific `result` or operation reference, and `issues`. MCP exposes machine-readable results through structuredContent and appropriate protocol content blocks; REST provides equivalent JSON semantics. Protocol and authentication errors follow the applicable standards; do not disguise them as successful research responses.

Illustrative completed search with no results:

```json
{
  "schema_version": "1.0",
  "request_id": "req-123",
  "status": "completed",
  "result": {"results": []},
  "issues": []
}
```

Common outcomes: completed, partial, accepted, failed, cancelled, timed_out, interrupted. An empty successful result is distinct from an outage or denied request. The companion registry and TC-050 define discriminators and error mappings.

## TC-006: Resource identities

**Status:** Accepted. **Authority:** AD-391–394, AD-397, AD-430.

Distinguish request_id (invocation), operation_id (async work), source_id (source identity), capture_id (particular observation), artifact_id (retained original or derived representation), browser_session_id (application browser session), and citation_id (reference to attributable captured material).

Public identifiers are opaque, server-generated and do not expose internal paths, credentials or database structure. Possession of an identifier does not establish authorization. Preserve distinct observations even when their bytes are identical; a new representation does not overwrite another capture. IDs do not imply indefinite retention or a permanent archive.

## TC-007: Explicit execution lifecycle

**Status:** Accepted. **Authority:** AD-410–414, AD-429.

Default execution is synchronous. Explicit async requests may return an authorized, bounded operation reference with the accepted status and current state, then support operation_status, operation_results and operation_cancel. Operation state is distinct from the outcome of a request to inspect the operation.

States: queued, running, completed, partial, failed, cancelled, timed_out, interrupted. Report effective mode and available authorized partial results. Never silently detach synchronous requests. Document disconnect, expiration, cancellation and restart behavior; durable job recovery is not required.

Illustrative async acceptance:

```json
{
  "schema_version": "1.0",
  "request_id": "req-124",
  "status": "accepted",
  "operation": {"operation_id": "op-456", "state": "queued"},
  "issues": []
}
```

## TC-008: Errors and limitations

**Status:** Accepted. **Authority:** AD-371, AD-378, AD-389–390, AD-411–412, AD-428–430.

Machine-readable issues identify failures and limitations while preserving authorized successful partial results. Common initial code vocabulary: invalid_request, unsupported_capability, unauthorized, access_restricted, provider_unavailable, rate_limited, network_error, retrieval_failed, extraction_failed, resource_limit, artifact_expired, integrity_error, timeout, cancelled, interrupted, internal_error. Issue descriptors may include a safe message, retryability and applicable provider. The companion registry defines the complete issue schema and vocabulary. Errors must not leak unauthorized resources, secrets or sensitive internals.

## TC-009: Authorized URI-first artifact delivery

**Status:** Accepted. **Authority:** AD-391–395, AD-397, AD-430.

Use the Grenslan-managed `grenslan://` resource URI scheme, e.g. `grenslan://artifacts/example`. A URI identifies a retained resource rather than an original source URL or bearer credential. Support authorized MCP resources/read and HTTPS artifact download to obtain retained original bytes when available.

Large documents and artifacts default to reference delivery with available decision-useful metadata, provenance, excerpts and limitations. Descriptors include available media type, byte size, actual SHA-256 digest, expiry and other applicable metadata required by AD-430. Unknown values are not fabricated. Bounded inline text and multimodal representations may be provided when appropriate. Every resolution enforces authorization, applicable expiry and integrity. The companion registry defines artifact, supplied-file ingestion and citation schemas.

## TC-010: Normalized search request and result contracts

**Status:** Accepted. **Authority:** AD-370–371, AD-390, AD-418–419, AD-429.

`web_search` requires a query. Optional arguments: category, providers, max_results, language, region, date_from, date_to, include_domains, exclude_domains, file_types, safe_search, ranking, cursor, retrieve and execution; applicable freshness policy from TC-015. Categories: general, news, images, video, academic, software, patents, government, documents, technical, local, enterprise, products and maps. Providers independently declare capabilities and categories.

Normalize source URL and identifier, available title and provider snippet, provider and upstream engine, original rank, optional aggregated rank, publication date, author/organization, media type, category-specific metadata and available thumbnail reference. Do not fabricate unknown metadata or represent discovery snippets as captures.

## TC-011: Search constraint disposition

**Status:** Accepted. **Authority:** AD-371, AD-429.

Report requested constraints and their effective disposition, distinguishing provider-applied, locally applied, partially applied and unsupported constraints. Do not silently ignore a requested filter. Example constraint descriptor: `{"name":"file_types","status":"unsupported"}`. TC-5 defines the exact disposition vocabulary and semantics.

## TC-012: Ranking, aggregation and deduplication

**Status:** Accepted. **Authority:** AD-372–373.

Initial ranking modes: provider_order, relevance, recency. Default to original provider order for one provider and transparent relevance-based aggregation for multiple providers. Recency uses available dates. Retain original provider attribution and rank. No generalized source-trust or ideological, political, philosophical, economic or religious ranking. Deduplicate conservatively, preserve attribution and distinguish redirection, identical content and possible syndication where detectable. Duplicate discovery results are not independent corroboration.

## TC-013: Deterministic search-and-retrieve composition

**Status:** Accepted. **Authority:** AD-368, AD-412, AD-429–430.

`web_search` may receive an optional retrieve object specifying max_sources and representation, subject to authorized limits. Select up to the requested number of eligible discovered sources according to effective ordering and retrieve them deterministically. Return discovery and retrieval attribution independently; report item-specific failures. Nested operations share the enclosing execution budget. No autonomous formulation of research questions or conclusions.

```json
{
  "query": "titanium alloy fatigue characteristics",
  "category": "academic",
  "max_results": 20,
  "retrieve": {"max_sources": 3, "representation": "text"}
}
```

## TC-014: Image discovery

**Status:** Accepted. **Authority:** AD-371, AD-387, AD-390.

`image_search` requires query. Optional providers, max_results, include_domains, exclude_domains, language, region, safe_search, min_width, min_height, cursor and execution, plus applicable freshness. Return available original image and source-page URLs, thumbnail reference, title/caption/description, dimensions, media type, provider attribution and licensing information. Metadata does not establish original availability or permission to reuse. Do not automatically acquire full-resolution originals merely because they appear in discovery. Use image_open for acquisition.

## TC-015: Pagination and freshness

**Status:** Accepted. **Authority:** AD-371, AD-379, AD-391, AD-408–409.

Use opaque, expiring continuation cursors scoped to authorized context and applicable request parameters. A cursor confers no authorization. Expose applicable freshness policies: default (operator policy), cache_only (eligible retained material, no live access), revalidate (check retained resource currency), fresh_independent (independent live observation bypassing incompatible caching/coalescing). Report actual observation and cache provenance. Apply freshness where relevant to search and acquisition; inspection of a specific retained capture must not silently refresh it.

## TC-016: Web acquisition

**Status:** Accepted. **Authority:** AD-374, AD-377–379, AD-390, AD-412.

`web_open` accepts a url or bounded urls batch, with optional route (auto, http, browser), representation, freshness, render and execution. Auto prefers direct HTTP when sufficient; browser escalation is authorized only to satisfy retrieval/rendering needs, not to bypass restrictions. Each batch item has independently attributable retrieval results and failures. Enclosing execution budgets apply to all items. Return available capture information and representations; preserve distinctions from discovery metadata.

## TC-017: Capture-specific web inspection

**Status:** Accepted. **Authority:** AD-382–384, AD-390–392, AD-394.

- `web_read`: resource_uri; optional section/heading, character range, max_chars, continuation and applicable execution controls. Read already acquired content; do not silently initiate a live capture.
- `web_find`: resource_uri, query; optional maximum matches and context_chars. Literal match by default; bounded regex an optional capability. Return matching text, surrounding context, locators and source/capture attribution. No embedding dependency.
- `web_links`: return discovered links from a captured resource with original and resolved URL where available. Optional internal/external, domain, file type, maximum results and anchor-text filters; bounded continuation as applicable. Link discovery grants no retrieval authority.

Missing or expired captures report explicit unavailable outcomes rather than quietly substituting a new observation.

## TC-018: Bounded traversal

**Status:** Accepted. **Authority:** AD-377, AD-400, AD-412.

`web_traverse` accepts a starting URL and bounded traversal controls, including max_depth, max_pages, include_domains and enclosing execution limits. Default traversal boundary is the starting host; additional destinations require explicit request and existing authorization. Enforce visited-resource tracking, depth, count, time, download, destination limits and cancellation. Report partial traversal and known limitations. No autonomous research planning.

## TC-019: Isolated browser lifecycle

**Status:** Accepted. **Authority:** AD-375–376, AD-398–403, AD-412.

- `browser_session_create`: optional authorized browser_provider, identity_profile, viewport, lifetime_ms and credential_ref. Default isolated and ephemeral; internally consistent operator-approved identity profile through session lifetime. No arbitrary launch arguments, agent-installed executable or changed network policy.
- `browser_navigate`: browser_session_id, URL, optional bounded wait_until/readiness controls including supported selector-based conditions. Preserve available observations with explicit incompleteness on deadline.
- `browser_session_close`: close authorized session, release execution resources; do not automatically destroy separately retained authorized artifacts. Expired/revoked sessions are not reusable.

Application browser handles are distinct from MCP protocol sessions and remain scoped to authorized context. Use approved worker isolation and independent network control.

## TC-020: Structured browser observations

**Status:** Accepted. **Authority:** AD-376, AD-391, AD-397–399.

`browser_observe` exposes bounded structured page information: title, current URL, rendered text, headings/links, accessibility-oriented elements, interaction handles, optional DOM representation and screenshot reference. Identify page-state revision. Element handles are bound to session and page state; reject stale handles rather than silently remapping them.

## TC-021: Typed browser interactions

**Status:** Accepted. **Authority:** AD-376, AD-396–405, AD-412.

`browser_interact` accepts browser_session_id, page_state_id and a discriminated typed action. Initial action vocabulary: scroll, click, fill, select, press. Do not expose arbitrary script execution. Validate session/page/element handles and applicable authorization, and bound actions. Ordinary research authorization does not grant authentication, state-changing external form submissions, uploads, publishing, purchases, messages or record modification. Require distinct authorization; deny or request expanded authorization if effect cannot reasonably be established within the granted scope. HTTP method alone does not establish that an action is harmless.

## TC-022: Browser screenshots

**Status:** Accepted. **Authority:** AD-376, AD-387, AD-391–394, AD-430.

`browser_screenshot` captures an authorized page observation: viewport, bounded full page, selected region or identified element. Default to resource-reference delivery, with bounded inline image representation where appropriate. Record browser session, page state, timestamp and source URL with the resulting artifact. Verify authorized access, limits and expiry.

## TC-023: Unified authorized document and image inputs

**Status:** Accepted. **Authority:** AD-380–381, AD-391, AD-395, AD-397, AD-420.

Document and image acquisition accepts remote URLs, existing authorized artifact URIs, authorized supplied-file resources and browser-acquired artifacts. Validate authorization, retrieval policy and input type independently of the source form. Supplied and retained content may be processed without external network access where the operation permits. Identify supplied origin distinctly from a live capture. Arbitrary caller-specified host paths confer no access.

## TC-024: Direct authenticated file upload

**Status:** Accepted. **Authority:** AD-389, AD-394–395, AD-397, AD-408–409, AD-428, AD-430.

Provide an authenticated HTTPS `POST /api/v1/uploads` interface for direct file transfer by a client without placing file bytes in an agent's tool-call context. Return an authorized opaque artifact URI and available metadata. Apply scoped authorization, ingestion limits, integrity hashing, validation, temporary storage and expiry. An MCP consumer with the appropriate authorization may subsequently use the resource URI in document/image tools. TC-052 and the companion registry define upload transport and response.

## TC-025: Separation of acquisition and processing

**Status:** Accepted. **Authority:** AD-380–381, AD-390–392, AD-420, AD-430.

`document_open` acquires or registers an authorized document, detects its actual format from content and structure, and returns available MIME type, byte size, SHA-256, title, author, language, page/sheet/slide counts, source and capture identifiers, original artifact URI, processing capabilities and limitations. Report material format discrepancies. Do not require full extraction, OCR or AI inference during opening. Unknown metadata remains unknown. Large originals default to reference delivery with available relevant data and attributed source-supplied descriptions or optional derived summaries, not mandatory model-context payloads.

## TC-026: Format-aware structural inspection

**Status:** Accepted. **Authority:** AD-381–385, AD-388, AD-420.

`document_inspect` exposes bounded available structure: PDF pages/bookmarks/sections/content types; DOCX headings/sections/paragraphs/tables; XLSX worksheets/populated ranges/tables/named ranges; PPTX slides/titles/notes/objects; HTML/XHTML headings/sections/links/tables; JSON/XML hierarchy; CSV/TSV columns/records/types; Markdown headings/sections/links/code blocks; plain-text structure as applicable. Disclose what was actually inspected, unknown values and unsupported sub-capabilities.

## TC-027: Selective reading and stable locators

**Status:** Accepted. **Authority:** AD-382–386, AD-388, AD-392, AD-430.

`document_read` extracts selected pages/regions, sections/headings, paragraphs, sheet/cell ranges, slides, structured paths or record ranges as applicable. Support appropriate methods such as auto, native, layout or OCR when available. Preserve source language, structure, headings, links, lists, tables, technical notation and code where supported. Return stable capture- and representation-specific locators, bounded output, continuation or derived artifacts. No silent source rewriting or translation.

Illustrative request:

```json
{
  "artifact_uri": "grenslan://artifacts/example",
  "selection": {"pages": [12, 13, 14]},
  "method": "auto"
}
```

## TC-028: Bounded document search and coverage

**Status:** Accepted. **Authority:** AD-383–385, AD-390, AD-412, AD-430.

`document_find` searches an available captured document using literal matching by default. Optional bounded regex support is permissible. Accept a query, applicable scope, case-sensitivity and match limits. Return matching text, surrounding context, locators, processing method, inspected coverage and continuation where applicable. Distinguish complete no-match from incomplete search. No semantic search or embeddings required.

## TC-029: Structured table extraction

**Status:** Accepted. **Authority:** AD-382, AD-385–386, AD-388, AD-392, AD-420.

`document_tables` returns structured tabular data, preserving available headers, row/column relationships, units, cell values/types, merged cells, formulas, cached spreadsheet values, source locators and extraction uncertainty. A stored formula result is not a newly calculated value. Do not invent missing cells or flatten away material table structure. Preserve partial valid results and uncertainty.

## TC-030: Document rendering and media extraction

**Status:** Accepted. **Authority:** AD-385–389, AD-391–394, AD-420.

`document_render` renders selected PDF pages/regions and slides, document pages or worksheet regions where supported. Use one-based public page/slide indexing and explicitly defined region coordinate systems; enforce size and processing limits. Return a separate derived artifact with source relationship.

`document_media` discovers/extracts embedded images, diagrams stored as image objects, attachments and supported multimedia objects. Preserve parent-document relationship and source location. Extraction authorizes neither execution of embedded content nor automatic external retrieval. Format-specific rendering and media sub-capabilities must be reported accurately.

## TC-031: Original image preservation and inspection

**Status:** Accepted. **Authority:** AD-380–381, AD-387, AD-390–392, AD-420.

`image_open` acquires or registers an authorized image and returns its original resource reference and available metadata. Preserve original bytes independently of any transform. `image_inspect` provides available format, dimensions, color space, transparency, orientation, resolution metadata, frame count, embedded metadata, size and integrity hash. Deterministic inspection does not require AI interpretation; separately requested interpretation remains attributable.

## TC-032: Immutable image transformations

**Status:** Accepted. **Authority:** AD-387, AD-389, AD-391–394, AD-430.

`image_transform` produces new artifacts for bounded crops, resizes, thumbnails, rotations and format conversions where supported. Define geometry, coordinate space, orientation and aspect-ratio behavior explicitly. Record source/parent and transformation history; never modify original or earlier retained representations. Use reference-first delivery for large results.

Illustrative request:

```json
{
  "artifact_uri": "grenslan://artifacts/example",
  "operation": "thumbnail",
  "max_width": 800,
  "max_height": 800,
  "preserve_aspect_ratio": true
}
```

## TC-033: OCR and attributed optional interpretation

**Status:** Accepted. **Authority:** AD-383, AD-385–387, AD-390, AD-420–421.

`image_ocr` extracts visible text from an image or selected region, returning available recognized text, detected language, bounding boxes, reading order, provider-specific confidence, method, source reference and uncertainty. Document OCR follows equivalent attribution. Do not silently correct, translate or reinterpret extracted source text. Core deterministic processing and OCR require no generative LLM. Optional document/visual interpretation or semantic summarization must be separately requested, authorized and distinguished from source content, with applicable model/provider/method attribution. No external generative AI service is mandatory.

## TC-034: Processing safeguards and original artifact fallback

**Status:** Accepted. **Authority:** AD-381, AD-389, AD-395, AD-400–403, AD-412, AD-420, AD-430.

Treat all input content as untrusted. Enforce file size, decompression, memory, CPU, deadline, pixel, recursion, output and storage bounds. Prohibit macro and embedded script execution; harden XML/SVG processing and restrict access to external resources. Cover the adopted format inventory (HTML/XHTML, plain text, Markdown, JSON/XML, PDF, DOCX, XLSX, CSV/TSV, PPTX, PNG, JPEG, WebP, TIFF, GIF, SVG). Support does not imply every operation works on every format; report capabilities and limitations without waiving adopted minimum requirements.

When processing is unavailable, fails or exceeds the applicable budget, return the authorized original artifact, available metadata and valid partial results where safe and allowed. Distinguish processing failure from acquisition failure. Never claim to have inspected unavailable content; preserve authorization, security and resource limits.

## TC-035: Standard artifact descriptors and derivation

**Status:** Accepted. **Authority:** AD-391–394, AD-430.

Every retained artifact has a standardized descriptor: opaque artifact ID and URI, applicable source/capture IDs, representation, available filename, media type, byte size, actual SHA-256, creation and expiration timestamps, availability, and available decision-useful source metadata. Derived artifacts identify parent artifacts and processing methods. Preserve distinct captures, originals and derived representations; authorized internal deduplication may share bytes, not observation identity.

## TC-036: Authorized artifact delivery

**Status:** Accepted. **Authority:** AD-394, AD-397, AD-428, AD-430.

artifact_get supports reference (default), bounded inline and download (an authorized HTTPS transfer reference). GET /api/v1/artifacts/{artifact_id} delivers retained bytes; supported MCP resources/read provides authorized resource access within applicable limits. Both enforce object authorization, integrity, disclosure and expiry. A URI, download URL, identifier or digest is not a bearer credential.

## TC-037: Retention and expiration

**Status:** Accepted. **Authority:** AD-394, AD-408–409, AD-411, AD-414.

Bound artifact, capture, citation, browser-session and operation-result lifetimes independently. Declare artifact expiration and availability. Protect active authorized reads from ordinary eviction without overriding revocation. Explicitly report expired or missing resources; do not silently replace evidence. Consumers retain their own authorized durable copies. No permanent archive required.

## TC-038: Capture-specific citation descriptors

**Status:** Accepted. **Authority:** AD-391–394, AD-430.

citation_get returns available source/capture/representation identity, source metadata, capture time, precise format-appropriate locator, bounded excerpt, extraction attribution and availability. Discovery metadata is not captured evidence. No permanent bibliography or citation-style generator required.

## TC-039: Independent source retrieval and comparison

**Status:** Accepted. **Authority:** AD-379, AD-391, AD-393, AD-413.

source_verify fresh mode makes an independent live observation, not reuse of an incompatible cached/shared observation. Compare mode retrieves anew and compares against an authorized prior capture, reporting timestamps, representation-specific hashes, retrieval conditions, identical or changed bytes, supported requested differences and limitations. Do not suppress contradictions.

## TC-040: Representation-specific integrity verification

**Status:** Accepted. **Authority:** AD-392–393, AD-409.

source_verify integrity mode hashes retained bytes and compares against recorded or explicitly expected digest; return findings and missing/corrupt outcomes. Integrity is not semantic truth, authenticity or claim verification.

## TC-041: Deterministic quotation verification

**Status:** Accepted. **Authority:** AD-383–384, AD-392–393.

quotation_verify checks supplied text against an authorized available representation and optional scope. Exact is default; optional explicitly reported whitespace, line-break or Unicode normalization. Outcomes exact_match, normalized_match, mismatch, inconclusive, unavailable. Mismatch requires full inspection of the requested scope. Return locators, methods and limitations; no LLM required.

## TC-042: Authorization-aware capability discovery

**Status:** Accepted. **Authority:** AD-368, AD-397, AD-416, AD-429.

capabilities_get exposes effective available functions, formats, provider capabilities and limitations, with states enabled, disabled, unavailable and unsupported. Report only appropriately authorized information; no secrets or private topology. Optional provider failure does not disable unrelated core functions.

## TC-043: Configurable tool profiles

**Status:** Accepted. **Authority:** AD-368, AD-397, AD-429.

Basic, technical, advanced, full and operator-defined custom profiles expose appropriate tools under applicable authorization. Visibility is not authority. The basic profile includes web_search, web_open, web_read, web_find, image_search and artifact_get; technical adds document and verification, advanced adds explicit browser interaction, full exposes enabled and authorized functions.

## TC-044: Operation status and progress

**Status:** Accepted. **Authority:** AD-410–412.

operation_status returns authorized operation state and available progress; no fabricated percentage when workload is unknown. States queued, running, completed, partial, failed, cancelled, timed_out, interrupted. The request outcome differs from operation state.

## TC-045: Operation results and partial delivery

**Status:** Accepted. **Authority:** AD-394, AD-411–412, AD-430.

operation_results returns authorized bounded available results, including partial results, continuations and artifact references. Execution state is independent of result availability; a running operation may have usable output and a completed operation may have expired output.

## TC-046: Cancellation and restart

**Status:** Accepted. **Authority:** AD-405, AD-411–414.

operation_cancel requests scoped cancellation; stop eligible work, notify workers, release resources, preserve authorized partial results and report irreversible or uncertain actions. Optional shared work must survive cancellation by one subscriber when still authorized for another. Unrecoverable restart state is interrupted or unavailable, not completed; no durable job scheduler or replay required.

## TC-047: Canonical schema registry and versioning

**Status:** Accepted. **Authority:** AD-367, AD-390, AD-428–430.

The companion `TOOL_SCHEMAS.json` is the canonical public registry of 32 tools. Each tool record names the tool, description, inputSchema, outputSchema, asynchronous availability and requirement traceability. JSON Schema Draft 2020-12 is the adopted schema dialect. Use the referenced definition as the schema root and include all reachable shared definitions under local `$defs`; no remote schema fetch is required. Expose the resulting self-contained object schema through MCP discovery and use the same input/output validation for REST. The registry itself is a catalog, not the schema for a tool invocation. Schema version 1.0 identifies the wire contract, independent of product version 0.1.0 and MCP protocol revision. Breaking wire changes require an explicitly reviewed incompatible contract revision.

Unknown request properties are rejected. Optional fields are absent unless supported and applicable; do not fabricate empty strings, zero counts or dates for unknown metadata. An explicit null is only allowed where the schema permits it (e.g. a cell value). Tool and result objects are closed; supported provider-specific data use typed normalized fields, not arbitrary unvalidated output. New metadata fields require contract review. Provider internal objects never cross this boundary.

## TC-048: Interface and authentication binding

**Status:** Accepted. **Authority:** AD-367, AD-396–398, AD-405, AD-428, AD-431.

| Interface | Contract |
|---|---|
| MCP | `POST /mcp`, Streamable HTTP over HTTPS, with protocol-defined additional methods and streaming handled according to the pinned current stable specification |
| REST tools | `POST /api/v1/tools/{tool_name}`, JSON request equal to the tool input object; application response equal to its output envelope |
| Artifact delivery | `GET /api/v1/artifacts/{artifact_id}`, authenticated binary transfer |
| Direct ingestion | `POST /api/v1/uploads`, authenticated raw binary request and typed UploadResult |
| MCP retained resource | `resources/read` on the returned Grenslan resource URI, subject to limits |
| SDK/CLI | Clients of these interfaces; no direct storage/provider access |

All network ingress is HTTPS with the TLS requirements of AD-428. Implement pinned MCP protocol negotiation, authorization, transport and errors according to the stable specification verified at release; no legacy fallback.

Controlled integration profile: use `Authorization: Bearer <credential>` on each protected HTTP request. The service validates either operator-issued application credentials or configured MCP-compatible access tokens according to the applicable profile. A credential binds application namespace and permissions. For trusted delegated integrations only, optional `Grenslan-User-Id`, `Grenslan-Agent-Id` and `Grenslan-Instance-Id` headers convey scoped identities. Header names are case-insensitive; duplicate, ambiguous or invalid values are rejected. These are deployment-specific trusted application extensions, not MCP protocol fields. Credentials must explicitly authorize delegation; reject claims outside the credential namespace. Without delegation, the credential establishes the operator-defined context. No model-controlled tool argument can convey identity, permissions, secrets or trust-domain overrides. Validate authorization per request and recheck policy/revocation throughout protected work and resource delivery. The application credential is not an administrative credential.

MCP tool discovery exposes only the permitted configured profile. MCP structuredContent carries the canonical envelope; compatible content blocks provide bounded text or image as negotiated/appropriate without duplicating large payloads. MCP protocol/authentication errors use the pinned specification; ordinary tool failures return the canonical failed application outcome, with the protocol tool-error indication where appropriate. REST/SDK/CLI preserve identical application semantics.

## TC-049: Request validation, constraints and limits

**Status:** Accepted. **Authority:** AD-368, AD-371, AD-389, AD-400–403, AD-410–412, AD-429.

Validate JSON types, enums, required fields, conditional selectors and formats before provider execution (enable format validation). Validate semantic constraints that depend on values or server state: dates ordered; ranges ordered; region within bounds; selected indices exist; formats and methods supported; compatible selector combinations; batch sizes and limits within policy; cursor and original parameters/context match. Unrecognized or meaningless combinations are invalid rather than silently ignored. URL schema permits outbound HTTP/HTTPS only; independent network authorization, DNS, redirect and destination checks are still mandatory. Resource URI syntax never establishes object access. Bound string lengths, collection lengths, input bytes, output bytes, CPU, worker admission, memory, decompression and elapsed time under operator policy; numeric maxima/defaults require implementation validation. Values such as browser lifetime and deadline may reduce effective limits but cannot override them. Return material requested/effective discrepancies as issues or constraint dispositions.

Search pagination reuses query and filters with the returned cursor; it does not silently reinterpret the request or initiate a new snapshot. Requests with cursor/continuation must identify the same scope and resource. Omitted constraints are server defaults; unsupported requested constraints are disclosed, not silently dropped. Default literal search is case-insensitive unless explicitly requested otherwise. Quotation verification is case-sensitive by default. Exact matching never uses fuzzy or model judgment.

## TC-050: Typed outcome and error mapping

**Status:** Accepted. **Authority:** AD-378, AD-390, AD-411–412, AD-428–430.

Every tool envelope requires `schema_version`, `request_id`, `status`, `effective_mode`, and `issues`. Completed and partial require a tool-specific result; partial requires an explanatory issue. Failed, cancelled, timed_out and interrupted require at least one issue and may include valid authorized partial results. Accepted requires an initial queued/running operation reference and async effective mode, not a result. A genuine empty result is completed with the empty typed array and not a provider failure. Resource-specific findings and operation state are distinct from the status of the current invocation.

For REST tool calls: valid synchronous application outcomes use HTTP 200; async acceptance uses 202. HTTP 400 for malformed input/invalid invocation, 401 for missing/invalid credentials, 403 for denied authentication scope where safe to disclose, 404 for unknown or undisclosable protected objects, 409 for conflicting state where disclosure is authorized, 413 for excessive request body, 429 for service admission/rate limitation, and 503 for service-level unavailability. Return the typed failure envelope where an invocation can safely be identified; transport-level failures may not yield a complete envelope. Never disclose unauthorized object existence via error text or distinctions. For authenticated artifact downloads, 200 returns binary bytes, 404 undisclosed/missing object, 410 explicitly expired authorized object where safe, 409 integrity conflict, and other applicable error statuses. HTTP status and issue code are complementary. Upstream retrieval errors, including upstream HTTP failures, normally belong in the tool outcome rather than being blindly forwarded as service transport status. Preserve retryability and safe retry-after information where available. No unbounded retries or hidden fallback.

## TC-051: Capture, locator and continuation semantics

**Status:** Accepted. **Authority:** AD-382–394, AD-408–409, AD-430.

Artifact, capture and citation identities are distinct and immutable. Captures identify requested/final URL for web acquisition and a supplied origin for imports; capture time is actual observation time, not cached access time. Derived artifacts identify parent artifact(s), method and provenance. Sources, captures, artifacts, operations and cursors are opaque scoped identifiers; no physical paths. Source content is untrusted data, never instructions.

Public page, slide, frame, paragraph, spreadsheet row and column and record indices are one-based. Character offsets are zero-based Unicode code-point offsets, half-open [start,end), in the specified immutable text representation; paragraph and record Range values use one-based half-open intervals, with start >= 1. Normalized regions are top-left origin, x/y/width/height in [0,1] with extent within bounds; pixels refer to the displayed oriented reference image and points to the selected rendered page coordinate space (1/72 inch), also top-left. A pixel or point region must identify its reference representation where ambiguity is possible. Apply requested native/visible orientation explicitly and preserve transformation mapping. Worksheet names use exact source names; cells use A1 notation. Structured JSON paths use JSON Pointer; XML paths use a restricted non-executing element/attribute path with one-based sibling positions, no arbitrary query evaluation. Format-incompatible selectors are rejected.

Continuation tokens are opaque, expiring, scoped to authorized context, tool, original request, capture/representation and pagination position. No implicit live recapture. Report omissions and coverage, with continuation only if more bounded material is available. Token estimates are labeled estimates; byte limits are authoritative. Preserve provenance on every page. Mismatch/no-match may assert absence only over completely inspected requested scope. Normalize quotations only using explicitly selected and reported transformations. Do not mark an incomplete search as full.

## TC-052: Binary delivery and upload semantics

**Status:** Accepted. **Authority:** AD-389, AD-392–395, AD-397, AD-408–409, AD-428, AD-430.

Resource URI form is `grenslan://artifacts/<opaque-id>`. A reference is not a bearer credential, nor a public file URL. Descriptors declare actual retained bytes' size, media type and SHA-256 when available; unavailable fields are omitted. Authorized originals are returned as exact retained bytes, not an extracted substitute. Download links resolve to configured service HTTPS origin and contain no reusable secret, internal hostname or path. `artifact_get` download returns a route reference; the consumer chooses whether to fetch it. The GET endpoint returns actual media type and exact bytes with content length when known; stream transfer with bounded buffering. Range requests are not required by this contract. Inline delivery is bounded and may be refused with explicit limits and an authorized reference. MCP resource access returns the applicable protocol binary/text representation within limits, never forces full documents into a model tool result.

Upload uses an HTTPS authenticated `application/octet-stream` body; optional `Grenslan-File-Name` header is a sanitized display label only, never a path. Stage bytes, enforce upload limits, compute digest, detect format, validate and publish the reference atomically only after success. Return HTTP 201 with UploadResult on success; scoped failures follow TC-050, with no published incomplete artifact. No multipart or arbitrary host path required. Supplied origin and acquisition time remain attributable. Core processing can operate on retained content offline. Protection against ordinary eviction during an active read does not override revocation.

## TC-053: Browser and operation lifecycle

**Status:** Accepted. **Authority:** AD-375–376, AD-399, AD-405, AD-410–414.

Browser session operations are synchronous in this contract to avoid ambiguous concurrent interaction ordering. Bound their wait and processing costs; require current page-state handle for state-bound interactions and screenshots. Concurrent actions on the same session are serialized or explicitly rejected as conflicting; no silent remapping stale handles. Actions are typed, scoped and validated against actual authorized effects. No arbitrary script, implicit authentication or state-changing authority. Browser sessions are explicit Grenslan resources, not MCP transport sessions.

Other tools may request explicit async mode where the registry declares support. Management and lightweight reference/capability/citation operations are synchronous. Synchronous disconnection cancels eligible work rather than silently detaching; report observable partial or uncertain irreversible outcomes where subsequently available. Async acceptance returns an initial state snapshot (the operation may progress before the consumer receives it). The separate operation state reports actual work progress, not the HTTP/tool invocation state. Operation results preserve originating tool name, typed result, operation issues and independently declared availability. Terminal states do not transition back to running. Cancellation requests are idempotent for already-terminal authorized operations, report disposition and preserve partial results. Cancellation does not imply reversal. Expiry/restart/revocation may make references unavailable; no durable workflow queue or replay mandated.

## TC-054: Profiles and provider-independent handling

**Status:** Accepted. **Authority:** AD-368–369, AD-370–373, AD-416, AD-418–422, AD-429.

Basic profile includes web_search, web_open, web_read, web_find, image_search, artifact_get and capability/operation support as authorized. Technical additionally includes document and image processing, web_links, web_traverse and verification/citations; advanced adds browser operations; full exposes all enabled and authorized tools; custom operator selection is allowed. Capability discovery is available under applicable authentication irrespective of ordinary research profile and reports only authorized information. A profile constrains exposure; effective permission remains enforced separately. Operator administration remains outside ordinary agent tools.

Search defaults to general category; one provider defaults to provider_order, multiple to transparent relevance aggregation. Freshness defaults to operator policy and reports actual observation/cache history. Optional requested inference requires scope, approved provider, available capability, attribution, disclosure controls and applicable limits. Distinguish generated output, deterministic extraction, OCR and source-supplied metadata. No ideological or generalized trust ranking, semantic truth score, hidden translation or autonomous research conclusions. Provider selection, model/weight licensing and actual processing implementations remain for Provider Contract and validation; no new mandatory inference or external runtime dependency.

## TC-055: Evidence verification and consistent findings

**Status:** Accepted. **Authority:** AD-379, AD-391–394, AD-413.

Fresh and compare source verification cause a new authorized retrieval, bypass incompatible cache/coalescing, and record actual capture conditions. Compare identifies reference capture and new representation; identical/changed is scoped to matching representation bytes, not semantic agreement. Verify the prior capture is authorized and independently identify missing evidence. Integrity mode hashes retained bytes and compares against the stored or explicitly requested expected digest; missing/corrupt information is explicit. Quotation checks use the chosen available representation and requested scope; match locators resolve that representation. For normalized checks report every transformation (whitespace collapses runs; line_breaks maps line endings to LF; unicode_nfc applies NFC; apply requested transformations in listed order). Normalized occurrence is not exact occurrence. Contradictions are not suppressed; integrity, quotation occurrence and independent retrieval are not truth or authenticity guarantees. No permanent claim/custody database.

## TC-056: Traceability and validation boundary

**Status:** Accepted. **Authority:** AD-417, AD-428–432.

The schema registry records primary accepted TC, AD and T references for each of the 32 tools. Common requirements apply across every tool: authentication/isolation AD-396–405 (T-419–433, T-490–492); resource/budget handling AD-406–414 (T-434–447); interfaces AD-367, AD-428–431 (T-385–386, T-481–493, T-495–503); provenance AD-390–395 (T-411–418); format/fidelity AD-380–389 (T-400–410). The registry is not a replacement for the adopted acceptance register. Provider, deployment, licensing, portability and infrastructure criteria retain their independent applicability even when not mapped to a particular tool. Architectural test IDs remain unchanged and unexecuted. Schema validation is design verification, not service conformance.

### Tool inventory and primary traceability

| Tool | Accepted contract decisions | Primary architecture decisions | Primary acceptance criteria | Execution |
|---|---|---|---|---|
| `web_search` | TC-010, TC-011, TC-012, TC-013, TC-015 | AD-370, AD-371, AD-372, AD-373, AD-379, AD-429 | T-388, T-389, T-390, T-391, T-397, T-398, T-399, T-461, T-485, T-486 | Sync / async |
| `image_search` | TC-011, TC-014, TC-015 | AD-371, AD-387, AD-390 | T-389, T-407, T-486 | Sync / async |
| `web_open` | TC-015, TC-016 | AD-374, AD-378, AD-379, AD-390, AD-412 | T-392, T-397, T-399, T-411, T-453 | Sync / async |
| `web_read` | TC-017 | AD-382, AD-383, AD-384, AD-392, AD-430 | T-401, T-404, T-489 | Sync / async |
| `web_find` | TC-017 | AD-384, AD-392 | T-404, T-414 | Sync / async |
| `web_links` | TC-017 | AD-376, AD-382, AD-384 | T-394, T-401 | Sync / async |
| `web_traverse` | TC-018 | AD-377, AD-400, AD-412 | T-396, T-426, T-427, T-444 | Sync / async |
| `browser_session_create` | TC-019 | AD-375, AD-399, AD-403 | T-393, T-424, T-425, T-454, T-462 | Sync |
| `browser_navigate` | TC-019 | AD-374, AD-376, AD-400, AD-412 | T-392, T-396, T-426, T-427 | Sync |
| `browser_observe` | TC-020 | AD-376, AD-391, AD-397 | T-394, T-424 | Sync |
| `browser_interact` | TC-021 | AD-376, AD-397, AD-400, AD-402, AD-405, AD-412 | T-394, T-395, T-431 | Sync |
| `browser_screenshot` | TC-022 | AD-376, AD-387, AD-392, AD-430 | T-394, T-488 | Sync |
| `browser_session_close` | TC-019 | AD-399, AD-405, AD-412 | T-424, T-444 | Sync |
| `document_open` | TC-023, TC-024, TC-025, TC-034 | AD-380, AD-381, AD-395, AD-420, AD-430 | T-400, T-402, T-418, T-463, T-497 | Sync / async |
| `document_inspect` | TC-026 | AD-381, AD-382, AD-385, AD-388 | T-400, T-405, T-408 | Sync / async |
| `document_read` | TC-027, TC-033, TC-034 | AD-383, AD-384, AD-385, AD-388, AD-420 | T-403, T-404, T-405, T-408, T-455, T-456, T-489 | Sync / async |
| `document_find` | TC-028 | AD-384, AD-390, AD-412 | T-404, T-415 | Sync / async |
| `document_tables` | TC-029 | AD-386, AD-388, AD-392 | T-405, T-406, T-408 | Sync / async |
| `document_render` | TC-030 | AD-385, AD-388, AD-389, AD-394 | T-405, T-455, T-488 | Sync / async |
| `document_media` | TC-030 | AD-387, AD-388, AD-389 | T-408, T-409 | Sync / async |
| `image_open` | TC-023, TC-031, TC-034 | AD-380, AD-387, AD-391, AD-420 | T-402, T-407, T-418 | Sync / async |
| `image_inspect` | TC-031, TC-033 | AD-387, AD-390, AD-421 | T-407, T-457, T-488 | Sync / async |
| `image_transform` | TC-032 | AD-387, AD-389, AD-391, AD-394 | T-407, T-410, T-412 | Sync / async |
| `image_ocr` | TC-033, TC-034 | AD-383, AD-387, AD-389 | T-403, T-407, T-410 | Sync / async |
| `artifact_get` | TC-035, TC-036, TC-037 | AD-392, AD-394, AD-397, AD-430 | T-413, T-417, T-421, T-439, T-487, T-490, T-497, T-498 | Sync |
| `source_verify` | TC-039, TC-040 | AD-379, AD-392, AD-393, AD-413 | T-399, T-413, T-416, T-446 | Sync / async |
| `quotation_verify` | TC-041 | AD-383, AD-384, AD-392, AD-393 | T-415 | Sync / async |
| `citation_get` | TC-038 | AD-391, AD-392, AD-394 | T-414 | Sync |
| `capabilities_get` | TC-042, TC-043 | AD-368, AD-416, AD-429 | T-386, T-449, T-452, T-484 | Sync |
| `operation_status` | TC-044 | AD-410, AD-411, AD-412 | T-420, T-443 | Sync |
| `operation_results` | TC-045 | AD-394, AD-411, AD-412, AD-430 | T-420, T-443, T-489 | Sync |
| `operation_cancel` | TC-046 | AD-405, AD-411, AD-412, AD-413, AD-414 | T-422, T-444, T-445, T-446 | Sync |

### Design validation performed

- All 32 tools match the architecture inventory and reference 124 shared definitions.
- All schema definitions validated against the Draft 2020-12 meta-schema using jsonschema; local references resolve.
- All 32 representative minimal/normal tool requests validated; all 32 forged application-context requests rejected.
- 13 additional invalid cases rejected (including conflicting source selectors, host file paths, zero page index, arbitrary browser script, async browser navigation, missing crop geometry and invalid verification requests).
- Eight envelope/result assertions checked completed, partial, accepted, failed and typed operation-result behavior.
- No runtime service, authorization enforcement, network isolation, parser behavior, transport, TLS or architecture acceptance tests have been executed. Numeric deployment limits, exact pinned MCP revision/SDK and provider implementations still require implementation-stage validation.

### Acceptance boundary

TC-047 through TC-056 and the companion registry are accepted; TC-057 supplements the contract. Designate this contract and registry as active implementation documents (`docs/contracts/TOOL_CONTRACT.md` and `docs/contracts/TOOL_SCHEMAS.json`); retain historical review revisions in the archive if desired. The Provider Contract has subsequently been accepted. Next review: PRP-001-FOUNDATION. No service implementation begins merely by adopting this contract.

## TC-057: Explicit optional translation and model-assisted OCR

**Status:** Accepted. **Authority:** AD-369, AD-383, AD-385, AD-387, AD-401–402, AD-421–422; PC-063.

This is the adopted pre-implementation amendment to wire contract 1.0. No new tools or architecture decisions. The following three schema definitions change; all other definitions and tool registry records remain unchanged.

- document_read_input: interpretation capability translation requires nonempty target_language; optional allow_model_assisted_ocr (default false) and ocr_provider require method=ocr when opt-in is true or a provider is selected.
- image_ocr_input: optional allow_model_assisted (default false); existing provider preference remains supported.
- Processing: optional model_assisted, target_language and bounded safe material_configuration name/value list. Generated outputs and model-assisted OCR require actual provider/model/material_configuration; model-assisted OCR kind is ocr, translation kind is generated with target_language.

Translation acts only on authorized selected content, explicitly requested with target language, and returns original-language content and separate attributed translated content, bounded or referenced. A consumer may submit recognized image text as an authorized supplied text artifact and request translation. No silent translation, replacement or source rewriting. Conventional OCR is default. Model-assisted OCR requires explicit opt-in, compatible enabled authorized provider and applicable disclosure, even for local endpoints. Preserve native/conventional/original availability and report limitations when optional intelligence fails. Material configuration records actual non-secret material settings, bounded scalar name/value pairs with unique names; secrets, private endpoints and unrelated identities are excluded. Empty list is allowed only when no safely disclosable material settings beyond existing attribution apply, with limitations reported as appropriate.

The canonical TOOL_SCHEMAS.json incorporates this amendment. Eleven targeted request/attribution assertions passed at design review; no runtime conformance claimed. All 32 public tools remain. For internal routing and attribution see PROVIDER_CONTRACT.md PC-063.

## Review record

| Round | Scope | Status |
|---|---|---|
| TC-1 | Common interface, context, execution and resource identity | Accepted |
| TC-2 | Search, web retrieval and browser | Accepted |
| TC-3 | Document and image processing | Accepted |
| TC-4 | Artifact delivery, citations, verification and operations | Accepted |
| TC-5 | Reconciliation, complete public schemas and conformance | Accepted |
| TC-057 | Optional translation and model-assisted OCR amendment | Accepted |

Architecture Revision 12 and Checkpoint 011 remain unchanged; no new architecture decision or acceptance criterion is adopted here. No runtime conformance tests have been executed. This revision is the adopted Tool Contract implementation baseline; no architecture acceptance test has been executed.
