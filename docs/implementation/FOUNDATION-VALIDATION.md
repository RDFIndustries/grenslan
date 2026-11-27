# Grenslan Foundation Technical Preflight

| Attribute | Value |
|---|---|
| Date | 2026-11-26 (Pacific) |
| Scope | PRP-001 F01 preflight: initial documentation-workspace checks and development-workspace rerun |
| Architecture | v0.1, Revision 12, Checkpoint 011 |
| Public contract | 1.0, TC-001–057 |
| Provider contract | 1.0, PC-001–066 |
| PRP-001 | Adopted by maintainer, 2026-11-26 |
| Preflight status | In progress. Complete: repository, contracts, resolver and lock, MCP ingress gate, in-process egress mechanism, provider interfaces, package bootstrap. Open: SearXNG build, server and egress design; container; config parser; MCP authorization profile and cancellation; security advisories |
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
5. OpenTelemetry is used only through `opentelemetry-api`. No OpenTelemetry SDK or exporter is installed as a dependency, and a source comment in `mcp/server/lowlevel/server.py` states that its spans are no-ops until an exporter is configured. The SDK's OpenTelemetry page (https://py.sdk.modelcontextprotocol.io/run/opentelemetry/, read 2026-11-26) states the same: with no OpenTelemetry SDK and no exporter installed, span creation is a no-op. A limited runtime observation is in Section 4.5.
6. The SDK depends on `httpx2` and `httpcore2` 2.16.2 (BSD-3-Clause; PyPI metadata names Tom Christie as author and https://github.com/pydantic/httpx2 as source). They are a separately published fork of `httpx`/`httpcore`, not the `httpx` 0.29.0 package. See Section 4.7.
7. The SDK's "Serving legacy clients" page (https://py.sdk.modelcontextprotocol.io/run/legacy-clients/, read 2026-11-26) states that both protocol eras are always served and that there is no option, allowlist or setting on `streamable_http_app()`, `run()` or the session manager to reject or disable an era. Current-only enforcement therefore has to be implemented in front of the SDK.
8. The SDK client's default `mode="auto"` performs discovery and falls back to the `initialize` handshake. Passing `mode="2026-07-28"` adopts that revision directly with no fallback. Grenslan-provided clients must use the explicit revision.
9. The high-level `MCPServer` derives tool schemas from Python type annotations. The low-level `mcp.server.Server` publishes the `Tool.input_schema` and `Tool.output_schema` given to it unchanged and returns `CallToolResult.structured_content` as built, but does not validate arguments against the advertised schema (https://py.sdk.modelcontextprotocol.io/advanced/low-level-server/, read 2026-11-26). TC-047 requires publishing the canonical projected schemas, so the low-level server with Grenslan-side validation is the fitting integration.

Candidate approach (validated by the spike in Section 4.5): a Grenslan ASGI gate in front of the public session manager that admits only `POST /mcp` with exactly one `MCP-Protocol-Version: 2026-07-28` header. It rejects absent, duplicate, handshake-era and unknown versions with the specified unsupported-version or validation response before the request reaches the SDK, so the legacy handler is unreachable. It also rejects GET and DELETE on `/mcp`, and no session ID is issued. Request-scoped cancellation and the standards-compatible MCP authorization profile remain to be validated in F03.

### 4.5 MCP ingress spike

A disposable spike is kept for reproduction in `docs/implementation/preflight/mcp-ingress/`. `spike_server.py` builds a low-level `mcp.server.Server` that publishes the canonical `web_search` input and output schemas projected from `docs/contracts/TOOL_SCHEMAS.json`. It mounts the SDK's public `streamable_http_app(stateless_http=True, transport_security=...)` behind a `ModernOnlyGate` ASGI wrapper, served by uvicorn 0.54.0 with direct TLS (`ssl_context_factory` setting `minimum_version = TLSv1_2`). The gate:

- answers anything other than `POST /mcp` with 405 and `Allow: POST`;
- rejects a present `Origin` not on the allowlist with 403;
- requires exactly one valid `Authorization: Bearer` value (a fixed test-only token in the spike) and answers otherwise with 401;
- requires exactly one `MCP-Protocol-Version` header: absent or duplicated gives 400 with JSON-RPC `-32020` (HeaderMismatch), and any value other than `2026-07-28` gives 400 with `-32022` and `{"supported": ["2026-07-28"], "requested": ...}`;
- strips `Mcp-Session-Id` and `Last-Event-ID` before delegating, so the SDK never sees them.

`spike_check.py` drives it with the SDK client pinned to `mode="2026-07-28"` over an `httpx2.AsyncClient` that trusts only a throwaway private test CA, plus raw HTTP and socket probes. `run.sh` creates the test CA and server certificate in a temporary directory, runs both scripts and deletes everything on exit.

Command, from the repository root, with `mcp==2.3.0` installed in an isolated environment:

```shell
docs/implementation/preflight/mcp-ingress/run.sh <venv>/bin/python 18444
```

Executed 2026-11-26T22:38:59-08:00 on the host in Section 4.1. Exit status 0, 27 of 27 checks passed:

| Check | Observed |
|---|---|
| Pinned modern client `tools/list` | `["web_search"]` |
| Discovered input and output schemas equal the canonical projection | Equal |
| `tools/call` structuredContent validates against the canonical output schema (Draft 2020-12 with format checking) | Valid |
| Forged `application_id` argument | Tool error, not executed |
| Client protocol version | `2026-07-28` |
| `server/discover` `supportedVersions` | `["2026-07-28"]` only |
| `Mcp-Session-Id` on modern responses | Never present |
| Missing `MCP-Protocol-Version` | 400, `-32020` |
| Handshake-era `initialize` without the header | 400, `-32020`, no session |
| Declared `2025-11-25`, `2025-06-18`, `2025-03-26`, `2024-11-05`, `2099-01-01` | Each 400, `-32022`, supported list `["2026-07-28"]` |
| Duplicate `MCP-Protocol-Version` | 400, `-32020` |
| `GET /mcp`, `DELETE /mcp` | 405 |
| Disallowed `Origin` | 403 |
| Invalid bearer | 401 |
| `Mcp-Name` not matching body tool name | 400, `-32020` (SDK validation after the gate) |
| Forged `Mcp-Session-Id` | Ignored, not echoed |
| SDK client in `mode="legacy"` | Connection fails |
| Untrusted CA; wrong hostname (`127.0.0.1` against a `localhost` certificate) | Both rejected |
| TLS 1.1-only client | Handshake refused |
| Plaintext HTTP to the TLS port | No HTTP response |
| Negotiated version, default client | TLSv1.3 |

Telemetry observation: during a further run, the server process's sockets were sampled eight times at 250 ms intervals. Only loopback connections were observed; no non-loopback peer was seen. The environment had only `opentelemetry-api` installed and no `OTEL_*` variables. This is a limited observation, not an egress proof; connection-level outbound evidence belongs with the container egress work.

Scope: the spike validates the protocol gate, schema projection and direct TLS on loopback with a test credential. It is not the Grenslan ingress implementation and does not establish F-G02, F-G03 or F-G04. Not covered: request-scoped cancellation on stream close, the standards-compatible MCP authorization profile (the low-level `streamable_http_app` accepts `token_verifier` and `auth` settings, not yet exercised), delegated identity headers, certificate replacement, and the REST route.

### 4.6 Resolver and lock

uv 0.13.10 was installed into an isolated environment (the host's global uv 0.8.8 was not changed) and exercised on a throwaway project with `requires-python = ">=3.12,<3.13"`, runtime dependencies `mcp==2.3.0`, `jsonschema==4.26.0`, `pyyaml==6.0.4`, a `dev` dependency group (`pytest==9.2.0`, `pytest-asyncio==1.5.0`, `ruff==0.17.6`, `mypy==2.4.1`) and the `uv_build>=0.13.10,<0.14` build backend.

| Step | Result |
|---|---|
| `uv lock` | `uv.lock` format `version = 1`, `revision = 5`, 262 SHA-256 artifact hashes |
| `uv sync --locked` | Installed; package and dependencies import |
| Delete `.venv`, then `uv sync --frozen --offline` | Reinstalled from the local cache with no network access |
| `uv export --frozen --format requirements-txt` | 124 requirement lines, for tooling that needs a requirements file |

uv and uv_build are dual-licensed MIT OR Apache-2.0 per PyPI metadata.

### 4.7 HTTP client stack

The MCP SDK brings `httpx2`/`httpcore2` 2.16.2. Adding `httpx` 0.29.0 for discovery would put two parallel HTTP client stacks in the runtime. `httpx2` is the leading candidate for discovery transport because it is already a required dependency. The deciding test is the outbound-enforcement spike: the transport must allow Grenslan to control and verify the actual connection target (resolved-address pinning, redirect and DNS-change handling, TLS verification and credential scoping). Until that test passes, neither stack is selected for discovery traffic.

### 4.8 Outbound enforcement spike

A disposable spike is kept in `docs/implementation/preflight/egress/`. `egress_spike.py` implements an `httpcore2.AsyncNetworkBackend` (`PolicyBackend`) that receives every outbound TCP connection the pool makes. For each one it:

1. resolves the hostname once through a substitutable resolver;
2. rejects the name if **any** resolved address is prohibited, so a mixed public/private answer cannot be used to reach a private address;
3. connects to the checked IP literal through the public `httpcore2.AnyIOBackend`, so no second resolution happens between check and connect;
4. reads the connected socket's peer address and closes the connection if it differs from the checked target.

The address policy denies multicast, every address for which Python's `ipaddress` `is_global` is false, and the cloud metadata addresses `169.254.169.254` and `fd00:ec2::254`. For IPv6 it also extracts IPv4 addresses embedded through IPv4-mapped, NAT64 (`64:ff9b::/96`), 6to4 and Teredo forms and applies the same policy to them. This is required: Python 3.12 classifies `64:ff9b::7f00:1`, which embeds `127.0.0.1`, as global. Approved non-global destinations are explicit `(address, port)` scoped exceptions. Redirects are not followed by the pool. A Grenslan-side loop re-applies scheme and destination checks on every hop and sends a credential only when the request origin equals the credential's origin.

Command, from the repository root:

```shell
docs/implementation/preflight/egress/run.sh <venv>/bin/python
```

Executed 2026-11-26T22:42:51-08:00. Exit status 0, 20 of 20 checks passed:

| Check | Observed |
|---|---|
| 21 hostile address classes (RFC 1918, CGNAT, loopback, link-local, metadata, unspecified, broadcast, multicast, IPv6 loopback/unspecified/link-local/ULA, IPv4-mapped loopback and metadata, NAT64-embedded loopback and metadata, 6to4- and Teredo-embedded addresses, AWS IPv6 metadata, benchmarking range) | All denied |
| Public example address | Permitted by policy (no connection made) |
| `127.1`, `2130706433`, `0x7f000001`, `0177.0.0.1`, `localhost` | Each denied on its resolved address `127.0.0.1` |
| Scoped loopback fixture exception | Reachable on the approved port only; another port on the same address denied |
| Resolver answering one public and one loopback address | Name rejected; no connection attempted |
| Resolver whose answer changes after the first lookup | One resolution; connection pinned to the checked address |
| Redirect from an allowed fixture to `169.254.169.254` | Denied before connecting |
| Cross-origin redirect from the HTTP fixture to the HTTPS fixture | Followed under policy; bearer credential sent on the first hop only, absent on the second (server-side observation) |
| Pinned connection with a certificate valid for the requested hostname | Accepted |
| Pinned connection where the certificate does not match the requested hostname | Rejected, `CERTIFICATE_VERIFY_FAILED: Hostname mismatch` |
| Default trust store against the private test CA | Rejected |
| `file://` URL | Denied before any connection |

Findings:

- `httpcore2` alone provides the needed control point through its public `network_backend` parameter. `httpx2.AsyncHTTPTransport` does not expose `network_backend`, so the discovery client should use `httpcore2` directly, or a Grenslan transport built on it, rather than `httpx2` or `httpx`. This resolves Section 4.7 in favour of not adding `httpx`.
- `httpcore2` does not read proxy environment variables, so an environment `HTTP_PROXY` cannot silently route traffic around the policy.
- **Open design gap:** this enforcement runs inside the Grenslan process. It cannot govern outbound traffic that SearXNG, a separately supervised process, makes to its upstream engines, which PRP-001 F05 and AD requirements on outbound destination enforcement require. Candidate designs, which need validation and maintainer review: (a) configure SearXNG's outgoing requests to use a Grenslan-operated local egress proxy that applies the same policy, combined with an operating-system or container-network rule that prevents the SearXNG process from connecting anywhere else; (b) a container network policy alone. SearXNG documents `outgoing.proxies` (https://docs.searxng.org/admin/settings/settings_outgoing.html, read 2026-11-26), with `all://` routing to HTTP, HTTPS, SOCKS4, SOCKS5 or `socks5h` proxies; with `socks5h` the proxy performs name resolution, so a Grenslan `socks5h` egress proxy could apply the same `PolicyBackend` checks. The same page shows SearXNG's outgoing client is based on `curl_cffi`. The maintainer directed on 2026-11-26 that SearXNG's actual outbound requests be examined first, to determine whether and how they are a problem, before an egress design is chosen. Proxy settings are cooperative, so option (a) would still need an enforced restriction on the SearXNG process's direct egress; a non-privileged way to apply one inside the primary container has not been verified.

Scope: loopback fixtures and substitute resolvers only; no external network traffic, browser or worker traffic. Not F-G13 or F-G14 evidence.

### 4.9 Discovery provider interfaces

Primary-source verification of SearXNG and the five specialized providers, performed 2026-11-26, is recorded in `docs/implementation/preflight/PROVIDER-APIS.md`, with each fact tagged as documented, read from published source, observed in one anonymous live call, or inferred, and with source URLs. No credential, email address or other identifying value was sent to any provider. Summary of facts that shape adapter design:

| Provider | Endpoint and version | Paging limits | Rate limits and credentials | Notice or licence obligations |
|---|---|---|---|---|
| SearXNG | `/search?format=json`; images tagged `YYYY.MM.DD-<commit>`, no git tags or releases | `pageno` | JSON format disabled by default (403 until enabled in `search.formats`); limiter off by default and needs Valkey if enabled | AGPL-3.0; corresponding source at the image's commit |
| arXiv | `https://export.arxiv.org/api/query`, unversioned | 2000 per call, 30000 total | 1 request per 3 s, single connection, across all operator machines; no key | Metadata CC0; e-prints may not be stored and served without permission; acknowledgement statement requested |
| Crossref | `https://api.crossref.org/works`, live spec 4.11.3 | `rows` ≤ 1000, `offset` ≤ 10000, cursors expire after 5 min idle | Public lists 1/s, concurrency 1; polite (`mailto`) 3/s, concurrency 3 | Metadata largely uncopyrightable; abstracts may be copyrighted |
| PubMed (E-utilities) | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` | ESearch returns only the first 10000 PubMed records per query | 3/s without key, 10/s with `api_key`; `tool` and `email` must be registered with NCBI | NCBI disclaimer must be evident to users; abstracts may be copyrighted |
| OpenAlex | `https://api.openalex.org/works`, unversioned path with tracked deprecations | `per_page` ≤ 100; page × per_page ≤ 10000; cursor beyond first page needs a key | Daily USD budget: $0.10 keyless, $1 with free key; search costs $0.001; 10/s keyless, 30/s with key; `Retry-After` on 429; polite pool and `mailto` withdrawn in 2026 | CC0 |
| GitHub | `https://api.github.com/search/*`, `X-GitHub-Api-Version: 2026-03-10` (requests without it default to `2022-11-28`) | 1000 results per search, `per_page` ≤ 100 | `User-Agent` required; search 30/min authenticated, 10/min unauthenticated; code search requires a token; `retry-after` / `x-ratelimit-reset` on secondary limits | Repository content licensed per repository; API terms not yet read |

Items needing maintainer review before the dependent adapter work:

1. SearXNG application server for a plain supervised process: Granian is described as the future replacement for uWSGI but is "only officially supported in the Installation container"; uWSGI remains the documented non-container path.
2. OpenAlex `relevance_score` includes a capped citation-count boost, and `rerank=true` applies a model. Approved by the maintainer on 2026-11-26, the handling under AGENTS.md Section 2 ranking rules is to preserve and label the provider's own order, never enable `rerank`, and apply no Grenslan-side popularity weighting. SearXNG engine `weight` values are likewise left at their default of 1.
3. Operator-level provider identities and keys (Crossref `mailto`, NCBI `tool`/`email`/`api_key`, OpenAlex and GitHub keys) are optional configuration and never derived from consumer identity. OpenAlex without a key cannot follow cursors, and GitHub code search is unavailable without a token; both must be reported as limitations, not empty results.
4. Whether arXiv e-prints may be cached or delivered to consumers affects later retrieval and artifact milestones; it is a licensing question outside PRP-001 discovery scope.

Unverified items are listed at the end of `PROVIDER-APIS.md` and remain open.

### 4.10 Selected and proposed foundation choices

| Choice | Status | Basis |
|---|---|---|
| Python 3.12 (`>=3.12,<3.13`) | Selected | Host Python 3.12.3; all candidates declare `>=3.10` or lower except FastAPI `>=3.11`; uv lock and spike executed on 3.12 |
| uv 0.13.10, `uv.lock`, `uv_build` backend, `pyproject.toml` with src layout | Selected | Section 4.6 |
| MCP protocol revision 2026-07-28 | Selected | Current stable revision per primary specification (Section 2); TC-001 review reference |
| `mcp==2.3.0`, `mcp-types==2.3.0` | Selected for the foundation lock | Latest release on PyPI 2026-11-26; Sections 4.4–4.5. Release security advisories not yet reviewed |
| Low-level `mcp.server.Server` behind a Grenslan modern-only ingress gate | Selected | Sections 4.4–4.5 |
| uvicorn 0.54.0, direct TLS, minimum TLS 1.2 | Selected | Section 4.5; already a required SDK dependency |
| Starlette (required by the SDK) for the REST route instead of adding FastAPI | Selected; approved by maintainer 2026-11-26 | PRP-001 names FastAPI/ASGI as reference candidates. The foundation REST surface is one `POST /api/v1/tools/{tool_name}` route validated against the canonical registry with jsonschema; FastAPI's model-driven validation and OpenAPI generation would duplicate that and add a dependency. AGENTS.md Section 4 discourages frameworks added for anticipated features |
| jsonschema 4.26.0 with the `format-nongpl` extra as the wire validator | Selected | Sections 3 and 4.11; SDK already depends on jsonschema |
| Discovery HTTP client: `httpcore2` (already required by the SDK) with a Grenslan policy network backend; no `httpx` | Selected, pending the SearXNG egress design | Section 4.8 |

### 4.11 Package bootstrap

The repository now has `pyproject.toml` (src layout, `uv_build` backend, exact direct pins, `[tool.uv] required-version = ">=0.13.10,<0.14"`), `uv.lock`, the `grenslan` package containing only its version, `tests/unit/test_contract_registry.py` (since moved to `tests/unit/contracts/test_adopted_contract_files.py`), `scripts/check.sh`, `docs/implementation/DEVELOPMENT.md` and `docs/implementation/DEPENDENCIES.md`.

Direct runtime pins: `mcp==2.3.0`, `mcp-types==2.3.0`, `starlette==1.10.0`, `uvicorn==0.54.0`, `httpcore2==2.16.2`, `anyio==4.16.0`, `jsonschema[format-nongpl]==4.26.0`. Dev pins: `pytest==9.2.0`, `pytest-asyncio==1.5.0`, `ruff==0.17.6`, `mypy==2.4.1`, `types-jsonschema==4.26.0.20261006`. PyYAML is deliberately not yet a dependency; the configuration parser choice is still open.

Licence finding: `jsonschema[format]` depends on `rfc3987`, declared GPL-3.0-or-later. The `format-nongpl` extra replaces it with MIT and Apache-2.0 validators and is used instead. The preflight script in Section 3 was run with the `format` extra in a throwaway environment only. The installed set contains no GPL-family licence; `fqdn` (runtime) and `pathspec` (dev) are MPL-2.0. Details are in `DEPENDENCIES.md`.

Clean-environment reproduction, executed 2026-11-26T22:46:34-08:00: the files git would commit were copied into an empty directory and installed with uv 0.13.10 using an **empty** uv cache.

| Step | Command | Result |
|---|---|---|
| Install | `uv sync --locked` | PASS |
| Lint | `uv run --locked ruff check` | PASS |
| Format | `uv run --locked ruff format --check` | PASS |
| Type check | `uv run --locked mypy` | PASS, no issues in 2 source files |
| Tests | `uv run --locked pytest` | PASS, 69 passed |
| Offline reinstall | delete `.venv`; `uv sync --frozen --offline`; `uv run --frozen --offline pytest` | PASS, 69 passed |

The 69 tests check the adopted contract files: Draft 2020-12 dialect, 32 tools, 64 projected object schemas valid against the meta-schema, rejection of a caller-supplied `application_id`, `uri` format checking available without the GPL extra, and the provider configuration schema. They are not service tests. The maintainer chose not to use hosted CI workflows; `scripts/check.sh` runs the same checks locally and can be invoked by any CI system. The host's global uv was later upgraded to 0.13.10 by the maintainer.

### 4.12 Knowledge-base coverage

The local research knowledge base contains SearXNG, Crossref REST API and arXiv API documentation. It does not contain the MCP specification, the MCP Python SDK, PubMed E-utilities, OpenAlex or the GitHub REST search API. Adding those sources was attempted on 2026-11-26 and did not complete because the knowledge-base service could not reach its local embedding provider. Verification of those sources used the primary URLs directly.

## 5. Remaining preflight in development workspace

| Work | Next evidence |
|---|---|
| Repository readiness | Complete (Section 4.1). |
| Python and resolver | Selected and bootstrapped (Sections 4.6, 4.10, 4.11). ARM64 compatibility and security advisory review remain open. |
| MCP SDK / ingress spike | Gate validated (Section 4.5); SDK and types selected (Section 4.8). Request cancellation, MCP authorization profile and release security advisories remain for F03. |
| TLS and identity | Direct TLS with private test CA validated for MCP (Section 4.5). REST, delegation headers and certificate replacement remain for F03. |
| Provider config | Safe parser and cross-field scope/registry checks with sanitized fixtures. |
| Outbound enforcement | In-process mechanism validated (Section 4.8). SearXNG upstream egress control is an open design gap needing validation and maintainer review. |
| SearXNG | Interface, distribution, licence and outgoing-proxy support verified (Sections 4.8–4.9). Select and pin a build, decide the application server, and validate process isolation and upstream egress control. |
| Specialized providers | Official interfaces verified (Section 4.9); unverified items listed in `PROVIDER-APIS.md`. Fixtures and approved smoke queries remain for F06. |
| Execution and resource defaults | Measure and document effective limits, concurrency, bounded operation/cancellation and no unapproved telemetry. |
| Container availability | Docker/WSL2 or appropriate Linux environment, nonprivileged protected endpoint proof; platform constraints remain explicit. |

Complete applicable rows before the dependent code work. The approved PRP permits documentation, validation and independent work packages within scope; do not mark the preflight complete merely because initial checks pass. Full architecture acceptance status remains 0 of 120 until actual tests are executed and recorded.

## 6. Implementation progress

### 6.1 F02: canonical contracts and common dispatch (in progress)

Implemented in `src/grenslan/contracts/` and `src/grenslan/service/`:

| Component | Behaviour | Contract basis |
|---|---|---|
| `contracts/registry.py` | Loads the packaged registry, a byte-identical copy of `docs/contracts/TOOL_SCHEMAS.json` kept in sync by `scripts/sync-contracts.sh` and checked by a test. Projects each of the 32 tools' input and output schemas, plus `UploadResult`, into self-contained Draft 2020-12 schemas. Validates with format checking. Error reports give the JSON pointer and keyword but never the supplied value. | TC-047, TC-049 |
| `contracts/json_input.py` | Strict body decoding. Rejects duplicate keys, `NaN`/`Infinity`, non-object bodies, invalid UTF-8, a byte-order mark, trailing data, oversized bodies (checked before parsing) and nesting deeper than 64 (checked before the recursive parser runs). | TC-047, TC-049 |
| `contracts/envelope.py` | Typed `IssueCode`, `Status` and `Issue`. The `completed`/`partial`/`failed`/`accepted` builders enforce the envelope invariants. Tests check the enums against the schema vocabulary. | TC-005, TC-007, TC-008, TC-050 |
| `service/profiles.py` | The basic/technical/advanced/full/custom tool profiles. Capability and operation tools are always included. A profile limits exposure and never grants authority. | TC-043, TC-054, AD-429 |
| `service/context.py` | Trusted `InvocationContext`. The application namespace is required and no identity comes from tool arguments. | TC-048 |
| `service/dispatch.py` | The dispatcher shared by MCP and REST. Checks run in this order: registry → authorization policy → implemented and in profile → input schema → handler semantic checks → handler. It assigns the request ID, freezes the arguments, contains handler exceptions as an `internal_error` issue that carries no detail, lets cancellation propagate, and validates every returned envelope against the tool's output schema. Tools without a handler return an explicit `unsupported_capability` failure, not a stub. | TC-005, TC-042, TC-047–050, TC-054; PRP-001 §7 |

Validation on 2026-11-26 (WSL2 Linux x86-64, Python 3.12, uv 0.13.10, `uv run --locked`):

- `pytest`: 465 passed (unit tests only). This covers forged context fields (`application_id`, `user_id`, `agent_id`, `instance_id`, `permissions`, `request_id`) added to an otherwise valid request for all 32 tools, conflicting selectors, format validation, non-reflection of supplied values, and failure envelopes valid for all 32 tools.
- `ruff check`, `ruff format --check`, `mypy` (strict): clean.
- Mutation checks. When the closed-object rule is removed from projected schemas, all 192 forged-context tests fail. Skipping the authorization check, or skipping output validation, fails the corresponding dispatcher test. Each mutation was reverted.

Remaining for F02: typed request records for the enabled tools and provider configuration types, plus the safe configuration parser. The MCP and REST adapters on the dispatcher belong to F03.
