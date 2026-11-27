# Grenslan — Active Architecture Decision Register

| Attribute | Value |
|---|---|
| Project | Grenslan |
| Owner | RDF Industries, Inc. |
| Product version | 0.1 |
| Document revision | 12 |
| Documentation checkpoint | 011 |
| Date | 2026-11-25 (Pacific) |
| License | Apache-2.0 (original Grenslan code) |
| Status | Adopted foundational architecture through Round 10; project naming adopted |

## Register authority

This register contains only the active requirements of the current Revision 12 baseline. Earlier IDs AD-001–364 are historical/reserved and SHALL NOT be reused. The archived Revision 7 register and the separate reconciliation crosswalk retain historical context. No historical decision imposes an independent implementation obligation. AD-365–417 are accepted as part of the approved narrowed scope; AD-418–422 are accepted in Round 8 with the customer amendments; AD-423–427 are accepted in Round 9 with the internal SearXNG and distribution-license amendments. AD-370 and AD-415 are reconciled to the adopted internal SearXNG deployment. AD-428–432 are accepted in Round 10, including current MCP-only compatibility, URI-first large-artifact delivery and mandatory HTTPS for consumer-facing network interfaces. AD-367, AD-394, AD-396, AD-401 and AD-415 are read together with these adopted refinements; AD-428 and AD-430 govern the more specific transport and artifact requirements. AD-433 is accepted following the project naming review, superseding the working designation Agent Research Engine (ARE) with Grenslan. It changes project identity only; AD-365–432 and their existing acceptance criteria remain in force. Exact consolidated wording is editorial implementation of those approvals. New changes require explicit review.

| Active decisions | Active acceptance criteria | Next decision | Next test |
|---:|---:|---|---|
| 69 | 120 | AD-434 | T-504 |

## Purpose and public contracts

### AD-365 — Independent research service

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL be a self-hosted, standalone, multi-user search, retrieval and content-processing service. Original Grenslan code SHALL use Apache-2.0; third-party licenses SHALL be respected. Python is the reference implementation; other languages MAY be used.

### AD-366 — Consumer boundary

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL deliver results to the authorized requesting consumer. Consumers own reasoning, agent orchestration, long-term evidence retention, cognitive memory, embeddings and knowledge indexing. Grenslan SHALL NOT require a research archive, vector corpus, graph database, agent runtime or generative LLM. Core research SHALL operate without GPU acceleration.

### AD-367 — Interfaces and contracts

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL expose versioned provider-independent MCP and REST contracts and supported Python SDK and CLI interfaces. All interfaces SHALL apply the same authorization, resource and execution rules. SDK and CLI SHALL NOT bypass the service boundary in the reference deployment.

### AD-368 — Tool discovery and composition

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL expose capabilities and limitations, atomic tools and bounded batches or deterministic compositions. Human use and limited-model tool profiles SHALL be supported. Grenslan SHALL NOT autonomously plan an agent’s research objectives or require persistent workflows.

### AD-369 — Optional intelligence

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support replaceable optional external intelligence for authorized document interpretation, visual analysis, OCR or translation. Original and deterministic representations SHALL remain available; provider/model identity and material configuration SHALL accompany derived outputs. No inference service SHALL be mandatory.

**Conformance suite:** T-384, T-385, T-386, T-387. See `ARCHITECTURE.md` for criteria.

## Discovery and retrieval

### AD-370 — Discovery providers

**Status:** Accepted (consolidated scope baseline)

SearXNG SHALL be the initial replaceable search provider, bundled as a separately managed internal process in the reference Grenslan container; an existing external instance MAY be configured instead (AD-423). Providers SHALL declare supported capabilities and categories; additional authorized providers MAY be configured. Preserve Grenslan provider and upstream engine attribution when available.

### AD-371 — Search constraints

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL normalize general, news, images, video, academic, software, patents, government, documents, technical, local, enterprise, products and maps discovery categories. Supported constraints include query, language, region, dates, domain inclusion/exclusion, file type, result limits, pagination, explicit safe-search preference and provider selection. Unsupported or partly applied constraints SHALL be reported, not silently ignored. Not every provider must implement every category.

### AD-372 — Ranking and aggregation

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support original provider order and transparent relevance-based aggregation/ranking, with original attribution and rank available. Recency, diversity and explicit consumer filters MAY be applied. No implicit ideological, political, philosophical, economic or religious preference or generalized source-trust/reputation ranking SHALL be used. Relevance SHALL NOT be represented as factual reliability.

### AD-373 — Duplicate handling

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL conservatively normalize URLs, identify exact duplicates and distinguish identical content, redirects and potentially related/syndicated results where detectable. Deduplication SHALL preserve available attribution and SHALL NOT imply independent corroboration. Near-duplicate analysis MAY be optional.

### AD-374 — Retrieval routes

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support direct HTTP and browser retrieval through replaceable contracts. HTTPX, Playwright and standard Chromium are reference choices. Selection SHALL consider content, requested capabilities, available providers, security and limits. Consumers MAY choose an authorized route. Search snippets SHALL remain distinct from captured content.

### AD-375 — Browser provider and identity

**Status:** Accepted (consolidated scope baseline)

Browser engine and controller contracts SHALL be separate. Approved alternative browsers, including Clearcote Open subject to license and security validation, MAY be supported. Configurable browser identity profiles MAY be used consistently within their lifetime; they SHALL NOT override authorization, network rules or external access restrictions. No proprietary browser licensing service SHALL be mandatory.

### AD-376 — Browser observation and interaction

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL expose structured page observations, links and screenshots, and bounded research-oriented interactions where authorized. Element handles SHALL be scoped to session and page state; stale handles SHALL be rejected. Authentication and external state-changing actions require distinct authorization and SHALL NOT be granted by ordinary research access.

### AD-377 — Traversal and completeness

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support bounded traversal and configurable render completion criteria, accounting for visited URLs, depth, count, time and destination limits. Dynamic or incomplete retrieval SHALL report known limitations. Discovered links SHALL NOT expand authorization.

### AD-378 — Retrieval failures and provider limits

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL distinguish access restrictions, network/provider failures, denied requests, unsupported capabilities and extraction failures from successful empty results. Use bounded retries, backoff and authorized fallback; enforce shared provider rate limits and Retry-After where applicable. Fallback SHALL NOT circumvent restrictions or silently replace requested observations.

### AD-379 — Freshness and independent observations

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support explicit cache eligibility, cache-only access where available, fresh independent retrieval and revalidation. Results SHALL identify actual retrieval time and cache access where relevant. Independent execution SHALL bypass incompatible caches and coalescing; one retrieval SHALL NOT be represented as multiple independent observations.

**Conformance suite:** T-388, T-389, T-390, T-391, T-392, T-393, T-394, T-395, T-396, T-397, T-398, T-399. See `ARCHITECTURE.md` for criteria.

## Content processing

### AD-380 — Normalized processing

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL separate retrieval from processing and support versioned, replaceable format processors. Actual content signatures and structure SHALL inform safe format selection; mismatches and unsupported operations SHALL be reported. Original authorized bytes MAY be delivered even when extraction fails.

### AD-381 — Format baseline

**Status:** Accepted (consolidated scope baseline)

v0.1 SHALL support retrieval, inspection and applicable processing of HTML, XHTML, plain text, Markdown, JSON, XML, PDF, PNG, JPEG, WebP, TIFF, GIF, SVG, CSV, TSV, DOCX, XLSX and PPTX. The Provider Contract SHALL define format-specific minimum capabilities. Audio/video processing and specialized engineering formats are optional extensions, not v0.1 requirements.

### AD-382 — HTML and structured content

**Status:** Accepted (consolidated scope baseline)

Trafilatura is the reference general HTML extractor with DOM parsing for specialized extraction. Grenslan SHALL preserve meaningful headings, links, lists, tables, code and available metadata. JSON/XML and delimited text SHALL be safely parsed without executing content.

### AD-383 — Fidelity and limitations

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL preserve substantive source meaning, source-language text and attribution. Extraction SHALL NOT silently apply ideological filtering, trust filtering, summarization or edits. Report partial extraction, omitted representations and material uncertainty; translations SHALL be separately attributed.

### AD-384 — Progressive document access

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support source-addressable sections, passages, pages and regions; inspect, read, find, continuation and bounded output. Document structure, adjacent text and exact passage access SHALL NOT require embeddings or a generative model. Estimated token counts SHALL be identified as estimates.

### AD-385 — PDF and complex documents

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support page-addressable PDF inspection, native text, layout-aware extraction, tables, page/region rendering and OCR for scans. Select methods by document/page/region and requested capability; advanced interpretation MAY use optional specialized providers. Preserve original document and deterministic representations independently of model output.

### AD-386 — Tables and technical material

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL preserve available table structure, headers, units, cell/row relationships, source locators, mathematical notation, code and technical symbols as faithfully as supported. Uncertain layout, OCR or inferred structure SHALL be marked; never invent missing values.

### AD-387 — Image and multimodal processing

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support image search, retrieval, inspection, original delivery, bounded thumbnails/crops, region access and OCR. Derived images SHALL identify transformations and origin. Consumer-aware inline or referenced delivery SHALL preserve media type and applicable limitations; visual interpretations SHALL be separately attributed.

### AD-388 — Office fidelity

**Status:** Accepted (consolidated scope baseline)

DOCX SHALL support paragraphs, headings, sections, tables, images, hyperlinks and metadata; XLSX sheets/ranges/cells, types, formulas, cached values, tables, merges and metadata; PPTX slides, text, object relationships, images, tables and metadata. Notes, charts, hidden structures, comments and rendering SHALL be reported where supported. Cached spreadsheet values SHALL NOT be described as recalculated.

### AD-389 — Safe processing and partial output

**Status:** Accepted (consolidated scope baseline)

Processing SHALL enforce applicable CPU, memory, time, expansion, pixels, recursion, output and temporary-storage bounds. Macros, embedded executables, unsafe XML/SVG features and external references SHALL NOT execute or resolve automatically. Completed eligible representations SHALL be returnable with stage-specific failures and limitations.

**Conformance suite:** T-400, T-401, T-402, T-403, T-404, T-405, T-406, T-407, T-408, T-409, T-410. See `ARCHITECTURE.md` for criteria.

## Result provenance and delivery

### AD-390 — Result contract

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL return versioned structured results with request ID, status, payload and limitations. Discovery results SHALL include URL, available title/snippet, provider and rank. Retrieval results SHALL include requested/final URL or supplied origin, capture time, method, content type, cache status and material conditions. Unknown metadata SHALL remain unknown.

### AD-391 — Source and representation identities

**Status:** Accepted (consolidated scope baseline)

Source, actual capture, original artifact and derived representation SHALL be distinguishable. Opaque resource references SHALL be independent of physical paths and scoped to authorized access and declared availability. Returned content SHALL NOT be silently replaced under the same capture reference.

### AD-392 — Integrity and citations

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL provide SHA-256 for available retained/delivered artifact bytes, with representation-specific hashes where applicable. Citation descriptors SHALL include available source identity, capture timestamp, representation and precise page/section/region/offset locator. Integrity checks SHALL NOT be represented as semantic truth verification. Report missing or corrupt content.

### AD-393 — Verification

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support independent fresh retrieval, deterministic quotation checking against an available representation and artifact integrity verification. Return findings, methods, provenance and limitations to consumers; do not maintain a mandatory claim, custody or corroboration database. Contradictory retrieved material SHALL NOT be suppressed merely because it contradicts another source.

### AD-394 — Artifact delivery and expiry

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support authorized original and derived text, structured and binary payload delivery using inline, reference-based or streamed methods as appropriate. Large payloads SHALL NOT be forced into model context. Expiring references SHALL report their lifetime and explicit expired/unavailable outcomes. Consumers requiring durable evidence SHALL copy it before expiry.

### AD-395 — Supplied and offline content

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL accept authorized supplied files and process available artifacts without external network access where the operation permits. Imported origin SHALL be identified, not represented as live web capture. Arbitrary caller-specified host paths SHALL NOT grant access. Portable evidence bundles and permanent collections are not mandatory.

**Conformance suite:** T-411, T-412, T-413, T-414, T-415, T-416, T-417, T-418. See `ARCHITECTURE.md` for criteria.

## Security and isolation

### AD-396 — Authentication and trusted context

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL authenticate protected interfaces using lightweight application credentials. Application namespace SHALL derive from authentication. Explicitly trusted consumers MAY assert user, agent, instance and session identifiers within their namespace; claims SHALL NOT impersonate other applications. Single-user setups SHALL use the same simplified boundary.

### AD-397 — Request isolation and object access

**Status:** Accepted (consolidated scope baseline)

Every request, result, temporary artifact, browser session and credential SHALL be associated with its authorized context. Identical names or IDs across namespaces SHALL NOT commingle data. Resource IDs and hashes SHALL NOT grant access; validate ownership on every protected read, write, status and cancellation. Do not disclose unrelated resource existence or activity.

### AD-398 — Credential handling

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL protect reusable credentials, support replacement and revocation, and distinguish credential use from disclosure. Credentials SHALL be destination-scoped and SHALL NOT leak through redirects, fallback, ordinary diagnostics or unrelated browser sessions. External vaults MAY be supported; not mandatory.

### AD-399 — Browser isolation

**Status:** Accepted (consolidated scope baseline)

Browser profiles, cookies, tokens and temporary state SHALL be isolated by authorized context. Ephemeral sessions are the default; bounded explicit session continuity MAY be supported. Browser contexts alone SHALL NOT be treated as adequate isolation for mutually untrusted domains. Use appropriate process/OS boundaries and clean state on reuse.

### AD-400 — Network and host protection

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL enforce destination restrictions independently of browser interception, including scheme, resolved address, connection target, redirects, DNS changes, embedded and script-initiated requests. Public retrieval SHALL default to denying unintended private, loopback, link-local, management and host infrastructure access. Authorized internal sources and inference/search endpoints require narrowly scoped operator configuration; browser workers SHALL NOT inherit provider privileges.

### AD-401 — Transport and disclosure

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL enforce configured TLS validation and report certificate failures. Private CAs MAY be configured. External queries, content uploads and provider fallback SHALL respect explicitly authorized destinations and consumer disclosure restrictions. Material query transformations SHALL be attributable. No independent subject-matter or ideology restrictions SHALL be imposed.

### AD-402 — Untrusted data and execution

**Status:** Accepted (consolidated scope baseline)

Retrieved instructions, structured tool-like data and model output SHALL NOT establish execution authority, change configuration or grant access. Original evidence SHALL remain unaltered. Protected actions SHALL be independently authorized. Prompt-injection classification MAY be optional; security SHALL NOT depend on it.

### AD-403 — Worker boundaries

**Status:** Accepted (consolidated scope baseline)

Untrusted browser and document workers SHALL be restricted by filesystem, network, process and resource boundaries; they SHALL NOT receive unrelated secrets, database access or administrative privileges. Reused workers SHALL NOT expose prior context state. Isolation failures SHALL be reported, not silently bypassed.

### AD-404 — Provider administration

**Status:** Accepted (consolidated scope baseline)

Operator authorization SHALL control provider installation, updates, disabling and configuration. Pin and integrity-check applicable executable dependencies and binaries; no unauthorized automatic replacement. Ordinary agents SHALL NOT access administration. Minimal attributable security events and protected bounded diagnostics SHALL be supported.

### AD-405 — Revocation and security outcomes

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL enforce credential and applicable scope revocation on queued and active protected work. Denials, restrictions and incomplete cancellation SHALL be explicit. Revocation SHALL NOT unnecessarily disrupt unrelated authorized requests. Consumer governance and user RBAC remain consumer responsibilities.

**Conformance suite:** T-419, T-420, T-421, T-422, T-423, T-424, T-425, T-426, T-427, T-428, T-429, T-430, T-431, T-432, T-433. See `ARCHITECTURE.md` for criteria.

## Storage and execution

### AD-406 — Minimal internal persistence

**Status:** Accepted (consolidated scope baseline)

Internal PostgreSQL and filesystem storage are the reference choices for persistent configuration, application registrations and operational/cache metadata where needed. Search and retrieval SHALL NOT require a durable record for every request. No permanent research history, vector index, corpus embedding pipeline or evidence archive SHALL be mandatory. Storage details SHALL NOT leak into public contracts.

### AD-407 — Encapsulated database

**Status:** Accepted (consolidated scope baseline)

When included, PostgreSQL SHALL run in the primary Grenslan container with restricted Unix-domain socket access and no TCP listener in the reference configuration. Only authorized internal service components may connect. Persistent configuration and any retained cache data SHALL use protected volumes; temporary data remains distinguishable. SQLite or external database configurations MAY be supported outside the reference deployment.

### AD-408 — Bounded cache

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support configurable bounded temporary resources and caching, including freshness and expiry. Cache reuse SHALL account for authorization, credentials, personalization, representation, retrieval/processor conditions and applicable caching restrictions. Unknown or restricted content defaults to private. Eligible public pooling MAY occur within configured trust domains; cross-organization pooling requires explicit operator authorization. Private queries, histories and results SHALL NOT be exposed through shared caches.

### AD-409 — Cache consistency and cleanup

**Status:** Accepted (consolidated scope baseline)

Cache writes SHALL stage and validate content before publishing references; concurrent updates SHALL NOT corrupt records. Content-addressed storage and compatible deterministic processing reuse MAY be used. Active authorized reads SHALL be protected from eviction; expiry, cleanup, missing files and storage exhaustion SHALL produce explicit outcomes. No forensic erasure guarantee without supporting storage capabilities.

### AD-410 — Concurrent request handling

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support bounded asynchronous execution across concurrent consumers using request-local contexts, async I/O and isolated worker pools. No mandatory external scheduler, broker or durable workflow engine. Global and optional application limits SHALL prevent unbounded admission; resource-intensive work SHALL NOT indefinitely starve lightweight research.

### AD-411 — Execution modes and results

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support synchronous calls and bounded asynchronous references for longer work. Report effective mode, authorized status and partial results; do not silently detach synchronous work. Document disconnection, expiration and restart behavior. Durable job recovery is not required; interruption SHALL NOT be represented as completion.

### AD-412 — Budgets and cancellation

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL enforce configurable request deadlines, concurrency, output, download, traversal and processing limits. Nested and parallel work SHALL share enclosing budgets without multiplying allocations. Support scoped cancellation, bounded retries and graceful shutdown. Preserve available authorized partial results and report irreversible or uncertain actions.

### AD-413 — Optional shared execution

**Status:** Accepted (consolidated scope baseline)

Compatible concurrent request coalescing MAY be implemented. It SHALL preserve independent access, context, cancellation and attribution, and SHALL NOT violate independent verification. One subscriber cancelling SHALL NOT cancel still-authorized shared work. No subscriber ledger is required when coalescing is disabled.

### AD-414 — Maintenance

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL support bounded logging, temporary cleanup, safe schema changes if persistent storage is used, basic configuration backup/restore procedures and explicit corruption reporting. Restart SHALL invalidate unrecoverable temporary references or report interruption; no durable job replay or full evidence-store migration is mandatory.

**Conformance suite:** T-434, T-435, T-436, T-437, T-438, T-439, T-440, T-441, T-442, T-443, T-444, T-445, T-446, T-447. See `ARCHITECTURE.md` for criteria.

## Packaging and conformance

### AD-415 — Reference deployment

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL provide a self-contained primary Docker container with MCP/REST as its research ingress, nonprivileged operation, restricted mounts, no Docker host socket and appropriate process supervision. Bundled SearXNG SHALL run as a separately managed internal process; approved external search or inference providers MAY be connected instead or as applicable. Database and internal worker endpoints SHALL NOT be externally exposed.

### AD-416 — Configuration and capability reporting

**Status:** Accepted (consolidated scope baseline)

Operators SHALL configure credentials, providers, network allowances, worker/resource limits and cache lifetimes. Capability discovery SHALL describe enabled, disabled and unsupported functionality. Optional provider failure SHALL NOT unnecessarily prevent core operations. Numerical defaults and library versions require implementation validation.

### AD-417 — Integration and conformance

**Status:** Accepted (consolidated scope baseline)

Grenslan SHALL remain independent of QOR, Mnemosyne, Zygos and third-party consumer internals. v0.1 SHALL implement the functional, security and isolation requirements of this baseline. Acceptance tests SHALL include concurrent independent clients, malicious-content containment, provider failures and artifact expiry. Tests are not passed until executed and recorded.

**Conformance suite:** T-448, T-449, T-450. See `ARCHITECTURE.md` for criteria.

## Provider architecture and extensibility

### AD-418 — Minimal provider contracts

**Status:** Accepted (Round 8)

Grenslan SHALL implement lightweight, versioned, capability-specific provider interfaces for discovery, retrieval, browser execution, content processing, OCR and optional intelligence. Providers SHALL return normalized results and applicable limitations. Provider implementations SHALL NOT require independently deployed services, a distributed plugin framework or an autonomous agent runtime.

### AD-419 — Reference provider selection

**Status:** Accepted (Round 8)

Grenslan SHALL establish an initial reference provider set supporting SearXNG discovery, direct HTTP retrieval, Playwright-controlled Chromium, structured HTML extraction, document inspection, PDF rendering, OCR and supported image and Office formats. v0.1 SHALL include direct specialized discovery adapters for arXiv, Crossref, PubMed, OpenAlex and GitHub, independently configurable and disableable. Customer operators SHALL be able to add deployment-specific government data API providers through the documented provider interfaces; no fixed government endpoint or jurisdiction is mandatory. Configurable private repository support and optional commercial search integrations SHALL use the same provider boundary; no specific repository or commercial service is required. Clearcote Open and Brave Origin are initial alternative browser integration targets, subject to licensing, compatibility and security validation; Firefox is not an initial target. Individual implementations SHALL remain replaceable. Optional providers SHALL NOT become mandatory dependencies of ordinary research execution.

### AD-420 — Selective content processing and original-artifact fallback

**Status:** Accepted (Round 8)

Grenslan SHALL select content-processing capabilities according to the actual resource format, requested output, available providers and applicable resource limits. Grenslan SHALL support selective page, region or representation processing where supported. Model-assisted processing SHALL NOT be required for ordinary deterministic extraction and inspection. When compatible processing is unavailable, prohibited by applicable licensing, fails, is incomplete or exceeds processing limits, Grenslan SHALL offer delivery of the authorized original artifact where safely acquired and permitted, together with available metadata, provenance and explicit limitations; partial extracted content SHALL be returned when available and authorized. Grenslan SHALL distinguish potential relevance inferred from discovery metadata from verified contents and SHALL NOT claim an uninspected passage exists. The consumer performs any remaining processing. Delivery SHALL respect applicable security, access, disclosure and resource limits.

### AD-421 — Provider execution boundaries

**Status:** Accepted (Round 8)

Grenslan SHALL provide providers with only the authorized execution context and resources necessary for their assigned tasks. Provider selection, fallback and extension mechanisms SHALL preserve applicable authorization, network restrictions, research isolation, deadlines and cancellation. Providers SHALL NOT independently expand their execution authority.

### AD-422 — Provider configuration and distribution

**Status:** Accepted (Round 8)

Grenslan SHALL support operator-controlled provider selection and registration through documented configuration and extension interfaces. Reference dependencies, executable binaries and distributed model weights SHALL be evaluated for applicable licensing, integrity, compatibility and security requirements. Ordinary research consumers SHALL NOT automatically install or activate unapproved executable providers. Optional inference SHALL be configurable by endpoint, adapter, model, capabilities and resource limits; Ollama native and OpenAI-compatible adapters are initial integration targets for Ollama, vLLM, llama.cpp and compatible services. Operators MAY configure multiple endpoints or disable inference entirely. No hosted service, bundled inference runtime or model weights SHALL be required. Government API additions SHALL be operator-authorized and deployment-specific, with applicable endpoint, credential and disclosure restrictions enforced.

**Conformance suite:** T-451, T-452, T-453, T-454, T-455, T-456, T-457, T-458, T-459, T-460, T-461, T-462, T-463, T-464. See `ARCHITECTURE.md` for criteria.


## Deployment, distribution and configuration

### AD-423 — Reference distribution and installation

**Status:** Accepted (Round 9)

Grenslan SHALL provide a versioned, single primary Docker reference deployment bundling SearXNG as a separately managed internal process. Its endpoint SHALL NOT be externally exposed or accessible to untrusted workers. An operator MAY configure an existing authorized external SearXNG instance instead. No separate SearXNG container, Docker Compose deployment, external inference infrastructure, centralized telemetry or remote licensing infrastructure SHALL be mandatory for core functionality. MCP and REST SHALL remain the consumer-facing service interfaces.

### AD-424 — Platform portability

**Status:** Accepted (Round 9)

Grenslan SHALL target Linux x86-64 and ARM64 container deployments. Windows and macOS Docker environments SHALL be supported where compatible with the reference runtime and available providers. Platform-specific provider limitations SHALL be documented and reported. Core research functionality SHALL NOT require GPU acceleration.

### AD-425 — Operator configuration

**Status:** Accepted (Round 9)

Grenslan SHALL support documented, validated, operator-controlled configuration of application credentials, providers, endpoints, SearXNG upstream search engines, network restrictions, processing capabilities, resource limits and temporary storage. Reusable secrets SHALL remain protected. Customer-specific providers SHALL be configurable without modifying public research contracts. A separate configuration-management service or administration dashboard SHALL NOT be mandatory. Outbound SearXNG queries and network behavior SHALL comply with configured provider and disclosure policies.

### AD-426 — Connected and restricted deployment compatibility

**Status:** Accepted (Round 9)

Grenslan SHALL support connected, restricted-network, internal-only and offline processing configurations through the same core architecture. Applicable network restrictions SHALL be enforced independently of retrieved content and untrusted execution components. Unavailable external capabilities SHALL be reported explicitly. Offline operation SHALL NOT require mandatory software downloads or external licensing services for core functionality.

### AD-427 — Controlled release and maintenance

**Status:** Accepted (Round 9)

Grenslan SHALL support operator-controlled installation, upgrades, dependency verification and graceful service shutdown. Reference releases SHALL include applicable licensing notices, dependency information, configuration examples and deployment documentation. Applicable third-party license texts, copyright notices, component inventory and required corresponding-source availability information SHALL be accessible within the container and repository; the README SHALL identify Grenslan’s own license, summarize bundled component licensing and link to detailed notices and applicable source information. Original Grenslan code SHALL remain Apache-2.0 and bundled components retain their own licenses. Links alone SHALL NOT substitute for required license texts, notices or source obligations. Grenslan SHALL provide lightweight health and capability reporting, bounded diagnostics and temporary-resource maintenance without requiring external observability or update-management infrastructure.

**Conformance suite:** T-465, T-466, T-467, T-468, T-469, T-470, T-471, T-472, T-473, T-474, T-475, T-476, T-477, T-478, T-479, T-480. See `ARCHITECTURE.md` for criteria.

## Public tool contracts, integration and foundational conformance

### AD-428 — Public interfaces and secure transport

**Status:** Accepted (Round 10, amended)

Grenslan SHALL expose versioned, typed, provider-independent research contracts through MCP and REST. Python SDK and CLI SHALL operate as clients of authorized public service interfaces. Contracts SHALL remain independent of internal providers, database schemas and consuming application architectures. Grenslan SHALL implement the current stable MCP specification at implementation/release time, pin its exact supported revision and compatible SDK version, document those versions and report unsupported protocol revisions according to the applicable specification. Grenslan SHALL use MCP Streamable HTTP exclusively over HTTPS for network communications; legacy HTTP+SSE transport and automatic compatibility or insecure fallback SHALL NOT be implemented. Protocol-defined streaming within the supported transport remains permissible over HTTPS.

All consumer-facing MCP, REST and artifact delivery network endpoints SHALL require HTTPS, including same-host, Docker-network, private-LAN and remote deployments. Grenslan SHALL NOT expose plaintext client-facing endpoints. TLS 1.2 SHALL be the minimum and TLS 1.3 SHOULD be preferred. Grenslan SHALL support enterprise certificates, approved private CAs and locally generated certificates explicitly trusted by clients. Grenslan-provided clients SHALL validate server certificates, including identity, validity and trust, and SHALL NOT fall back to plaintext or disable verification. Certificate material SHALL be configurable through protected deployment configuration and mounted files, replaceable without rebuilding the container. The single-container reference deployment SHALL serve HTTPS without requiring an external proxy, public CA, certificate-management service or enterprise identity infrastructure. Mutual TLS MAY be supported but SHALL NOT be mandatory. An approved proxy MAY be used provided no plaintext consumer-facing interface or network hop is introduced. This requirement does not prohibit authorized outbound retrieval of HTTP-only sources or private in-process/Unix-socket communications inside the container.

### AD-429 — Practical tool composition and profiles

**Status:** Accepted (Round 10)

Grenslan SHALL support concise atomic research tools, bounded batches and deterministic search-and-retrieve compositions. Grenslan SHALL support configurable tool exposure appropriate to consuming applications and model capabilities. Tool visibility SHALL NOT substitute for authorization enforcement. Grenslan SHALL NOT require autonomous research planning or agent orchestration. Unsupported constraints and capability limitations SHALL be explicit.

### AD-430 — Consumer-aware result and artifact delivery

**Status:** Accepted (Round 10, amended)

Grenslan SHALL support structured research results, bounded text and multimodal representations, authorized binary artifact delivery and applicable continuation mechanisms. Full documents, PDFs and other large artifacts SHALL be returned by default as independently resolvable resource URIs rather than mandatory inline binaries or model-context payloads. Grenslan SHALL provide available relevant passages, source metadata and source-provided abstracts/descriptions or separately attributed derived summaries when available, with applicable page/section/region locators, provenance and limitations, sufficient for consumers to decide whether to inspect, import or disregard the full resource. Unknown metadata and uninspected content SHALL NOT be fabricated. Summary generation SHALL NOT require a mandatory LLM. Original source URL, actual capture, original bytes and derived representations SHALL remain distinguishable. Artifact descriptors SHALL provide available title, author, date, table of contents, media type, byte size, SHA-256, expiry and availability as applicable. Authorized consumers SHALL be able to resolve the URI through supported MCP resource access or HTTPS REST artifact delivery and obtain the retained original bytes when available; possession of a URI SHALL NOT confer authorization. Inline bounded representations MAY be returned as appropriate. Output limits and continuation SHALL preserve attribution, identify omissions and distinguish partial failures from empty successful results.

### AD-431 — Consumer authentication and interoperability

**Status:** Accepted (Round 10)

Grenslan SHALL support authenticated service-to-service integration and authorization compatible with the pinned MCP specification. Trusted consuming applications MAY establish user, agent and instance context within their authenticated namespace. Every protected operation and resource-access request, including URI resolution, SHALL enforce applicable authentication and authorization. External authorization infrastructure MAY be configured where needed by standards-compatible MCP clients; lightweight authorized application credentials remain supported for controlled integrations. Grenslan SHALL NOT require an independent enterprise identity or governance system.

### AD-432 — Final foundational implementation boundary

**Status:** Accepted (Round 10)

Grenslan v0.1 SHALL implement the discovery, retrieval, processing, delivery, security, isolation, concurrency and deployment capabilities established by the active architectural baseline. Grenslan SHALL remain a standalone research tool rather than a cognitive memory system, research archive, vector retrieval platform or agent framework. Historical superseded requirements SHALL NOT become implementation obligations. Optional capabilities SHALL NOT prevent ordinary core research execution when unavailable. Conformance SHALL be demonstrated through executed and recorded tests, not inferred from adoption.

**Conformance suite:** T-481, T-482, T-483, T-484, T-485, T-486, T-487, T-488, T-489, T-490, T-491, T-492, T-493, T-494, T-495, T-496, T-497, T-498, T-499, T-500, T-501, T-502, T-503. See `ARCHITECTURE.md` for criteria.

## Project identity

### AD-433 — Project identity and naming

**Status:** Accepted (project naming review)

The project SHALL be named Grenslan, superseding the working designation Agent Research Engine (ARE). Its canonical technical identifier SHALL be `grenslan`. RDF Industries, Inc. remains the project owner; the intended repository is `RDFIndustries/grenslan`. Project-owned documentation and technical naming SHALL use the adopted identity, with the former designation retained only for historical traceability. Grenslan SHALL remain an independent, standalone service as established in AD-365, AD-366 and AD-432. The naming decision SHALL NOT modify the previously adopted functional, security, integration, licensing or deployment requirements, nor prematurely finalize illustrative wire contracts or deployment identifiers. Trademark and domain registration are not prerequisites for this naming adoption; no clearance or availability is asserted.

**Conformance:** Documentation consistency review only. No additional runtime acceptance criterion; all existing T-384–503 criteria remain unchanged in substance and unexecuted.

Next unused decision ID: AD-434. Next unused test ID: T-504.
