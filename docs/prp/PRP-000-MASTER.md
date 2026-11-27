# Grenslan v0.1: Master Product Requirements Prompt

| Attribute | Value |
|---|---|
| PRP | PRP-000-MASTER |
| Project | Grenslan |
| Owner | RDF Industries, Inc. |
| Product target | v0.1 |
| Baseline | Architecture Revision 12, Documentation Checkpoint 011 |
| Active decisions | AD-365 through AD-433 (69) |
| Acceptance criteria | T-384 through T-503 (120) |
| Status | Adopted implementation roadmap; subordinate PRP-001 adopted 2026-11-26 |
| Scope | Coordination, sequencing, implementation gates and validation |

## 1. Purpose and authority

Develop Grenslan as an independently deployable, multi-user, self-hosted information discovery, retrieval and content-processing service for AI agents and applications. Deliver attributable results through authorized MCP and REST service interfaces. The Python SDK and CLI are clients of those interfaces.

This master PRP provides a roadmap, not an alternate architecture. Before beginning any work, read:

1. `AGENTS.md` for engineering instructions and repository guardrails.
2. `docs/ARCHITECTURE.md` for the current scope, implementation sequence and acceptance criteria.
3. `docs/DECISION_REGISTER.md` for normative active requirements.
4. The approved Tool and Provider Contracts and their companions under `docs/contracts/`, and the applicable approved milestone PRP under `docs/prp/`.

The active decision register is authoritative for normative requirements. The architecture explains their intended implementation; approved contracts refine it. This PRP coordinates the work. It neither adopts new architecture decisions nor makes provisional examples binding. If the adopted baseline changes, reconcile this plan and affected milestone PRPs before proceeding. Never restore requirements from `docs/archive/` without explicit approval.

No service implementation may begin until the Tool Contract and Provider Contract are finalized and the affected implementation-level specifications and PRP-001 are reviewed. Documentation and contract design work may proceed before that gate. Repository creation and initial documentation are not evidence that the service is implemented.

## 2. Product outcomes and exclusions

At completion, an authorized independent client can discover information, acquire content, inspect or process supported documents and images, evaluate available metadata and provenance, and resolve permitted resource references without mandatory reliance on an agent framework, hosted AI service, GPU, vector database or permanent research corpus.

The consuming application owns research objectives, reasoning, memory, evidence retention, indexing and subsequent decisions. Grenslan does not determine truth on its behalf. Preserve provider attribution and original ordering, allow documented relevance aggregation and explicit filters, and distinguish relevance from factual reliability. Do not introduce ideological preference or generalized source-trust ranking.

The implementation must not:

- Require QOR, Mnemosyne, Zygos or their internals.
- Introduce autonomous research planning, orchestration, permanent research memory or a mandatory embedding pipeline.
- Require a separate SearXNG container, distributed job broker, external observability platform or enterprise identity system for ordinary core execution.
- Introduce legacy MCP transports, plaintext consumer-facing interfaces, or an authorization bypass for SDK, CLI, local deployments or resource URIs.
- Silently expand access, transmit private material to unauthorized providers, install provider executables in response to ordinary consumer requests, or weaken a requirement for implementation convenience.

All six milestones target v0.1. They are implementation increments, not separate releases or grounds for postponing adopted capabilities.

## 3. Pre-implementation gate

Complete the following in order, reconciling cross-contract dependencies as needed:

| Deliverable | Required outcome |
|---|---|
| Master PRP | Maintainer-reviewed milestone and conformance planning baseline |
| `docs/contracts/TOOL_CONTRACT.md` | Reviewed public interface specifications, including tool inventory, exact request/result/error schemas, transport and version negotiation, authorization expectations, limits, async lifetime, resource access and representation rules |
| `docs/contracts/PROVIDER_CONTRACT.md` | Reviewed versioned capability-specific provider interfaces, execution context, normalization, fallback, disclosure, extension boundaries, failures and configuration semantics |
| PRP-001 | Bounded foundation work package grounded in those contracts, concrete fixtures, acceptance criteria and implementation choices |

Contract reviews must resolve illustrative names, fields, operation states, error codes, URI formats, route shapes and capability declarations before treating them as final. Preserve transport and authentication requirements from AD-428 and AD-431. Pin the exact supported current stable MCP revision and compatible SDK at implementation/release time. Do not guess version numbers or claim backward compatibility.

The 32-tool working inventory in Architecture Section 10 is the starting point. Review practical atomic operations, bounded compositions and tool profiles; do not introduce autonomous research planning. The provider contract must support the capability categories in AD-418 through AD-422, not require each provider to implement every capability.

Decisions still requiring technical validation include whether persistent DB storage is needed, actual schema, worker isolation mechanisms, cache defaults, selected parser/browser/inference versions, platform compatibility, license compatibility and measurable performance/resource limits. Do not turn these open choices into unreviewed requirements.

## 4. Milestone roadmap

Each milestone PRP must reference the current authoritative decision IDs and acceptance criteria, state its exact prerequisites, define implementation tasks and deliverables, and specify how to demonstrate the applicable functionality and negative paths. Gate criteria below are planning guidance; authoritative acceptance text remains in the architecture.

### PRP-001-FOUNDATION: contracts, secure ingress and discovery

**Prerequisites:** Approved Tool and Provider Contracts, approved PRP-001, and resolved foundation-affecting technical choices.

**Scope:** Establish the Python project and shared typed contracts; service ingress, TLS and authenticated namespace handling; provider capability declarations, registration and configuration; separately managed SearXNG integration and normalized search. Establish the intended reference discovery adapters (arXiv, Crossref, PubMed, OpenAlex, GitHub) and extension interfaces. Validate availability and operator configuration. Implement minimal execution limits and secure boundaries necessary for this increment.

**Primary decisions:** AD-365–373, AD-396–398, AD-401, AD-404, AD-406, AD-410–412, AD-416, AD-418–419, AD-421–423, AD-425, AD-428–429, AD-431.

**Exit gate:** Authorized clients invoke bounded search with normalized attribution and explicit constraint/capability reporting. Authentication failures, forged context, invalid TLS, provider errors, rate limits and unauthorized configuration operations are exercised. No mandatory LLM, GPU or permanent research record. No plaintext fallback. Deployment-integrated checks not yet possible remain explicitly unverified.

### PRP-002-RETRIEVAL: HTTP, browser and execution boundaries

**Prerequisites:** Foundation milestone gate and relevant retrieval/browser contracts.

**Scope:** Direct HTTP and Playwright-controlled Chromium retrieval; browser session lifecycle, observations, scoped interactions and bounded traversal; independent connection-level network policy; isolated browser execution; request scheduling, deadlines, scoped cancellation, retry rules and distinct partial/failure outcomes. Evaluate approved alternative browser targets under the common contract without bypassing access controls or licensing restrictions.

**Primary decisions:** AD-374–379, AD-390–391, AD-397–405, AD-410–414, AD-418–419, AD-421–422, AD-429, AD-431.

**Exit gate:** Retrieve static and scripted fixtures through authorized paths; enforce scoped browser interaction, DNS/redirect/subrequest restrictions, isolation and shared execution budgets. Report unsupported capabilities and access failures explicitly. No private-endpoint or credential inheritance. Validate alternate browsers where supported before enabling or distributing them.

### PRP-003-EXTRACTION: structured content and provenance

**Prerequisites:** Authorized retrieval and result contracts; reviewed handling of untrusted parser input.

**Scope:** HTML and structured-content extraction, native text/structured formats, original representation preservation, progressive reading, exact find and locators, source and capture attribution, content hashing, authorized artifact delivery interfaces, bounded output and continuation. Provide secure temporary storage and reference semantics needed by this milestone; complete full lifecycle/cache features in PRP-005.

**Primary decisions:** AD-380–384, AD-389–392, AD-394–395, AD-397, AD-402–403, AD-408–412, AD-418–421, AD-430.

**Exit gate:** Authorized consumers receive attributable actual captures and bounded representations, find relevant passages without embeddings, resolve permitted original content, and distinguish failures or omissions from inspected results. Mislabeled content, parser failures and active content cannot bypass constraints. Do not claim uninterpreted content is verified.

### PRP-004-DOCUMENTS: PDF, images, OCR and Office formats

**Prerequisites:** Secure content-processing boundaries, provenance and authorized artifact interfaces.

**Scope:** Format matrix from the active architecture; PDF text extraction, page/region rendering, scanned content/OCR, layout, technical material and tables; image retrieval/inspection/transforms/OCR; supported DOCX, XLSX and PPTX processing with locators. Select and validate compatible processors, including non-mandatory alternatives for complex documents. Preserve original-language content, explicit fidelity/uncertainty and partial outcomes. Where processing is not possible, retain the authorized original-artifact fallback.

**Primary decisions:** AD-369, AD-380–389, AD-390–395, AD-397, AD-402–403, AD-412, AD-419–420, AD-430.

**Exit gate:** Representative native, scanned, complex and hostile fixtures demonstrate supported processing, limits and provenance. Full format coverage and limitations are recorded. Macros, external references, XML entities, oversized inputs and embedded active content cannot trigger unauthorized activity. Large binary returns use authorized reference delivery by default, not model-context insertion.

### PRP-005-ARTIFACTS: lifecycle, cache, verification and optional intelligence

**Prerequisites:** Retrieval, extraction and document-processing milestones; validated minimal persistence choice and applicable resource contracts.

**Scope:** Complete expiring resource references, independent authorized access, integrity checking, bounded private caching and eligible public reuse, freshness and independent observation, quotation/source/citation verification, approved optional inference adapters and disclosure constraints. Ensure expiry, cleanup, scoped revocation and concurrent reads/writes are safe. Keep verification tied to observed material, not generalized truth claims.

**Primary decisions:** AD-369, AD-379, AD-390–395, AD-397–398, AD-401–405, AD-406–414, AD-420–422, AD-430–431.

**Exit gate:** Correct bytes, locators, freshness and expiry are verified. Private cache data cannot leak across contexts. Independently authorized original and deterministic representations remain available without inference. Optional provider failure, corruption, storage exhaustion, interrupted writes and unauthorized references produce explicit bounded outcomes.

### PRP-006-INTEGRATION: reference distribution and full conformance

**Prerequisites:** All earlier milestone gates; selected dependency, browser, model and deployment compatibility validated to the extent required for the distribution.

**Scope:** Complete single-container reference deployment and supervised internal component lifecycle, protected configuration, operator-controlled install/update/rollback, documented certificate management, Linux x86-64/ARM64 validation and Windows/macOS Docker compatibility validation; connected, restricted, internal-only and offline processing profiles. Complete public MCP/REST interoperability, SDK and CLI integration, documentation, licensing and dependency inventory. Validate complete v0.1 behavior with representative independent consumers.

**Primary decisions:** AD-365–369, AD-396–417, AD-418–432, AD-433.

**Exit gate:** Execute the full active conformance suite. Demonstrate authorized, isolated multi-user consumption over HTTPS, including independently integrated clients with no RDF Industries product dependencies. Record actual platform results and provider limitations. Verify no internally exposed service endpoints, no unauthorized telemetry/disclosure or insecure transport, and applicable bundled-license and source obligations. Do not declare conformance from architecture adoption or incomplete validation.

## 5. Acceptance criteria ownership and traceability

This is the proposed primary full-evidence milestone for each current acceptance criterion. All earlier increments implement and test relevant portions as soon as feasible; security checks must not be delayed merely because full end-to-end verification is assigned later. A criterion may have tests in multiple milestones and must be rerun when affected. Exact definitions are in Architecture Sections 14, 16 and 17; this table does not replace them.

| PRP | Primary full-evidence criteria |
|---|---|
| 001 | T-386, T-388–390, T-398, T-419, T-423, T-429, T-434, T-451–452, T-459, T-461, T-470, T-481, T-484, T-486, T-496 |
| 002 | T-392–397, T-424–428, T-431–432, T-441, T-443–444, T-453–454, T-462, T-485, T-493 |
| 003 | T-391, T-401–402, T-404, T-411, T-489 |
| 004 | T-400, T-405–410, T-418, T-442, T-455–456, T-488 |
| 005 | T-387, T-399, T-403, T-412–417, T-421–422, T-430, T-437–440, T-446, T-457–458, T-463–464, T-487, T-490, T-497–498 |
| 006 | T-384–385, T-420, T-433, T-435–436, T-445, T-447–450, T-460, T-465–469, T-471–480, T-482–483, T-491–492, T-494–495, T-499–503 |

For conditional functionality, test applicability and record the specific condition and outcome in accordance with the authoritative decision. Do not substitute an unapproved exemption for an unmet requirement. Unsupported or unavailable capabilities must be reported; that reporting is not proof of the otherwise required capability.

### Evidence record

Each milestone PRP must identify applicable AD/T IDs and concrete test cases. For each tested criterion record:

- Criterion ID, test identifier and fixture.
- Source revision/commit, environment, platform and pinned dependencies relevant to the result.
- Exact executed command or procedure and observed outcome.
- Pass, fail, blocked or not run; conditional applicability with justification where appropriate.
- Outstanding defects, limitations or decisions; regression scope.

Do not mark a checkpoint passed from a plan, a successful lint run, a mock in place of required integration evidence, or a test that was never executed. Unexecuted tests remain unverified. Do not waive a failing criterion without explicit architectural review.

## 6. Cross-cutting implementation and release gates

These apply throughout the project rather than being separate milestones.

| Gate | Required treatment |
|---|---|
| Scope and contract fidelity | Every public behavior maps to approved contracts and active decisions; material changes require review. |
| Security | Deny unauthorized access at every boundary; treat retrieved content and providers as untrusted; verify isolation, TLS, egress, resource bounds and scoped revocation. |
| Dependency selection | Pin selected versions and validate compatibility, integrity and applicable licensing; document why choices were made. |
| Provider independence | Validate normalized contracts, configuration, capability limitations, failure handling and optionality. |
| Data and provenance | Preserve source/capture/representation distinctions, locators, integrity and authorized delivery without mandatory context loading. |
| Performance and resilience | Measure rather than invent defaults; exercise budgets, concurrency, cancellation, backpressure, failures and restart behavior. |
| Packaging and licensing | Original code Apache-2.0; SearXNG separately supervised and AGPL-3.0. Respect third-party license texts, copyright and corresponding-source obligations; include applicable materials in repository and image. |
| Documentation | Document actual supported versions, interfaces, configuration, certificates, limitations, test status and deployment procedures. |

## 7. Milestone PRP template

Use the following structure for each subsequent work package:

1. Identity, version, status and adopted baseline.
2. Objective, scope and explicit exclusions.
3. Architectural context, applicable AD/T IDs and authoritative contract paths.
4. Prerequisites, dependencies, implementation-level decisions and validation concerns.
5. Concrete implementation steps and expected affected components; do not invent paths for code that does not yet exist.
6. Interface and behavior expectations, including error and partial-result handling.
7. Security, isolation, resource limits and applicable negative paths.
8. Test plan, fixtures, traceability and measurable exit gate.
9. Required documentation and handoff evidence.
10. Open questions, risks and maintainer review points.

Before executing a milestone, reconcile it against the current baseline and previous milestone results. Scope changes require a reviewed decision; ordinary implementation fixes that satisfy the adopted requirements do not require inventing new AD entries.

## 8. Repository planning structure

Use the agreed documentation structure. The following contract and milestone files are planned deliverables, not claims that they already exist:

```text
grenslan/
├── AGENTS.md
├── README.md
├── LICENSE
├── .gitignore
└── docs/
    ├── ARCHITECTURE.md
    ├── DECISION_REGISTER.md
    ├── contracts/
    │   ├── TOOL_CONTRACT.md
    │   ├── TOOL_SCHEMAS.json
    │   ├── PROVIDER_CONTRACT.md
    │   ├── PROVIDER_INTERFACES.py
    │   └── PROVIDER_CONFIG_SCHEMA.json
    ├── prp/
    │   ├── PRP-000-MASTER.md
    │   ├── PRP-001-FOUNDATION.md
    │   ├── PRP-002-RETRIEVAL.md
    │   ├── PRP-003-EXTRACTION.md
    │   ├── PRP-004-DOCUMENTS.md
    │   ├── PRP-005-ARTIFACTS.md
    │   └── PRP-006-INTEGRATION.md
    └── archive/
```

Follow repository conventions for source code, test layout and tooling once established. Keep historical local documentation excluded under `docs/archive/`.

## 9. Status and next action

This PRP is a coordination document for the adopted Revision 12 baseline, not a new documentation checkpoint or architectural decision. At drafting, no runtime acceptance tests have been executed and no service implementation is claimed.

| Work item | Status at drafting |
|---|---|
| Foundational architecture | Adopted |
| Project naming (AD-433) | Adopted |
| GitHub repository setup | Created by maintainer |
| README, LICENSE, .gitignore and AGENTS.md | Prepared |
| Master PRP | Adopted |
| Tool Contract | Adopted, TC-001 through TC-057 |
| Provider Contract | Adopted, PC-001 through PC-066 |
| PRP-001 | Adopted by maintainer, 2026-11-26 |
| PRP-002 through PRP-006 | Pending |
| Runtime conformance | 0 of 120 executed |

**Next:** Review PRP-001-FOUNDATION and resolve its foundation-affecting technical choices before service implementation. Preserve all adopted contracts and acceptance criteria.
