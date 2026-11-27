# Grenslan Foundation Technical Preflight

| Attribute | Value |
|---|---|
| Date | 2026-11-26 (Pacific) |
| Scope | PRP-001 F01 preflight: initial documentation-workspace checks and development-workspace rerun |
| Architecture | v0.1, Revision 12, Checkpoint 011 |
| Public contract | 1.0, TC-001–057 |
| Provider contract | 1.0, PC-001–066 |
| PRP-001 | Adopted by maintainer, 2026-11-26 |
| Preflight status | In progress; repository readiness and contract checks complete in development workspace; other rows open |
| Runtime acceptance | 0 of 120 executed |

## 1. What has been verified

The initial preflight was executed in a transient Linux documentation workspace, not the maintainer's VS Code clone or target Docker deployment. No source repository was modified. No service code was generated.

| Item | Observed result | Status |
|---|---|---|
| Python | 3.12.14 | Available for preliminary checks |
| OpenSSL | 3.5.8 (25 Aug 2026) | Available for preliminary checks |
| Python server SSL context | Minimum TLS 1.2 in this environment | Observed default; require explicit production configuration |
| jsonschema | 4.26.0 | Available |
| MCP Python package | 1.29.0 | Does not meet modern-protocol target; do not pin it |
| FastAPI | 0.141.1 | Observed local version only; not approved release pin |
| Uvicorn | 0.52.1 | Observed local version only |
| HTTPX | 0.28.1 | Observed local version only |
| Pydantic | 2.13.4 | Observed local version only |
| PyYAML | 6.0.3 | Observed local version only |
| mcp-types, httpx2, pytest, pytest-asyncio | Not installed | Resolve in target development lock |
| Docker/Podman | Not found | Container and process isolation proof blocked here |
| Git checkout | None for Grenslan in this workspace | Repository bootstrap blocked here |

Versions shown are environment observations, not project requirements or final dependency pins.

## 2. Protocol finding: modern MCP only

Official sources checked on 2026-11-26 identify **2026-07-28** as the current MCP revision. The official Python SDK release page lists **2.3.0** as the latest stable release observed. Candidate for local locked preflight: mcp==2.3.0 and compatible mcp-types as specified by that release; verify actual dependency resolution and release security information before pinning. Recheck the current revision and release at implementation/release.

The current protocol's Streamable HTTP is stateless at protocol level. Each request declares its own protocol version. The legacy initialization handshake, separately opened GET stream, session ID lifecycle and legacy HTTP+SSE transport are not the intended behavior. Discovery is via server/discover; ordinary request-scoped SSE is a permissible response transport within HTTPS.

**Important implementation risk:** the Python SDK's documented server behavior accepts the modern and earlier protocol families by default through a single application. Merely mounting the SDK's Streamable HTTP endpoint or selecting stateless_http does not enforce Grenslan's current-only policy. The SDK's published documentation reports no ordinary server-era allowlist knob. Grenslan must prevent older-version requests from reaching the legacy handler and must not advertise older revisions as supported.

Required F03 preflight spike and acceptance evidence:

1. Install the selected current SDK in a clean project environment. Inspect the exact pinned release API; do not rely on a different version's docs or private SDK internals.
2. Use a bounded, secure ingress wrapper or supported SDK integration mechanism to enforce the single current protocol revision before dispatch. Validate required headers, per-request protocol metadata and header/body match according to the current specification, including method/name where applicable. Deny duplicate/invalid fields. Do not create a legacy endpoint.
3. For a supported modern request, return correct discovery metadata listing only the supported Grenslan revision. Verify actual tool invocation by a pinned modern client, including canonical input/output schema projection.
4. Verify unsupported declared protocol revisions produce the specification's unsupported-version error and HTTP status, including the supported-version list; missing or inconsistent header/body information produces the specified validation failure. Do not pass legacy initialize requests into the generic SDK. Verify legacy GET/DELETE /mcp and old HTTP+SSE routes cannot invoke capabilities, and no protocol session ID is issued.
5. Pin Grenslan-provided clients to the supported revision rather than SDK automatic fallback. Verify Origin/security checks, HTTPS, request-scoped cancellation, and the two approved authorization profiles. Do not require optional MCP Tasks extension: Grenslan operations are explicit application resources.
6. Confirm that any SDK observability defaults do not result in mandatory telemetry or unauthorized outbound content/metadata disclosure. Disable unapproved export and verify actual outbound connections.
7. If no compatible supported integration can meet these requirements, stop the affected MCP implementation, document the conflict and propose a compatible solution. Do not relax current-only or HTTPS requirements.

These are implementation constraints derived from already adopted AD-428, AD-431, TC-001, TC-048 and the foundation PRP. This is not a new architectural decision or a transport test result.

### Primary sources

- MCP versioning and negotiation: https://modelcontextprotocol.io/specification/versioning
- Stable revision 2026-07-28: https://modelcontextprotocol.io/specification/2026-07-28
- Streamable HTTP, metadata, cancellation and backwards-compatibility behavior: https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http
- Official Python SDK releases: https://github.com/modelcontextprotocol/python-sdk/releases (v2.3.0 was the latest stable release displayed)
- Official Python SDK server-era behavior: https://py.sdk.modelcontextprotocol.io/run/legacy-clients/
- Official SDK protocol/version documentation: https://github.com/modelcontextprotocol/python-sdk/blob/main/docs/protocol-versions.md

## 3. Executed reproducible checks

Run after installing a compatible jsonschema in the isolated development environment. These are design/primitive checks only, not architecture conformance tests.

Repository-layout command:

```shell
python docs/implementation/FOUNDATION-PREFLIGHT.py --tls-smoke
```

Actual command in the documentation workspace:

```shell
python grenslan-starter/FOUNDATION-PREFLIGHT.py --contracts grenslan-starter --tls-smoke
```

| Check | Outcome |
|---|---|
| Canonical registry tool count | PASS, 32 |
| Independent projection of input and output schemas with reachable local definitions | PASS, all 64 object-root schemas validated against Draft 2020-12 |
| Eight representative valid and invalid request/result assertions, including forged identity and TC-057 | PASS |
| Provider configuration schema meta-schema validation | PASS |
| Six provider family and two browser component protocol declarations loaded | PASS |
| Standard-library TLS loopback test with generated ephemeral certificate explicitly trusted by client | PASS, negotiated TLS 1.3 |
| Untrusted certificate and wrong server hostname rejected | PASS |

TLS smoke uses an ephemeral loopback socket and temporary certificate, not an ASGI server, real MCP/REST endpoint, deployment certificate or container. It does not alter system trust. It does not establish F-G03 or T-429/501/502/503 compliance. No runtime provider/security or application tests were executed.

Baseline SHA-256 of unchanged contract files checked:

```text
19d95e6b4887a36e4e49a40f8e85d5c0cb9c279e50ce0c17418631daf566b5fc TOOL_CONTRACT.md
b50ca06c75bcdad9e1b2ccfbbcc2c5cd6704c73d29fd767fd40656deca6db1eb TOOL_SCHEMAS.json
f71431422cc88344fa7fef4ded79f5816ba3d61d4f26460fcba6258ab0ea92f9 PROVIDER_CONTRACT.md
cdb0328820d2ab844d7057c702429665628d3157348046f71907548b616a6802 PROVIDER_INTERFACES.py
6729ae1c98c73389f19ff7668f6ca903c92b56e8d3a2b3bd288c4cc7dc7d9505 PROVIDER_CONFIG_SCHEMA.json
```

The companion script is a preflight test, not service implementation.

## 4. Development workspace preflight

### 4.1 Environment and repository

| Item | Observed result (2026-11-26, Pacific) |
|---|---|
| Host | Ubuntu 24.04.5 LTS on WSL2 (kernel 5.15.167.4-microsoft-standard-WSL2), x86_64 |
| Python | 3.12.3 (system `/usr/bin/python3.12`) |
| OpenSSL | 3.0.13 (30 Jan 2024), system and Python `ssl` module |
| Resolver | uv 0.8.8 installed locally; PyPI lists 0.13.10 as current. Lock tooling not yet selected or pinned |
| Docker | Docker 29.8.2 available; container and egress proof not yet executed |
| Repository | Git repository initialized on branch `main`; baseline commit `1e704995327bbb699beb22e538e2961d24946c01`; remotes `origin` (`https://github.com/RDFIndustries/grenslan`, public) and `gitea` (maintainer LAN Gitea 1.25.5, `jrogers/grenslan`, served over plain HTTP) |

Document placement was reconciled before the baseline commit. The adopted contract set, PRP-000 and PRP-001 were moved to the locations named in `AGENTS.md`. Superseded working revisions were moved to the ignored local `docs/archive/` directory and are not active requirements. The contract hashes in Section 3 match the files now in `docs/contracts/` exactly.

Baseline SHA-256 of the remaining authoritative documents at the baseline commit, after recording PRP-001 adoption:

```text
4d4c56390abe0c5368af8a1ecf6abf02c8e14d1e6ddfec11c336c7d9891dbbea docs/ARCHITECTURE.md
33783ebc18db093291f84e7f458136fe99fca7424552b41f738338d0d91f4c79 docs/DECISION_REGISTER.md
903b96bf1e33324f50405a4809dddf27a8a922bd0b3d975756d1023f831589a5 docs/prp/PRP-000-MASTER.md
30eaefa0595dc50a17712a6e9cde2ac8c627a25e3df60b8251d28247fa3741ef docs/prp/PRP-001-FOUNDATION.md
```

### 4.2 Contract and TLS primitive checks rerun

Command, from the repository root, using an isolated throwaway virtual environment with jsonschema 4.26.0:

```shell
uv venv -p 3.12 <scratch>/preflight-venv
uv pip install -p <scratch>/preflight-venv/bin/python jsonschema 'jsonschema[format]'
<scratch>/preflight-venv/bin/python -I docs/implementation/FOUNDATION-PREFLIGHT.py --tls-smoke
```

Executed 2026-11-26T21:59:30-08:00. Exit status 0.

| Check | Outcome |
|---|---|
| 64 projected tool schemas, 8 representative assertions, configuration meta-schema, 8 protocol declarations | PASS |
| Contract file SHA-256 | PASS, identical to Section 3 |
| Loopback TLS with explicitly trusted ephemeral certificate | PASS, negotiated TLSv1.3 |
| Untrusted certificate and wrong hostname rejected | PASS |

The scope limits stated in Section 3 still apply: these are primitive checks, not F-G03 or architecture acceptance evidence.

### 4.3 Candidate package versions observed on PyPI

Queried from `https://pypi.org/pypi/<name>/json` on 2026-11-26. These are observations, not pins.

| Package | Latest observed | Declared license | Requires-Python |
|---|---|---|---|
| mcp | 2.3.0 | MIT | >=3.10 |
| mcp-types | 2.3.0 | MIT | >=3.10 |
| fastapi | 0.165.0 | MIT | >=3.11 |
| uvicorn | 0.54.0 | BSD-3-Clause | >=3.10 |
| hypercorn | 0.18.0 | MIT | >=3.10 |
| httpx | 0.29.0 | BSD-3-Clause | >=3.10 |
| pydantic | 2.14.4 | MIT | >=3.10 |
| pyyaml | 6.0.4 | MIT | >=3.10 |
| jsonschema | 4.26.0 | MIT | >=3.10 |
| pytest | 9.2.0 | MIT | >=3.10 |
| pytest-asyncio | 1.5.0 | Apache-2.0 | >=3.10 |
| ruff | 0.17.6 | MIT | >=3.7 |
| mypy | 2.4.1 | MIT | >=3.10 |

Declared package metadata licenses are not a substitute for the dependency license review required by AGENTS.md Section 8; transitive review remains open.

### 4.4 MCP SDK 2.3.0 inspection

`mcp==2.3.0` was installed into an isolated throwaway environment and its installed source was inspected. It resolved these runtime dependencies: anyio 4.16.0, cryptography 50.0.2, httpx2 2.16.2, httpcore2 2.16.2, jsonschema 4.26.0, mcp-types 2.3.0, opentelemetry-api 1.45.2, pydantic 2.14.4, pyjwt 2.15.1, python-multipart 0.0.34, sse-starlette 3.7.1, starlette 1.10.0, truststore 0.10.5 and uvicorn 0.54.0, plus their support packages.

Findings:

1. `mcp_types.version` declares `MODERN_PROTOCOL_VERSIONS = ("2026-07-28",)` and `HANDSHAKE_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26", "2025-06-18", "2025-11-25")`. The deprecated `SUPPORTED_PROTOCOL_VERSIONS` is the union of both.
2. `StreamableHTTPSessionManager._handle_request` routes by the `MCP-Protocol-Version` header only. A request whose header is present and not a handshake version goes to the modern handler. A request with **no header**, or with a handshake version, is served by the legacy stateful or stateless handshake path. This confirms the Section 2 risk: mounting the session manager unwrapped would accept legacy clients.
3. The modern path rejects `initialize` with error `-32022` (unsupported protocol version) and data listing the supported modern versions. `mcp.shared.inbound.classify_inbound_request` validates the per-request `_meta` envelope, header and body consistency (`MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name`) and the supported version. `find_duplicated_routing_header` detects duplicate routing headers. Both are in a public, non-underscored module.
4. The modern HTTP entry point `handle_modern_request` lives in the private module `mcp.server._streamable_http_modern`. Section 2 forbids relying on private SDK internals.
5. OpenTelemetry is used only through `opentelemetry-api`. No OpenTelemetry SDK or exporter is installed as a dependency, and a source comment in `mcp/server/lowlevel/server.py` states that its spans are no-ops until an exporter is configured. Absence of outbound telemetry connections has not yet been demonstrated at runtime.
6. The SDK depends on `httpx2` and `httpcore2`, which are distinct from the `httpx` discovery-transport candidate. Their provenance, license and the effect of having two HTTP client stacks are not yet reviewed.

Candidate F03 approach, not yet validated: a Grenslan ASGI gate in front of the public session manager that admits only `POST /mcp` with exactly one `MCP-Protocol-Version: 2026-07-28` header. It rejects absent, duplicate, handshake-era and unknown versions with the specified unsupported-version or validation response before the request reaches the SDK, so the legacy handler is unreachable. It also rejects GET and DELETE on `/mcp`, and no session ID is issued. Whether this gate plus the public session manager delivers correct modern discovery and invocation, cancellation and authorization remains the F03 spike in Section 2.

### 4.5 Knowledge-base coverage

The local research knowledge base contains SearXNG, Crossref REST API and arXiv API documentation. It does not contain the MCP specification, the MCP Python SDK, PubMed E-utilities, OpenAlex or the GitHub REST search API. Verification of those sources must use the primary URLs directly.

## 5. Remaining preflight in development workspace

| Work | Next evidence |
|---|---|
| Repository readiness | Complete (Section 4.1). |
| Python and resolver | Establish reproducible venv and lock, verify Python/platform compatibility, actual dependency/license/security inventory. |
| MCP SDK / ingress spike | Source inspection done (Section 4.4). Build and test the ingress gate; verify modern discovery and invocation, no outbound telemetry, then pin compatible SDK/types. |
| TLS and identity | Actual HTTPS ASGI/MCP/REST test with private CA, auth and delegation; no plaintext bypass; certificate replacement. |
| Provider config | Safe parser and cross-field scope/registry checks with sanitized fixtures. |
| Outbound enforcement | Demonstrate actual resolved connection, redirect, DNS and credential policies; negative fixtures. |
| SearXNG | Verify official interface, pin compatible approved build, terms/license/source availability, internal process isolation and upstream policy. |
| Specialized providers | Check official API docs/version, credentials, query/filters/pagination/limits and terms for all five adapters; fixtures and approved smoke queries. |
| Execution and resource defaults | Measure and document effective limits, concurrency, bounded operation/cancellation and no unapproved telemetry. |
| Container availability | Docker/WSL2 or appropriate Linux environment, nonprivileged protected endpoint proof; platform constraints remain explicit. |

Complete applicable rows before the dependent code work. The approved PRP permits documentation, validation and independent work packages within scope; do not mark the preflight complete merely because initial checks pass. Full architecture acceptance status remains 0 of 120 until actual tests are executed and recorded.
