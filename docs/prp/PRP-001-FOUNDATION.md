# Grenslan v0.1: Foundation Implementation PRP

| Attribute | Value |
|---|---|
| PRP | PRP-001-FOUNDATION |
| Project | Grenslan |
| Owner | RDF Industries, Inc. |
| Product target | v0.1, milestone 1 of 6 |
| Architecture | v0.1, Revision 12, Documentation Checkpoint 011 |
| Adopted architecture decisions | AD-365 through AD-433 (69) |
| Adopted acceptance criteria | T-384 through T-503 (120) |
| Tool Contract | Revision 06; wire 1.0; TC-001 through TC-057 |
| Provider Contract | Revision 05; internal version 1.0; PC-001 through PC-066 |
| Status | Adopted by maintainer, 2026-11-26 |
| Scope | Shared contracts, secure ingress, authentication, provider configuration, discovery |
| Date | 2026-11-26 (Pacific) |

## 1. Objective and exit deliverable

Implement the first working increment of Grenslan: a standalone, CPU-capable, self-hosted service exposing authorized discovery through MCP Streamable HTTP and REST over HTTPS. Provide deterministic, attributable search results from the bundled SearXNG process or an approved external instance, specialized discovery adapters and a documented extension boundary. Demonstrate concurrent isolation, explicit constraint/failure reporting, bounded execution and protected configuration.

This milestone creates the foundation for the remaining five increments. It is not a public v0.1 release or a claim that all 32 tools or 120 acceptance criteria are complete.

**Definition of done:** An authorized independent MCP client and a REST client can issue equivalent bounded search requests over validated HTTPS, receive normalized results with actual configured provider/upstream attribution, search constraint disposition, original ranks and explicit limitations, and inspect authorized capabilities and eligible async operations. The service rejects unauthorized and forged context, insecure transport, prohibited destinations, unauthorized provider configuration, invalid inputs and cross-context operations. Required discovery providers exist and are separately configurable. All milestone gate tests run and evidence is recorded; any remaining affected architecture test is explicitly partial or unverified.

## 2. Required reading and authority

Read these active repository files before modifying implementation:

1. `AGENTS.md`.
2. `docs/ARCHITECTURE.md` and `docs/DECISION_REGISTER.md`.
3. `docs/contracts/TOOL_CONTRACT.md` and `docs/contracts/TOOL_SCHEMAS.json`.
4. `docs/contracts/PROVIDER_CONTRACT.md`, `docs/contracts/PROVIDER_INTERFACES.py`, `docs/contracts/PROVIDER_CONFIG_SCHEMA.json`.
5. `docs/prp/PRP-000-MASTER.md` and this PRP.

The current architecture and decision register are authoritative; accepted contracts refine them. This PRP defines the first work package only. No new architecture decision or acceptance ID is adopted here. If actual repository files differ from the approved revisions, stop the affected work, reconcile with the maintainer and preserve unrelated changes. Do not use archived specifications as active requirements.

**Primary architectural authority:** AD-365–373, AD-396–398, AD-400–406, AD-408–414, AD-416, AD-418–419, AD-421–426, AD-428–429 and AD-431. AD-390–394 apply to discovery/capture distinction, identity, result shape and protected resource boundaries as relevant. AD-415, AD-417, AD-424, AD-427, AD-430, AD-432 and AD-433 apply to deployment, integration, nomenclature and overall conformance. Other adopted requirements remain in force.

## 3. Scope boundary

### 3.1 In scope

- Establish a maintainable, typed Python package and reproducible development/dependency workflow.
- Implement the shared canonical schema registry, validation, normalized request/result/issue records, provider interface types and configuration parsing.
- Implement HTTPS-only MCP and REST ingress, current stable MCP-only compatibility, certificate validation in project client/test harnesses and standard-compatible authorization plus lightweight application credential integration.
- Implement authenticated namespace, trusted delegated context and effective tool/operation authorization on every protected invocation.
- Implement provider registration, capability declarations, validated operator configuration, provider health/lifecycle and deterministic eligible routing.
- Integrate SearXNG as a separately managed protected internal process and allow an operator-approved external replacement.
- Implement specialized search adapters for arXiv, Crossref, PubMed, OpenAlex and GitHub; all independently configurable and disableable.
- Implement normalized web/image discovery, category/filter reporting, provider order, deterministic aggregation, conservative deduplication, bounded continuation, applicable cache/freshness and error normalization.
- Implement minimum bounded sync/async search execution, scoped cancellation/results/status, request-wide budgets, shared provider rate limits, timeouts and containment.
- Demonstrate outbound destination and disclosure enforcement for all foundation provider traffic, including internal SearXNG upstream traffic, and protected internal endpoint isolation.
- Provide a foundation development/container smoke path, documented configuration samples, reproducible tests, license/dependency records and milestone handoff.

### 3.2 Explicitly deferred to subsequent increments of the same v0.1

| Later PRP | Work outside milestone 1 |
|---|---|
| PRP-002-RETRIEVAL | Arbitrary authorized resource retrieval, HTTPX RetrievalProvider, browser controllers/engines, direct HTTP/browser route composition, navigation, observations, interactions and traversal, browser-specific independent network/worker isolation |
| PRP-003-EXTRACTION | Full artifact staging and delivery, upload, format-aware inspection, HTML/structured extraction, progressive read/find/link tools, content hashing and locators |
| PRP-004-DOCUMENTS | PDF, Office, image processing, rendering, structured tables, OCR and associated parser/worker isolation |
| PRP-005-ARTIFACTS | Comprehensive artifact/cache lifecycle, citation and verification tools, optional inference and translation/model-assisted OCR |
| PRP-006-INTEGRATION | Complete reference deployment, SDK/CLI, cross-platform and interoperability conformance, release packaging and full acceptance run |

Security is not deferred: the boundaries needed by each implemented feature must be enforced before that feature is enabled. Foundation output must not fabricate completed retrieval, image artifacts, citations or inspected passages. No service exposes future unfinished behavior as operational. Do not introduce an agent framework, cognitive memory, vector index, permanent archive, hosted AI dependency, GUI, distributed broker, mandatory persistent database, external telemetry or automatic executable installation.

## 4. Pre-coding validation and recommended technical choices

The maintainer's acceptance of this PRP permits foundation work only after the relevant preflight record is complete. Resolve foundation-affecting choices through documented technical validation. A developer must not silently pin a version guessed from memory, disable a protection to get a demo running, or change an adopted requirement. If verification is blocked, record the blocker and seek review for the affected work; independent approved work may continue if it does not depend on the blocked choice.

| Choice | Proposed initial direction | Required preflight evidence before dependent implementation |
|---|---|---|
| Python | Python 3.12 initial supported development target; validate compatible current reference stack, x86-64 and ARM64 images | Supported Python/dependency matrix and reproducible lock mechanism; document constrained alternatives |
| Packaging | `pyproject.toml`, src layout, isolated virtual environment, committed reproducible dependency lock; choose one resolver/workflow | Verify selected tooling and lock format, install/test on clean environment; no unnecessary framework |
| HTTP server | FastAPI/ASGI and a TLS-capable ASGI server as reference candidates | Verify direct HTTPS, TLS minimum 1.2, certificate mount/replacement, stream lifetimes and shared REST/MCP authentication; no plaintext port |
| MCP | Official compatible Python SDK | Verify actual current stable MCP revision in primary specification and SDK support; pin exact pair, transport/negotiation/auth behavior, and compatible client tests; do not implement legacy SSE transport |
| Typed contracts | Adopted Draft 2020-12 registry canonical; Pydantic or equivalent typed models, with standards-compliant JSON Schema validation and parity tests | Prove local references, closed objects, format validation, conditional unions, output validation and exact discovery schema projection; no generated schema drift |
| Provider configuration | Safe YAML parser and validated provider configuration schema plus separate validated ingress/auth settings | Duplicate keys and unsafe tags rejected; adapter-specific schema checks; reference resolution and secret-safe failure diagnostics |
| Discovery transport | Bounded async HTTP client (HTTPX candidate) for approved search API destinations; separately managed SearXNG process | Verify actual connection-target/redirect enforcement and TLS checks; no independent browser/worker access; controlled default denial |
| Provider limits | In-process bounded asyncio admission/worker concurrency, shared rate/deadline/budget tracking, ephemeral operation records | Test queue cap, exhaustion, cancellation, rate-limited retries, lightweight bounded work and cleanup; avoid unsupported numeric defaults |
| Storage | In-memory bounded operation/continuation/cache for foundation; configuration and secrets via protected deployment files | Demonstrate no mandatory persistent research record or DB; quantify caps and restart behavior. Revisit persistent DB only if justified by adopted requirements |
| Ranking | Transparent unweighted reciprocal rank fusion (RRF) candidate for multi-provider relevance | Validate deterministic ordering, tie behavior and attribution with fixture; record actual formula/constant. Original provider order default for single provider |
| SearXNG | Pinned approved separately supervised process bundled in primary container; approved external config alternative | Verify supported service interface/output format, platform availability, upstream network policy, process endpoint protection and license/source obligations |
| Specialized adapters | arXiv, Crossref, PubMed, OpenAlex, GitHub direct interfaces | Verify official provider documentation for endpoint, API/version, rate limits, credentials, terms, attribution, pagination and supported filters; fixtures from permitted synthetic or public samples |
| Testing | pytest with async support and controlled local HTTPS fixtures; lint/type check tools selected during bootstrap | Reproducible test commands, versions and fixture setup; no sensitive data or production secrets |
| Container | Linux nonprivileged foundation development image with only configured HTTPS public ingress | Evaluate actual connection-level egress control and process separation for foundation, protected SearXNG internal endpoint, mounted cert/config and no Docker host socket; do not disable security to satisfy tests |

Record verification results in `docs/implementation/FOUNDATION-VALIDATION.md` or a maintainer-approved equivalent. Include primary source URLs and dates for actual selected versions and API assumptions, license findings, evidence of compatibility and the rationale for chosen mechanisms. Pin versions only after verification. Unverified alternatives remain candidates. A technical proof-of-concept for a preflight choice is disposable validation, not a public service implementation or conformance claim.

## 5. Proposed repository layout

Inspect the actual repository in the development environment first; preserve existing conventions and maintainer changes. If it is still documentation-only, use this proposed modular layout. Create only components needed for the foundation, not placeholder packages or speculative frameworks.

```text
grenslan/
├── pyproject.toml
├── dependency lock (selected and documented during preflight)
├── src/
│   └── grenslan/
│       ├── contracts/        # shared public validation and provider types
│       ├── config/           # operator settings and safe loading
│       ├── security/         # auth, context, policy and credential use
│       ├── execution/        # budget, admission, operations and cancellation
│       ├── providers/        # registry, discovery adapters, lifecycle
│       ├── discovery/        # normalize, rank, filters, dedup, continuation
│       ├── service/          # common invocation routing and public results
│       └── transport/        # REST and MCP over HTTPS
├── tests/
│   ├── unit/
│   ├── integration/
│   └── fixtures/
├── config/                   # sanitized operator example only
├── docker/                   # development/reference foundation packaging
├── docs/
│   ├── contracts/
│   ├── prp/
│   └── implementation/
└── AGENTS.md
```

The authoritative schema files remain in `docs/contracts/`. Package or generate runtime copies via a documented deterministic build process, with tests verifying exact semantic identity and local references. Do not maintain two divergent versions. `PROVIDER_INTERFACES.py` is an adopted declaration specification; production runtime code may implement equivalent types with the same fields and invariants.

## 6. Work packages and execution order

### F01. Bootstrap and validation record

- Confirm branch and working tree, inspect existing repository, record baseline source/doc hashes and contract versions; no force operations or external push without authorization.
- Establish package and development lock, formatting/type/test commands, minimum CI-ready workflow and sanitized test configuration.
- Record verified preflight choices and unresolved dependencies. Establish deterministic unit test environment and scope-specific fixture harness.
- Keep real credentials/cert private keys and generated test data out of source control. Test certificates may be generated locally using fixtures; no production keys included.
- Record third-party versions/licensing and initial dependency inventory; no unreviewed dependencies or runtime downloads.

**Deliverables:** reproducible package install, basic test invocation, lock, development instructions, preflight record.

### F02. Canonical contracts and dispatch

- Load and validate all adopted 32 input/output schemas and supporting upload schema; project self-contained per-tool schemas with reachable local definitions.
- Define typed request/result/issue/status, provider context, registry, capability and configuration types, using adopted public schema as the canonical wire source.
- Reject malformed JSON, unknown properties, conflicting selectors, invalid format/type/enum and caller-supplied identity/permissions. Enforce semantic validation and configured max lengths, arrays and bytes.
- Normalize results using adopted envelope, request ID, effective mode, result/operation discriminator and issues. Validate before public return; use typed exceptions translated without exposing secrets.
- Central tool dispatcher is shared by MCP and REST. No tool transport directly invokes an adapter outside the common auth/policy/budget path.
- Register all 32 schema definitions; enable/expose only implemented and authorized capabilities. Do not ship misleading success stubs.

**Deliverables:** schema conformance tests and common authorized invocation boundary.

### F03. Secure ingress and trusted context

- Implement directly served HTTPS (TLS 1.2 minimum, prefer 1.3), certificate/key/approved CA settings via protected mounted files. No plaintext client-facing listener, insecure fallback or disabled certificate validation.
- Implement `POST /mcp`, permitted protocol-defined additional HTTP methods/streaming, initialization/version negotiation, discovery and invocation according to the verified pinned current stable revision; no legacy transport.
- Implement `POST /api/v1/tools/{tool_name}` and exact status/envelope mapping. Future protected resource/upload endpoints remain unavailable until their milestones; no access-bypass placeholder.
- Support operator-issued application credentials and configured standards-compatible MCP authorization. Validate bearer credential scope; no mandatory external identity system for controlled integrations. Use a local test authorization fixture to exercise the configured interoperability path without a mandatory hosted IdP.
- Derive application namespace from authenticated credentials. Validate optional authorized `Grenslan-User-Id`, `Grenslan-Agent-Id`, `Grenslan-Instance-Id` headers per TC-048, reject duplicate/invalid or unauthorized delegation, never trust ordinary tool arguments or claimed alternate namespace.
- Enforce effective permissions/tool profile and every protected object access. Support credential replacement/revocation through approved operator configuration; revoked credentials cannot start protected work, and affected active/queued work must be stopped appropriately without harming unrelated requests.
- Provide redacted bounded security diagnostics, safe authentication failures and no protected existence disclosure. Apply pinned MCP Origin/network security requirements and reject malformed protocol messages.

**Deliverables:** verified HTTPS MCP and REST calls using real local TLS fixtures; no in-process bypass considered a transport pass.

### F04. Configuration and provider registry

- Validate provider configuration with the adopted schema and semantic cross-checks. Validate separate ingress/auth configuration, approved secret references and scope mapping. Reject duplicate YAML keys, unsafe tags, invalid adapter-specific settings, unknown implementations or unapproved executable loading.
- Register approved built-in provider implementations explicitly by ID and family; extension installation is operator-only. Validate interface version, capabilities, method compatibility, dependency manifests and platform. No research tool accepts endpoint or configuration changes.
- Implement startup/health/shutdown with bounded deadlines and state transitions; optional provider failure affects only relevant functions.
- Implement configured provider priority/eligibility, effective capability projection and safe profile discovery. Fail explicit mandatory configuration errors before service admission; do not require every specialized provider credential.
- Implement a controlled fake/fixture SearchProvider through the same registry for tests; production does not return test data or silently default to fake provider.

**Deliverables:** validated config sample, extension documentation, provider capability/health tests.

### F05. Foundation outbound enforcement and SearXNG

- Implement provider-purpose destination and disclosure checks: allowed scheme/host/port, resolved addresses and actual connection target, redirect/DNS changes, TLS trust, approved credential destination. Deny unintended private, loopback, link-local, host-management and metadata destinations; only scoped approved exceptions.
- Validate independent connection-level enforcement rather than trusting URL parsing or preflight DNS alone. Do not send queries to unapproved sources, leak credentials across redirects, or pass unrelated user/agent data to upstream engines.
- Integrate bundled SearXNG as a separately supervised protected internal process in the primary container; use its service interface, not incorporated source code. Ensure upstream traffic obeys operator-authorized engine/destination and disclosure policy; no protected internal endpoint externally reachable.
- Integrate an approved external SearXNG instance using scoped endpoint, TLS/credential and network policy. Do not make it a second mandatory container.
- Preserve configured provider identity and upstream engine attribution where available; fail explicitly on configuration, rate, access, network and provider errors.
- Demonstrate no reliance on optional inference or GPU. Validate the bundled component and applicable AGPL/source availability obligations based on actual pinned distribution; keep notices accessible within container and referenced in README.

**Deliverables:** protected bundled/external integration fixture, egress policy tests, isolated endpoint smoke test, license inventory.

### F06. Specialized discovery and normalized search

- Implement separate arXiv, Crossref, PubMed, OpenAlex and GitHub adapters following verified official API/provider requirements, operator configuration and approved endpoints. Each declares actual supported categories, constraints, continuation, provider limitations and needed credentials.
- Normalize valid search/image records against canonical schemas. Preserve original positions, source URL, provider/upstream attribution, available metadata and image discovery properties. Unknown fields remain omitted. Image discovery does not fetch originals or claim unacquired thumbnails as artifacts.
- Implement category and constraint disposition; supported provider filters are translated, bounded local filtering applied only when reliable, incomplete/unsupported reported. Never silently substitute a category or claim exhaustive filtering over a limited page.
- Implement provider-order default, validated deterministic relevance aggregation, explicit recency mode and conservative URL deduplication. Keep original rank and attribution for merged matches. Do not infer trust, ideological preference or independent corroboration from duplicate results.
- Implement bounded pagination, expiring provider-specific core cursor mapping, authorized scope/parameter binding and disclosure of upstream snapshot limitations. Core cache-only performs no live request; default/revalidation/fresh_independent report actual observation and reuse conditions, not falsely independent captures. Bound cache by bytes/time and context; private by default. No durable research database.
- If requested web_search.retrieve composition is outside this milestone, return explicit unsupported capability with valid discovery as partial where possible; do not claim acquisition. Expose actual supported constraints and limitations via capability discovery.

**Deliverables:** six discovery adapters (SearXNG plus five specialized), normalized cross-provider fixtures, customer extension example and search end-to-end.

### F07. Bounded execution and operation management

- Support public sync default and explicitly requested async search/image search per adopted schema. Async returns initial accepted operation reference; implement authorized operation_status, operation_results, operation_cancel for those operations.
- Bound admission, worker concurrency, per-application/provider limits, result count/output bytes, input and download budgets, retries and deadline. Shared allocations cannot be multiplied by nested work; rate limits apply across consumers and honor applicable Retry-After. Cancellation cooperatively stops eligible work, bounded termination/cleanup where necessary.
- Ensure execution status, result availability and current status-call outcome remain distinct. Preserve valid authorized partial results and normalized errors. Synchronous disconnection cancels eligible work rather than silently detaching. Restart reports interrupted/unavailable references, not success or durable replay.
- Cursors, cache entries and operations are opaque, authorized, bounded, expiring; possession alone grants no access. Scope content and credential cache reuse by context; no cross-user private cache reuse. No mandatory external scheduler or record persisted per search.
- Graceful shutdown stops admission and cleans resources. Report resource exhaustion and unavailable capabilities explicitly. Verify public envelope and issue mappings and no false successful empty result.

**Deliverables:** concurrency, cancellation, deadlines, shared rate and isolation fixtures; bounded operation store.

### F08. Integration, validation and documentation

- Exercise local MCP and REST across actual HTTPS; compare normalized authorized results under deterministic fixtures, not request IDs or protocol-specific metadata.
- Run security, provider contract and transport negative tests following Section 8. Record exact commands and environment, pinned component versions, actual results and blockers.
- Create foundation development/container smoke workflow with protected internal endpoint; demonstrate nonprivileged operation and configured ingress only. Full packaging and cross-platform end-to-end conformance remain PRP-006.
- Update README implementation status, usage examples, configuration and security limitations without claiming unsupported capabilities or v0.1 completion. Include notices/component inventory and actual source references.
- Produce `docs/implementation/FOUNDATION-HANDOFF.md` with changes, acceptance mapping/evidence, unresolved risks, actual enabled tools/providers, deferred work and PRP-002 prerequisites.

## 7. Public tool enablement and behavior

| Tool | Foundation disposition |
|---|---|
| web_search | Enabled where authorized; discovery, constraints, rank, cursor and effective freshness. Requested retrieve composition reports explicit unsupported/partial until retrieval exists. |
| image_search | Enabled for supported image discovery providers; no automatic original download. |
| capabilities_get | Enabled for authorized client; truthful implemented/configured/operational capabilities. |
| operation_status, operation_results, operation_cancel | Enabled for authorized foundation async search operations; scope/expiry enforced. |
| Other 26 tools | Canonical schemas present, not advertised as available; invocation explicitly unsupported/unavailable where safe and authorized. No successful mock responses. |
| MCP resources/read and REST artifact/upload | Protected interfaces declared in contract, substantive behavior deferred; no unprotected or fictitious bytes/references. |

All enabled tools respond according to the adopted Tool Schemas including TC-057. Source/capture/artifact/citation identities remain distinguishable; discovery references identify sources, not actual captured bytes. No full document insertion into model context. Public wire 1.0 remains stable. REST follows TC-050; MCP follows the verified pinned specification with equivalent structured application semantics.

## 8. Test fixtures and milestone gate

Use reproducible controlled fixtures as the default. Synthetic records and locally controlled test-only endpoints must be clearly identified. Explicit allowlists for controlled private fixture servers must not weaken production default-deny policy. Use live provider smoke tests only where approved/configured and justified, with non-sensitive queries; report credentials, network or provider limits as blocked/unverified rather than claiming pass.

Foundation gate checks below are implementation evidence labels, not new architecture acceptance IDs. A check is passed only when executed, with records and applicable negative assertions. Architecture T criteria spanning later milestones remain partial/unverified until their full adopted scope is demonstrated.

| Gate | Fixture and required assertion | Primary T references |
|---|---|---|
| F-G01 | Clean isolated CPU environment installs locked prerequisites, starts foundation search with no GPU/LLM/vector DB/persistent DB requirement; schema inventory equals 32 and no schema drift | T-384 (foundation portion), T-434, T-494 (portion) |
| F-G02 | Actual HTTPS MCP current revision discover/invoke and REST equivalent deterministic fixture; rejects unsupported revision/legacy transport/plaintext; no listening plaintext consumer port | T-385 (portion), T-481–482, T-496, T-499–500 |
| F-G03 | Valid trusted CA succeeds, invalid/untrusted/expired/wrong hostname rejects; test-only private CA; no verification disable or insecure fallback; replace mounted test certificate and controlled restart without image rebuild | T-429, T-501 (private CA portion), T-502 (foundation clients), T-503 (foundation smoke) |
| F-G04 | Missing/invalid/revoked bearer denied; forged app namespace or model arg rejected; unauthorized delegated headers rejected, including duplicate headers; two supported auth paths apply same policy | T-419, T-422, T-491 |
| F-G05 | Concurrent three applications and multiple users/agents with identical names; private searches, cursors, cache, operations/results/status/cancel remain isolated, ID guessing denied without unrelated existence disclosure; revoke one active credential without cancelling other work | T-420–422 (foundation objects), T-437, T-443, T-490 (scope portion), T-492 |
| F-G06 | SearXNG fixture with multiple upstream engines normalizes source/title/snippet/rank/attribution; replace with alternate registered fixture provider without changing public contract; bundled and approved external mode smoke | T-388, T-451, T-423 (credential case), T-449 (portion) |
| F-G07 | Synthetic general/specialized search and image records, provider/local/partial/unsupported filter cases; category unavailable explicit; image metadata, no invented full-resolution retrieval | T-389, T-407 (discovery portion), T-452, T-486 |
| F-G08 | Single provider order exact; deterministic multi-provider aggregate with duplicates, source attribution, stable tie cases and explicit recency; do not equate duplicates to corroboration or add trust/ideological scoring | T-390–391 (URL discovery portion) |
| F-G09 | Fixture adapters for arXiv, Crossref, PubMed, OpenAlex, GitHub normalize distinct results, pagination and failure/unsupported metadata; operator-installed mock government adapter via same interface; authorized live smoke where configured | T-461, T-451–452 |
| F-G10 | Empty fixture result completed; provider outage, timeout, access challenge, rate limit, malformed result, partial multi-provider result all distinct; original successful results preserved | T-397–398, T-493 |
| F-G11 | Shared provider limit and Retry-After under concurrency; bounded retries/deadline; queue saturation explicit; cancel queued/running search; nested budget cannot enlarge allocation | T-398, T-441, T-443–444 (search portion) |
| F-G12 | Default/cache_only/revalidate/fresh_independent fixture count and timestamps; cache-only sends no network traffic; context-bound cursor cannot replay in unrelated context; expired cursor explicit | T-399 (discovery portion), T-437–438 |
| F-G13 | Deny loopback/private/link-local/metadata, alternate address representations, unauthorized redirect and simulated DNS change/rebinding; validate actual connect destination, not only input URL; approved fixture exception scoped | T-426–427 (search portion), T-458 |
| F-G14 | Source credentials and query disclosure scoped; credential not forwarded across unauthorized redirect/fallback, private query not sent to unapproved provider, retrieved prompt-like text cannot grant authority, diagnostic output redacted | T-423, T-430–431, T-458 |
| F-G15 | Provider config unknown/duplicate/unsafe YAML rejected, unauthorized runtime install/config/activation denied, modified executable fixture verification fails; optional failed provider leaves unrelated capability usable | T-433, T-449, T-459 |
| F-G16 | Capability states and configured profile expose only enabled/authorized implemented tools; other tool requests return explicit limitations; bounded batch/search composition cannot be falsely represented as retrieval | T-386 (search portion), T-484–485 (discovery portion), T-493 |
| F-G17 | Scope-limited internal SearXNG endpoint, nonprivileged container, no host socket or external bypass ingress; verify separate supervision and controlled shutdown; untrusted probe cannot reach internal service under validated isolation design | T-448 (foundation portion), T-472 (foundation endpoint portion), T-445 (portion) |
| F-G18 | Sync and async search accepted/complete/partial/failed/cancelled/timed_out states, authorized results; disconnect cancellation, restart expiry/interruption, resource cleanup; no durable replay | T-443–445 (search portion), T-436 (foundation config portion) |
| F-G19 | Inspect pinned dependency and SearXNG distribution manifest/license/source availability, offline install from approved dependencies, disable external providers and report capabilities without startup downloads | T-460, T-449 (portion); deployment/license suite |
| F-G20 | Independent test client using only public authorized inputs and no consumer-framework dependency; verify result envelope and issue mapping, no future tools advertised as available | T-450 (search portion), T-495 |

**Milestone gate:** F-G01–F-G20 must be demonstrated with executed reproducible fixture evidence on the selected foundation environment. Any blocked mandatory assertion prevents claiming milestone completion; independent partial results must be recorded. Full T-count conformance remains governed by adopted acceptance criteria. Public certificate smoke, multi-platform install, browser/parser isolation, complete SDK/CLI, artifact/download and search-and-retrieve end-to-end tests may require later milestones; identify them explicitly as not fully executed rather than weakening tests or marking them complete.

### 8.1 Required test evidence format

For each gate/test record:

- Stable gate ID, mapped AD/T references, test file/name (where actually created).
- Environment, Python/dependency/MCP revision and selected provider build/config (redacted).
- Exact command, timestamp, expected and observed result, PASS/FAIL/BLOCKED/NOT RUN.
- Evidence of actual negative assertion (e.g. no outbound connection occurred, blocked cross-context operation), not merely absence of an exception.
- Coverage: fully demonstrated applicable criterion or milestone portion only; outstanding dependencies.
- Reproduction notes, known limitations and fix/retest outcome.

Maintain all 120 architecture acceptance statuses; do not count a partial or design-only test as an architecture pass.

## 9. Security and implementation constraints that block release

- No plaintext consumer-facing HTTPS alternative, invalid TLS acceptance or legacy MCP compatibility.
- No trust derived from IDs, model arguments, browser/network source content or provider response text.
- No externally exposed SearXNG internal endpoint, unrestricted internal network access, unvalidated redirect, unintended credential disclosure or shared private results.
- No unapproved third-party provider activation/executable installation, source download at startup or silent bypass of integrity/license review.
- No unbounded queue/results, budget multiplication, ignored cancellation or fabricated progress.
- No required hosted inference service, GPU, permanent research database or consumer framework.
- No false evidence, fabricated observations, implicit source-trust/ideology ranking or unimplemented tool advertised as available.

If a dependency, MCP SDK, egress mechanism or SearXNG bundle cannot meet the requirements, document the concrete conflict and propose a compatible alternative for maintainer review; do not lower requirements to make the build run.

## 10. Handoff and next milestone

At completion, deliver:

1. Reviewable implementation changes in the authorized repository workspace (do not push or publish without maintainer authorization).
2. Reproducible dependency lock and installation/test commands.
3. Validated operator configuration and protected TLS/credential setup instructions.
4. Provider dependency/license/source-availability documentation and actual component inventory.
5. Foundation test/evidence matrix with gate outcomes, architecture T status and known blockers.
6. README/configuration capability and limitation updates.
7. Foundation handoff with security decisions, verified versions, runtime constraints, follow-on risks and exact PRP-002 prerequisites.

Do not begin PRP-002 implementation until the foundation gate is demonstrated and the next milestone PRP is reviewed. PRP-002 introduces direct HTTP retrieval and explicit browser execution under the already adopted Provider Contract; it is the next controlled implementation increment, not a public version change.

## 11. Review and approval

The maintainer adopted this PRP on 2026-11-26. The two major contracts are already adopted. Completion of the foundation-specific technical preflight for each affected choice remains a prerequisite to the dependent service coding.

No source repository has been modified by preparing this PRP. No runtime architecture acceptance criteria have been executed or passed. The existing 69 AD decisions and 120 T criteria remain unchanged.
