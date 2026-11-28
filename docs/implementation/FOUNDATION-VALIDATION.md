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
- **Open design gap:** this enforcement runs inside the Grenslan process. It cannot govern outbound traffic that SearXNG, a separately supervised process, makes to its upstream engines, which PRP-001 F05 and AD requirements on outbound destination enforcement require. Candidate designs, which need validation and maintainer review: (a) configure SearXNG's outgoing requests to use a Grenslan-operated local egress proxy that applies the same policy, combined with an operating-system or container-network rule that prevents the SearXNG process from connecting anywhere else; (b) a container network policy alone. SearXNG documents `outgoing.proxies` (https://docs.searxng.org/admin/settings/settings_outgoing.html, read 2026-11-26), with `all://` routing to HTTP, HTTPS, SOCKS4, SOCKS5 or `socks5h` proxies; with `socks5h` the proxy performs name resolution, so a Grenslan `socks5h` egress proxy could apply the same `PolicyBackend` checks. The same page shows SearXNG's outgoing client is based on `curl_cffi`. The maintainer directed on 2026-11-26 that SearXNG's actual outbound requests be examined first, to determine whether and how they are a problem, before an egress design is chosen. Proxy settings are cooperative, so option (a) would still need an enforced restriction on the SearXNG process's direct egress; a non-privileged way to apply one inside the primary container has not been verified. **Follow-up, 2026-11-27:** SearXNG's actual outbound requests were examined as directed; the results and a proposed design are in `docs/implementation/SEARXNG-EGRESS.md` (decisions S1–S6, awaiting maintainer approval).

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
| MCP SDK / ingress spike | Gate validated (Section 4.5); SDK and types selected (Section 4.8). Request cancellation and the MCP authorization profile are implemented in F03 (Section 6.2). Security advisories for the pinned versions remain to be reviewed before release. |
| TLS and identity | Direct TLS with private test CA validated for MCP (Section 4.5). REST, delegation headers and certificate replacement by restart are implemented and tested in F03 (Section 6.2). |
| Provider config | Safe parser and cross-field scope/registry checks with sanitized fixtures. |
| Outbound enforcement | In-process mechanism validated (Section 4.8). SearXNG upstream egress control is an open design gap needing validation and maintainer review. |
| SearXNG | Interface, distribution, licence and outgoing-proxy support verified (Sections 4.8–4.9). Select and pin a build, decide the application server, and validate process isolation and upstream egress control. |
| Specialized providers | Official interfaces verified (Section 4.9); unverified items listed in `PROVIDER-APIS.md`. Fixtures and approved smoke queries remain for F06. |
| Execution and resource defaults | Measure and document effective limits, concurrency, bounded operation/cancellation and no unapproved telemetry. |
| Container availability | Docker/WSL2 or appropriate Linux environment, nonprivileged protected endpoint proof; platform constraints remain explicit. |

Complete applicable rows before the dependent code work. The approved PRP permits documentation, validation and independent work packages within scope; do not mark the preflight complete merely because initial checks pass. Full architecture acceptance status remains 0 of 120 until actual tests are executed and recorded.

## 6. Implementation progress

### 6.1 F02: canonical contracts and common dispatch

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

Provider configuration, added in `src/grenslan/config/`:

| Component | Behaviour | Contract basis |
|---|---|---|
| `config/yaml_loader.py` | PyYAML 6.0.4 safe loader, restricted to plain data. Rejects duplicate keys, every explicit tag (executable `!!python/*`, custom, `!!binary`, `!!set`, `!!str`), anchors, aliases, merge keys, unquoted timestamps, non-finite floats, non-string keys, a non-mapping root, multiple documents, oversized text and nesting deeper than 32. Structure is checked on the parser event stream before composition, so deep nesting cannot exhaust the stack. Errors give the line number but no content, including no source snippet. | PC-059; F-G15 (YAML portion) |
| `config/provider_config.py` | Validates against the packaged byte-identical copy of `PROVIDER_CONFIG_SCHEMA.json`, then runs the cross-field checks listed below and reports every problem together. Returns an immutable `ProviderConfig`. `routes(family)` gives the executable route order: enabled instances only, and no intelligence route while `optional_intelligence_enabled` is false. | PC-059, PC-060 |
| `config/loader.py` | Reads the file with a size bound, decodes strict UTF-8, then parses and validates. Every failure is a `ConfigLoadError` carrying a line or JSON-pointer location. | PC-059 |

Cross-field checks implemented:
- implementation IDs resolve in an explicit `ImplementationSpec` registry with a matching family;
- route entries exist and their family matches the route;
- network, disclosure and credential scope references exist;
- a credential's purpose matches the provider family, and its network scope matches the provider's;
- every enabled search, retrieval, browser or intelligence provider (including internal SearXNG) has network and disclosure scopes;
- `offline` and `internal_only` modes reject public-web scopes on enabled providers;
- endpoints carry no user information and no credential-like query parameters, match an approved scheme, host and port destination of their scope, and use plain HTTP only where the scope sets `allow_outbound_http`;
- provider limit overrides do not exceed global limits;
- `adapter_settings` is rejected unless the implementation has an approved closed settings schema, and is validated against it;
- model-assisted OCR references an existing, enabled intelligence provider that declares `model_ocr`, with the master switch on;
- a browser's default profile is in `allowed_profiles`, and each allowed profile exists and uses the provider's engine.

Validation on 2026-11-26 (same environment): `scripts/check.sh` passed, with 538 unit tests. Mutation checks: disabling the limit-override check, the endpoint-destination check or the isolated-mode check each fails its tests, and each mutation was reverted.

Interpretations, approved by the maintainer on 2026-11-27:
- (a) Credential-like query parameters are detected by name, using the markers key, token, secret, password, passwd, auth, signature, sig and credential. Any query parameter whose name contains one of these is rejected.
- (b) An enabled intelligence provider while `optional_intelligence_enabled` is false is not a configuration error. It simply never executes.
- (c) In `offline` and `internal_only` modes, destinations are not yet checked statically for private addresses. Runtime egress enforcement (Section 4.8) remains authoritative.

Typed records and argument bounds, added 2026-11-27:

| Component | Behaviour | Contract basis |
|---|---|---|
| `providers/contract.py` | Runtime Provider Contract 1.0 types: common records and protocols, the search family, and the shared records it depends on (`Range`, `Region`, `Locator`, `Heading`, `Metadata`). A conformance test loads the adopted `PROVIDER_INTERFACES.py` and compares field names, order, annotations and defaults, protocol method signatures and every vocabulary alias. Construction enforces the PC-058 invariants: partial needs a value and an issue; failed, cancelled, timed_out and interrupted need an issue; issue codes are known and messages are 1–1000 characters; limits are positive (redirects and retries may be zero); a discovery has rank ≥ 1, carries a URL, image URL or source-page URL, and has unique `category_metadata` names; record tuples contain only their declared types. The other provider families are added with the milestones that implement them. | PC-055, PC-057, PC-058 |
| `contracts/requests.py` | Typed request records for `web_search`, `image_search`, `capabilities_get` and `operation_status`, `operation_results` and `operation_cancel`, built from schema-validated arguments. Omitted fields take the schema default, or `None` where the schema declares none. A test checks field names, required fields, defaults and enum vocabularies against the canonical schemas. Request-local semantic checks: `date_from` after `date_to`; a domain both included and excluded; `retrieve.max_sources` greater than `max_results`. | TC-047, TC-049 |
| `service/dispatch.py` (`ArgumentLimits`) | Operator bounds on string length (including property names), array size and nesting depth, checked breadth-first without recursion before schema validation, so decoded MCP arguments get the same protection as REST bodies. | TC-049 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed, with 654 unit tests. Mutation checks: changing a provider record default, renaming a protocol parameter, removing an issue code, or reordering a request enum each fails the conformance tests. Each mutation was reverted.

F02 status: the work package's code is complete and its deliverables (schema conformance tests and the common authorized invocation boundary) exist, so the Archon task is in review.

Gate evidence:
- F-G01: the schema portion is satisfied: 32 tools, and packaged copies byte-identical to the adopted contracts. Installation and search startup remain.
- F-G16: dispatcher-level exposure and explicit `unsupported_capability` responses are evidenced. Capability-state projection (`capabilities_get`) belongs to F04, and search composition to F06.

Moved to later work packages by PRP-001:
- F04: ingress and authentication settings, environment overrides, and wiring the configured `ArgumentLimits` and request-size values.
- F03: the MCP and REST adapters on the dispatcher.

### 6.2 F03: secure ingress and trusted context

Implemented in `src/grenslan/server/`:

| Component | Behaviour | Contract basis |
|---|---|---|
| `server/tls.py` | Server TLS context: TLS 1.2 minimum (1.3 negotiated when offered), compression and renegotiation disabled. Missing or unreadable certificate material fails with a generic error that does not echo file contents. | AD-428, TC-002 |
| `server/auth.py` | Operator-issued application credentials, held only as SHA-256 digests and compared in constant time. Exactly one `Authorization: Bearer` header of at most 4096 bytes is accepted; every failure carries the same message. A credential binds an application namespace, permitted tools and, only when delegation is allowed, the right to assert `Grenslan-User-Id`, `Grenslan-Agent-Id` and `Grenslan-Instance-Id`. Unknown `Grenslan-*` headers, duplicates, non-ASCII values and values outside the identity pattern get 400; delegation headers from a non-delegating credential get 403. The store is replaced as a whole for rotation and revocation and notifies watchers of revoked or changed records. | TC-003, TC-048 |
| `server/app.py` | When OAuth is configured, serves the protected resource metadata at `/.well-known/oauth-protected-resource` followed by the resource URI's path, without authentication. Request gate for every route: exactly one `Host` naming a configured host (else 400), and an `Origin`, when present, must be configured (else 403, before authentication). `Cache-Control: no-store` and `X-Content-Type-Options: nosniff` on every response. REST `POST /api/v1/tools/{tool}`: authentication, then `application/json` (UTF-8 only), then a body bounded by both the declared and the streamed length, then the common dispatcher. Statuses: 200, 202 for accepted, 400, 401 with a Bearer challenge, 403, 404, 405, 413. Artifact and upload routes are not registered until their milestones. | TC-048, TC-050 |
| `server/mcp_endpoint.py` | MCP Streamable HTTP on `POST /mcp`, revision 2026-07-28 only, using the SDK in stateless JSON-response mode behind a gate. Other methods get 405 with `Allow: POST`. A missing or duplicated `MCP-Protocol-Version` gets 400 with -32020; any other version, including every handshake-era version, gets 400 with -32022 and the supported list. Legacy session headers are stripped and no session is issued. Discovery lists only tools the trusted context may use, with the canonical projected schemas. Results carry the canonical envelope as `structuredContent`, with `isError` for failure statuses and a text copy bounded to 8 KiB. An unknown tool is a protocol error (-32602). | TC-001, TC-048, F-G02, F-G03 |
| `server/app_support.py` | Shared ingress pieces. `run_while_authorized` cancels in-flight work when its principal is revoked, changed or, for an access token, expires; REST then answers 401 and MCP a protocol error. | TC-048, AD-428 |
| `server/oauth.py` | MCP-compatible access tokens, validated locally as JWTs against operator-configured trusted issuers and public signing keys (RS256 or ES256 only; RSA at least 2048 bits, EC on P-256; private or symmetric key material refused at configuration). The token must name a configured issuer and a configured key whose algorithm matches its header. `iss`, `aud`, `exp` and `iat` are required, the audience must include the configured resource URI (RFC 8707), and the token must be current within the configured leeway and no longer-lived than the configured maximum. Headers that let a token choose its own key or alter processing (`jku`, `x5u`, `jwk`, `x5c`, `crit`, `b64`) and foreign `typ` values are refused. Each issuer maps to one application namespace; operator-mapped scopes give the tool permissions; an optional claim gives the user identity. Tokens never carry delegation. Every rejection has the same message. Replacing the issuer configuration revokes in-flight work admitted by a removed or changed issuer or key. Publishes the RFC 9728 protected resource metadata document. | TC-048 |
| `server/authenticator.py` | Looks up the bearer token among application credentials first, then, if OAuth is configured, validates it as an access token. The 401 challenge carries `resource_metadata` when OAuth is configured and `error="invalid_token"` when a token was presented and refused. | TC-048 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 741 tests, of which 49 are integration tests against a real HTTPS server on loopback. They cover authentication failures, delegation and forged identity, unpermitted and unknown tools, content type and size limits, revocation of a pending request and of in-flight work on both interfaces, refusal of plaintext HTTP and of TLS below 1.2, rejection by a client that does not trust the test CA, TLS 1.3 negotiation, Host and Origin enforcement, protocol version rejection, the legacy `initialize` handshake and MCP discovery and calls through the SDK client in current-revision mode. Mutation checks: skipping the protocol version check (3 failures), the Origin check (2), the per-context tool filter (1), or the revocation watch (2) each fails the suite, and each mutation was reverted. The test server shuts down within two seconds, so a regression of this kind fails rather than hangs.

Authorization profile decision (maintainer, 2026-11-27): MCP-compatible access tokens are validated locally as signed JWTs against configured keys, not by token introspection. Operator-issued application credentials remain the primary profile. Basis: the intended consumers' existing identity infrastructure (one OIDC provider publishing RS256 keys, no introspection endpoints), no per-request call to an authorization server, and suitability for restricted networks. Trade-off: an access token cannot be revoked individually before it expires. Removing its issuer or key revokes it, and in-flight work stops at expiry.

Access-token validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 810 tests, 63 of them integration tests. Added: 55 validator unit tests (valid RSA and EC tokens; wrong audience, issuer, signing key or key ID; missing required claims; expired, not yet valid and over-long tokens; forbidden headers; unsigned and HMAC-with-public-key tokens; algorithm and key mismatch; malformed tokens; unsafe key configuration; revocation on issuer replacement) and 13 integration tests (metadata published only with OAuth configured, challenge parameters, token-authorized REST and MCP discovery and calls, scope enforcement, identity headers refused for tokens, cancellation at expiry and on issuer removal over both interfaces, static credentials unaffected), plus one confirming that an SDK client in `mode="auto"` settles on revision 2026-07-28. Mutation checks: disabling the audience check, the forbidden-header check, the expiry deadline, the token revocation watch or the metadata challenge each fails the suite, and each mutation was reverted.

Limitations of the access-token profile:
- Signing keys are configuration; key sets are not fetched from a JWKS URI at runtime. Key rotation means replacing the issuer configuration.
- An issuer maps to a single application namespace. Distinct namespaces for tenants of one authorization server need separate issuer entries.
- A token whose scopes grant no permitted tool is authenticated but sees no tools; the HTTP `insufficient_scope` step-up response is not used, consistent with tool-level authorization failures being tool results.
- Configuration is programmatic until F04 provides the operator configuration file and environment overrides.

Security diagnostics, revocation isolation and certificate handling, added 2026-11-27:

| Component | Behaviour | Contract basis |
|---|---|---|
| `server/security_events.py` | One structured `WARNING` event on the `grenslan.security` logger per rejected or revoked request. The events are `authentication_failed`, `context_rejected`, `host_rejected`, `origin_rejected`, `authorization_denied`, `request_too_large` and `work_revoked`. Fields: interface, client address, application namespace and principal (`credential:<id>` or `token:<issuer>#<kid>`), a reason from a fixed vocabulary, and named details. Request-derived values (rejected `Origin` or `Host`) are reduced to printable ASCII and cut to 128 characters. Tokens, `Authorization` values, credential digests and rejected identity-header values are never recorded. Each event kind is limited per window; suppressed events are counted and reported with the next event of that kind. | PRP-001 F03; F-G14 (diagnostic redaction portion) |
| `server/auth.py`, `server/oauth.py` | Failures carry an internal reason (`missing`, `malformed`, `unknown_credential`; for tokens `expired`, `not_yet_valid`, `audience`, `issuer`, `unknown_issuer`, `unknown_key`, `signature`, `missing_claim`, `lifetime`, `header`, `scope`, `user_claim`, `malformed`) used only in the security event. The client still receives the same 401 and fixed message. | TC-048 |

Certificate replacement: AD-428 requires certificate material that is replaceable without rebuilding the container, and the architecture states that a controlled restart is sufficient. Certificate and key are read from the configured files at startup, so no live reload is implemented.

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 853 tests, 83 of them integration tests. Added:
- unit tests for event structure, attribution, sanitizing, bounding, rate limiting and failure reasons;
- 11 integration tests asserting the emitted events and that the sent token and rejected identity-header values do not appear in the log;
- revocation of one credential while another credential's request is in flight: the revoked request gets 401 and the other completes with 200;
- malformed MCP messages (invalid JSON, wrong JSON-RPC version, batch, non-object) and a `Mcp-Method` header that contradicts the body, all rejected with 400 before any handler runs;
- client rejection of an expired server certificate and of a wrong hostname;
- certificate files replaced at the same mounted paths and a restart: the new certificate is served, and a client trusting only the previous CA is rejected.

Mutation checks: logging the `Authorization` value, logging rejected identity-header values, dropping the MCP denial event, always reporting `expired` instead of `revoked`, removing the rate limit, and making credential replacement cancel all work each fail the suite. Each mutation was reverted.

F03 status: the work package's requirements are implemented and its deliverable is met: verified HTTPS MCP and REST calls against a real local TLS server with a private test CA, and no in-process transport shortcut. The Archon task is in review.

Gate evidence from F03 (foundation gates are assessed together at the milestone gate):
- F-G02: MCP 2026-07-28 discovery and invocation and REST equivalents over HTTPS; unsupported and handshake-era revisions, legacy `initialize`, other methods and plaintext rejected; no plaintext listener. Starting a foundation search with a deterministic fixture provider depends on F05 and F06.
- F-G03: trusted private CA accepted; untrusted CA, expired certificate and wrong hostname rejected; certificate replacement by restart without rebuild. Grenslan-provided clients (T-502) do not exist yet; they are checked when the SDK and CLI are built.
- F-G04: missing, invalid and revoked credentials denied; forged namespace and identity arguments rejected; unauthorized and duplicate delegation headers rejected; static credentials and access tokens go through the same dispatcher policy.
- F-G05: revoking one active credential does not cancel another credential's work. Isolation of cursors, caches and operations is shown with F06 and F07.
- F-G14: diagnostic output redaction for ingress. Source-credential and query-disclosure scoping belong to F05 and F06.

Limitations carried forward:
- Ingress settings, credentials, issuers, security-event limits and TLS file paths are constructed in code until F04 adds the operator configuration file. The security-event limits then become operator settings.
- Logging is the Python standard library's. Handler, format and destination are deployment configuration, to be documented with packaging.
- Queued work does not exist until F07; revocation of queued operations is verified there.

### 6.3 F04: configuration and provider registry (complete, for review)

Service configuration specification: `docs/implementation/SERVICE-CONFIGURATION.md`, decisions D1–D8 approved by the maintainer on 2026-11-27. Two clarifications were recorded while implementing it, both within D3: `oauth.leeway_seconds` and `oauth.max_token_lifetime_seconds` need a restart (they are not issuers); removing the `oauth` section revokes every access token immediately.

Provider registry and lifecycle:

| Component | Behaviour | Contract basis |
|---|---|---|
| `providers/registry.py` | Implementations are registered explicitly in code by implementation ID and family. There is no package discovery and no loading by name from configuration. Configuration validation can select only registered implementations. Creating an instance checks its self-description against the registration: implementation ID, family, contract version 1.0, at least one capability, each capability unique and in the family, and a callable method for every lifecycle step and declared capability (`close_session` also for browsers). A mismatch, or a factory or `describe` failure, stops startup with a `ProviderRegistrationError` that names the provider but not the exception text. | PC-002, PC-004, PC-056 |
| `providers/runtime.py` | Disabled instances are never created and stay `disabled`. Enabled instances initialize concurrently, each within the lower of the global and instance `timeout_ms`, passing a `LifecycleContext` with that deadline and a cancellation signal. A failed result, an exception, an overrun or an invalid reported state makes that instance `unavailable` with a `provider_unavailable`, `internal_error` or `timeout` issue, without affecting the others or startup. Health refresh moves instances between `ready`, `degraded` and `unavailable` under the same deadline. Shutdown stops every created instance within its deadline and leaves it `stopped`, whatever it does. Eligibility for a capability follows the configured route order, keeping only `ready` or `degraded` instances that declare it; nothing is substituted when none qualifies. Provider exception text is never logged or reported. | PC-006, PC-010, PC-056; D8 |
| `tests/support/fixture_providers.py` | A controlled fixture search provider and configuration, registered only by tests through the same registry, so production cannot return test data or default to it. | PRP-001 F04 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 879 tests; 26 cover registration and lifecycle. Mutation checks: skipping the method check, the family check or the state filter on eligibility, creating disabled instances, or removing the lifecycle deadline each fails the tests. Each mutation was reverted. Tests involving hung providers have an outer bound, so a missing deadline fails rather than hangs.

Service configuration and commands:

| Component | Behaviour | Basis |
|---|---|---|
| `config/SERVICE_CONFIG_SCHEMA.json`, `config/service_config.py` | The service file is read with the restricted YAML loader, then checked against the schema (closed objects, no numeric defaults) and, if that passes, by cross-field checks reported together: listen host, allowed hosts (no port) and exact browser origins (no path, credentials or default port), all lowercased; permissions and scopes name registered tools; token digests unique; profiles exist, and custom profiles neither shadow built-in names nor list unknown tools; the OAuth resource is an `https` URL without query or fragment whose host is allowed; issuer values are `https` and unique. Problems give a location and reason, never the value. | D1, D2, AD-429, TC-043, TC-048, TC-049 |
| Environment overrides | Only the D5 allowlist applies, to a copy of the parsed file, before the same validation. A malformed value or any other `GRENSLAN_*` variable is a problem naming the variable, never its value. | D5 |
| `server/deployment.py` | Builds credentials (a credential profile narrows permissions and never adds to them), issuers from local JWKS files (strict JSON: no duplicate members or non-finite numbers; public RS256 or ES256 keys only), the authenticator, ingress settings, argument limits, the exposure profile and the security log. `AccessReloader` re-reads the service and key-set files: if everything is valid, credentials and issuers are replaced and only work whose grant was removed or changed is cancelled; otherwise nothing changes and the problems are logged. Restart-only changes are logged and not applied. | D3, D4, F-G05 |
| `server/runner.py` | Validates both files, the TLS pair, the key sets and every provider declaration before binding the port; starts providers, serves HTTPS with forwarded headers ignored and no `Server` header, reloads on `SIGHUP` on the event loop, and shuts providers down on exit. | D6, D7, D8, AD-428 |
| `cli.py`, `grenslan` entry point | `check-config` (exit 1 with every problem), `serve`, and `credential new` (32 random bytes, URL-safe, printed once with its `token_sha256`). | D2, D6 |
| `providers/builtin.py` | The production implementation list. It contained no implementations at F04; F05 adds `searxng`. | PC-004 |
| `examples/service.yaml` | Reviewed sample. Its digests are placeholders that no token matches; a test validates it. | Section 2 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 963 tests: 47 cover service configuration and overrides, 21 deployment and reload, 7 the commands, and 6 integration tests run the configured service over HTTPS. Those 6 cover authentication, a real `SIGHUP` revoking one credential while another keeps working, startup stopped before binding by invalid configuration, an unknown variable or a provider declaration mismatch, and a failed provider not stopping startup and still being shut down. Mutation checks: removing profile narrowing, the credential replacement on reload, strict key-set parsing, the unknown-variable check, the resource-host check, digest uniqueness, the default-port origin check or the profile-shadowing check each fails the tests. One mutation survived because a condition in the reload was redundant; it was removed. Each mutation was reverted.

Capability discovery:

| Component | Behaviour | Basis |
|---|---|---|
| `service/capabilities.py` | `capabilities_get` lists each tool in the service profile and the caller's permissions: `unsupported` if not implemented; otherwise `enabled` when every provider capability it needs has a `ready` or `degraded` instance, `unavailable` when enabled instances declare it but none is serving, `disabled` when no enabled instance declares it. Enabled entries carry the serving declarations' formats and limitations, plus a fixed limitation when a serving instance is degraded. Tools the caller cannot see are omitted; requested by name they are `disabled` with no detail, and unknown names `unsupported`. The profile reported is the credential's profile if it has one, otherwise the service profile. Limits are the global output, download, timeout and concurrency limits. Provider identities, endpoints and health details are never reported. | TC-042, TC-043, PC-010, PC-064, AD-416 |
| `server/runner.py` | Every implemented tool declares the provider capabilities it needs in one table, which `capabilities_get` reports from; startup fails if a handler has no entry. | PC-064 |
| Credential and context | A credential's profile name is carried into the trusted invocation context; a change to it is a grant change, so reload treats it as revocation. | TC-043, D3 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 979 tests; 15 unit tests and one integration test cover capability discovery. Mutation checks: dropping the permission or the profile filter, reporting hidden requested tools in full, collapsing `unavailable` into `disabled`, ignoring the credential profile, counting non-serving instances as eligible, or dropping the degraded limitation each fails the tests. Each mutation was reverted.

Limitations:
- The production service implements only `capabilities_get`; other permitted tools return `unsupported_capability` until search (F05, F06) and later work packages are wired in.
- Provider health is refreshed only on demand. The configuration defines no refresh interval, and none is invented.
- Reload reads small, size-bounded files on the event loop.

Registration verification and extensions (`PROVIDER-REGISTRATION.md`, decisions R1–R5 approved by the maintainer on 2026-11-27):

| Component | Behaviour | Basis |
|---|---|---|
| `providers/MANIFEST_SCHEMA.json`, `providers/manifest.py` | Each implementation registers a dependency manifest: strict JSON, closed and bounded. Registration checks that its ID, implementation ID, version, family, contract version and platforms equal the self-description, and that the running platform (`linux-x86_64`, `linux-aarch64`, or `any`) is supported. Each listed distribution must be installed at its listed version, each listed file must match its SHA-256 digest (read in chunks), and each license notice must exist inside the manifest directory. Messages name the item, never file content. | R1–R3, PC-056, T-433 |
| `providers/registry.py` | Manifest verification is part of creating an enabled instance, so it runs before the port is bound. `ImplementationRegistry.check` registers every enabled instance without initializing it. Disabled providers are never verified. | R3, R5 |
| `cli.py`, `providers/builtin.py` | `check-config` performs registration. `main` and the built-in list accept an operator launcher's additional implementations; nothing is discovered from installed packages. | R4, R5, PC-004 |
| `docs/implementation/EXTENSIONS.md`, `tests/support/example_launcher.py` | Extension guide, with the fixture provider as a worked example that the tests run. | R4, PRP-001 F04 deliverable |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 1014 tests. 29 cover manifests, 4 registration with manifests, and 2 the launcher and `check-config` verification. The wheel contains the three packaged schemas. Mutation checks: skipping the digest, platform, distribution-version, license-notice or notice-path check, skipping manifest verification in the registry, registering disabled instances in `check`, or skipping registration in `check-config` each fails the tests. Each mutation was reverted.

Gate assessment for F04:
- **F-G15:** evidenced at the F04 level. Unknown, duplicate and unsafe YAML is rejected (F01 and the service file). A modified pinned executable fails verification. A failed optional provider leaves unrelated capabilities usable (`capabilities_get` stays `enabled`, and the service starts and serves). Unauthorized runtime installation, configuration or activation is denied by construction: registration exists only in code; configuration selects registered implementation IDs only; no tool's closed input schema accepts endpoints, modules or configuration. No dedicated test enumerates that last property across all 32 tools.
- **F-G16:** the capability-state and profile portions are evidenced. Search composition remains for F06.
- **F04 deliverables:** the validated configuration sample (`examples/service.yaml`), the extension documentation, and the provider capability and health tests are present.

Certificate issuance (`grenslan tls new`, added at the maintainer's request on 2026-11-27 because not every integration can issue certificates):

| Component | Behaviour | Basis |
|---|---|---|
| `server/tls_issue.py`, `cli.py` | Creates an ECDSA P-256 server certificate (SAN host names and IP addresses, `serverAuth`, not a CA) signed by a new P-256 private CA (path length 0) or by an operator-supplied EC or RSA CA whose key must match it. Validity is required on the command line, bounded at 825 days for the server and 3650 for a CA, and the certificate cannot outlive its CA. All requests are validated before writing; existing files are never overwritten, including one that appears while writing; private keys are created with mode 0600 and a new directory with 0700. Output gives the configuration lines and CA path, never key material. Externally issued files remain fully supported. | AD-428 |
| `cryptography` | Now a direct runtime dependency, at the version already locked. | DEPENDENCIES.md |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 1035 tests; 21 cover certificate issuance, including real TLS handshakes through the issued CA (accepted for each name, rejected for another) and reissuing from an existing CA. Mutation checks: making the server key world-readable, dropping the overwrite check, opening without exclusive create, dropping the CA-lifetime check for a reused CA, the CA basic-constraints check, the key-match check or the name check each fails the tests. The first run left two mutations alive; tests for a file created during writing and for a reused CA expiring too soon were added. Each mutation was reverted.

F04 is complete for review. The SearXNG provider (F05) adds the first production implementation and manifest.


### 6.4 F05: outbound enforcement and SearXNG (in progress)

SearXNG's outbound behaviour was examined on 2026-11-27 as directed. The findings and the bundled-process design are in `docs/implementation/SEARXNG-EGRESS.md`. The maintainer approved option A and decisions S1–S6, and the tracker-rule decisions T1–T5, on 2026-11-27.

Connection-level outbound enforcement, used by every provider for external requests:

| Component | Behaviour | Basis |
|---|---|---|
| `network/addresses.py` | Only globally routable unicast addresses are public. IPv6 forms carrying an IPv4 address (mapped, NAT64, 6to4, Teredo) are also judged by the embedded address. Metadata (`169.254.169.254`, `fd00:ec2::254`), unspecified, multicast and broadcast addresses are never reachable, even for a destination that allows private addresses. | AD-400, PC-022 |
| `network/policy.py` | Applies a provider network scope. A URL must be absolute `http` or `https`, carry no user information, and match a listed `scheme://host:port` destination (host compared case-insensitively, without a trailing dot, IDNA-encoded, IP literals in canonical form) or, with `public_web`, any host on the standard port: 443 for https, or 80 for plain http. Other ports must be listed. Plain `http` needs `allow_outbound_http`. Only a listed destination with `allow_private_address` may resolve to a private, loopback or link-local address. | AD-400, AD-401, PC-022 |
| `network/backend.py` | The `httpcore2` network backend refuses a host and port the scope does not admit before resolving it. It resolves once per connection and refuses the name if any answer is prohibited. It connects to the checked address literal, not the name, and closes the connection if the peer is not that address. Unix sockets are refused. | AD-400, PC-022 |
| `network/client.py` | `OutboundClient` follows redirects itself, re-checking each hop, with a redirect limit. HTTP method and body follow 301/302/303/307/308 semantics. A `Credential` is bound to one origin and is attached only while the request stays there; after a redirect leaves it, it is never sent again. Credential headers cannot be passed as ordinary headers. TLS verification cannot be disabled, and TLS 1.2 is the minimum; a private CA bundle may be supplied. Proxy environment variables are ignored. The body size and the total time are bounded. Failures are classified as `denied`, `unresolved`, `connect`, `tls`, `timeout`, `redirect_limit`, `too_large` or `protocol`. | AD-398, AD-400, AD-401, PC-022, PC-023 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 1115 tests; 80 in `tests/unit/network/test_outbound.py`. They run against loopback HTTP and HTTPS fixture servers and a substitutable resolver, with no external network access. Covered: hostile address classes; URL scope checks; names resolving to private, mixed or mapped addresses, which are refused without any connection; metadata addresses; single resolution per connection; proxy variables; redirects within and outside the scope, including an IP-literal redirect for an approved name and an https-to-http downgrade; redirect limits and method semantics; credential origin binding; certificate trust and name mismatch; refusing contexts with no verification or a TLS floor below 1.2; body size, timeout, and refused connections; and the backend's own refusal of unlisted targets and of a mismatched peer. Mutation checks: each of 16 weakenings was caught. They covered disabling the address check, the backend's target check, the peer check, connecting by name, per-hop URL checks, the metadata and embedded-IPv4 rules, the plain-HTTP rule, credential origin binding, credential-header refusal, the size bound, and the three standard-port rules for `public_web`.

Egress proxy for confined processes (S1, S3):

| Component | Behaviour | Basis |
|---|---|---|
| `network/egress_proxy.py` | Listens on a new owner-only Unix socket; refuses to replace an existing file. Accepts only `CONNECT host:port HTTP/1.x`. Absolute-form requests get 405. Malformed lines, user information, path characters or bad ports get 400. A head over 8 KiB gets 431, even before it ends; an incomplete head gets 408 after the idle timeout. Each tunnel must be an approved https destination of the scope (403 otherwise), and is opened through `PolicyBackend`, so the resolution, address and peer checks are the same as Grenslan's own requests. Unresolvable or unreachable destinations get 502, a connect timeout 504, and tunnels beyond the limit 503. Bytes sent with the request are forwarded. Tunnelled bytes are relayed unchanged, so TLS stays end to end and the confined process verifies the certificate. A tunnel closes when either side does, or after the idle timeout with no traffic in either direction. | AD-400, PC-022, S1, S3 |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 1139 tests; 24 cover the proxy against loopback upstreams, and were repeated 5 times without a failure. Mutation checks: each of 11 weakenings was caught. They covered the https scope check, the tunnel limit, activity tracking in each direction, the incremental head limit, forwarding early bytes, the socket mode, refusing an existing path, and the method, authority and version checks. SearXNG's observed proxy use (`CONNECT host:443 HTTP/1.1`, with no local name resolution) matches what the proxy accepts. A test with a real SearXNG process comes with the supervised bundled process.

Bundled SearXNG process (S1 to S4, S6):

| Component | Behaviour | Basis |
|---|---|---|
| `packaging/searxng/` | `SOURCE` pins the repository, commit, version and reference image. `requirements.lock` is SearXNG's own runtime and server requirements, with indirect dependencies pinned to the official image's versions. It is hash-locked for Linux and identical for x86_64 and aarch64. `install.sh` fetches the commit, refuses any other commit, writes the version module so that git is not needed at run time, and installs the lock with `--require-hashes --no-deps` into a separate virtual environment. The full source tree stays installed. | AD-423, S6 |
| `searxng/settings.py` | Generates SearXNG's settings as JSON, so configured values cannot alter their structure. Only the configured engines are kept (`keep_only`), and the plugin list is empty. Only JSON is served. The limiter, image proxy and metrics are off. TLS verification is on, HTTP/2 is off, and every outgoing request goes to the relay. | S3 |
| `searxng/confine.py` | Enters new user and network namespaces, mapping only the caller's own user and group IDs. Brings up loopback, and refuses to continue (exit 70) if any other interface exists or a namespace cannot be created. Relays `127.0.0.1:3128` to the egress socket, runs the command as a child, passes on SIGTERM and SIGINT, and exits with the child's status. | S1 |
| `searxng/bundled.py` | Creates a 0700 runtime directory with the settings and two sockets, egress and SearXNG; SearXNG has no TCP listener. It starts the egress proxy and probes confinement: if confinement fails, SearXNG is not started and the error explains why. It then starts Granian (WSGI, one worker, a configured thread count) through the launcher in its own process group, with a five-variable environment and no inherited Grenslan configuration. It waits for `/healthz`. Output is kept, bounded, only until healthy, then discarded, because SearXNG's diagnostics can contain query text. `stop` terminates the process group, escalating to SIGKILL, and removes the runtime directory. | S1, S4, AD-423, F-G14 |

Validation on 2026-11-27 (same environment, unprivileged namespaces available): `scripts/check.sh` passed with 1161 tests. 23 cover settings, the launcher and the supervisor. One integration test runs the real pinned SearXNG under Granian, confined, with engines `wikipedia` and `duckduckgo` and a scope approving only `en.wikipedia.org:443`. The resolver maps that host to loopback, so nothing reaches the internet. The test confirmed the following:
- the runtime directory holds only the settings and the two sockets, at mode 0700;
- a JSON search over the socket returns 200, with both engines reported unresponsive;
- the proxy resolved the approved host, so its tunnel passed the policy;
- the unapproved engine's host was never resolved, and its tunnel was logged as denied;
- the runtime directory was removed on stop.

It passed 5 consecutive runs, and no processes or directories were left behind. Mutation checks: each of 10 weakenings was caught. They covered the network namespace, the identity mapping, the loopback-only check, the empty plugin list, the relay proxy setting, `keep_only`, engine-name validation, the confinement probe, runtime cleanup, and environment inheritance.

SearXNG search provider (`implementation: searxng`, built in):

| Component | Behaviour | Basis |
|---|---|---|
| `providers/registry.py` | A factory receives the instance's resolved network and disclosure scopes and its effective limits (global limits with the instance's reductions). A factory may raise `ConfigurationProblem(location, reason)`; that message is reported, while any other factory failure is still reported only by type. | PC-004, PC-022 |
| `searxng/provider.py` | Bundled (`deployment: internal`) or external. `search.upstream_engines` is required, and each search names exactly those engines. Adapter settings (a closed schema) set the categories the engines serve and `engine_timeout_ms`, which must be below `timeout_ms`. Bundled mode also sets `install_prefix` and `startup_timeout_ms`, needs a scope listing https destinations without `public_web`, and checks the installed build's commit. The disclosure scope must allow queries to external destinations. The query goes by POST (`application/x-www-form-urlencoded`), never in a URL, with no user, agent or application context. The category is applied locally, by SearXNG's result category; language and safe search are applied by the provider, and optional operator defaults (`default_safe_search`, `default_language`, added at the maintainer's request on 2026-11-27) are sent when a request sets neither, with a request's own value taking precedence; region, date, domain, file-type and image-size constraints are reported as unsupported. Continuation and `cache_only` are refused without sending. Each result keeps its SearXNG rank and upstream engine, plus any merged engines and published date; results without an http(s) URL are dropped. Image results carry image, thumbnail, source page and size. Engines that did not respond become retryable `network_error` issues: the outcome is `partial` if any engine answered, `failed` if none did and there are no results, and a responsive empty result is `completed`. HTTP 429 (with `Retry-After`), 403, other statuses and malformed JSON are classified. The deadline and cancellation are honoured. Response size is bounded by `max_download_bytes`. | AD-423, AD-401, PC-022, PC-023, F05 |
| External mode | Uses `OutboundClient` with the instance's scope (no redirects), and `GET /healthz` for health. `credential_ref` and `private_ca_ref` are refused as not yet supported, because no secret or private-CA store exists yet. | S5 |
| `searxng/manifest.json`, `searxng/searxng-notice.txt` | The dependency manifest, plus the AGPL notice stating where the corresponding source is. | R1 to R3, S6 |
| `examples/providers.yaml` | Reviewed sample: bundled SearXNG with three engines and the hosts observed for them. A test loads it and runs the `check-config` registration. | F05 deliverable |

Validation on 2026-11-27 (same environment): `scripts/check.sh` passed with 1207 tests; 42 provider unit tests. External mode was tested against a loopback server through the real outbound client: search by POST, health, and refusal of an endpoint outside its scope. One integration test validates a bundled configuration against the built-in registry, starts the real pinned SearXNG through `ProviderSet`, finds it `ready` and eligible, searches, and shuts down. Its scope approves only an `.invalid` host, so no engine was contacted, and the search failed with both engines reported. Mutation checks: each of 13 weakenings was caught. They covered the engine list in the request, the disclosure check, the category filter, URL validation, the outcome for unresponsive engines, the bundled public-web refusal, `max_results`, the deadline, cancellation, POST, the engine-timeout bound, continuation refusal, and the installed-commit check.

Refinement of S3, accepted by the maintainer on 2026-11-27: S3 says that each allowed engine is mapped to the hosts it may contact, and that the proxy enforces the mapping. A CONNECT tunnel does not say which engine opened it, so the proxy enforces the scope as a whole: the union of the approved destinations. The mapping is therefore operator configuration (the scope lists exactly the hosts the configured engines need, as the sample does), not a per-engine check. Per-engine enforcement would need one relay port per engine, each with its own scope, and SearXNG's per-engine proxy settings.

Network-scope semantics (the schema defines the fields but not their meaning):
- `public_web` admits only the standard port: 443 for https, and 80 for plain http when `allow_outbound_http` is set. Any other port must be a listed destination. Decided by the maintainer, 2026-11-27.
- A listed destination without `allow_private_address` must resolve only to public addresses. `allow_private_address` admits private, loopback and link-local addresses, but never metadata, unspecified, multicast or broadcast addresses.
- A credential is never re-sent within a request once a redirect has left its origin, even if a later hop returns there.
- The last two points are interpretations still open for maintainer review.

Limitations:
- Disclosure scopes (`allow_query` and the rest) are enforced where requests are composed, by providers and the service core, not by this transport layer.
- The redirect limit (5) and body limit (16 MiB) are protective defaults; providers will pass the configured limits when they are wired in.
- HTTP/2 is not enabled for outbound requests.
- The proxy carries https tunnels only. A SearXNG engine needing plain http would need an explicit decision first.
- Proxy timeouts, the tunnel limit, SearXNG's thread count, request timeouts and startup timeout are constructor arguments. Their configured values come with the SearXNG provider's adapter settings.
- The real-process test shows that approved and unapproved tunnels are handled correctly. A completed upstream TLS exchange through the tunnel is not shown, because that would need the internet or a trusted fixture certificate for a real engine host.
- Running in the container needs Grenslan's seccomp profile (S2). See "Container, seccomp profile and notices" below.

#### Container, seccomp profile and notices

| Item | Implementation | Decisions |
|---|---|---|
| Seccomp profile | `docker/seccomp.json` is Docker's default profile (moby/profiles `seccomp/v0.2.3`, byte-identical to the copy vendored in Docker Engine 29.8.2) plus one rule. The rule allows `unshare` only when its flags equal `CLONE_NEWUSER \| CLONE_NEWNET`. `docker/seccomp.py` regenerates the profile; a test asserts it is exactly the default plus that rule, and that it is current. | S2 |
| Image | `docker/Dockerfile`, multi-stage:<br>- **Pinned inputs:** the base image `python:3.12-slim` (Debian 13.8, Python 3.12.16) and uv 0.13.10, both by digest.<br>- **Grenslan:** installed from `uv export --no-dev` with `--require-hashes`, in a venv without pip.<br>- **SearXNG:** installed with `packaging/searxng/install.sh`, after which pip is removed from its venv. pip is also removed from the runtime base.<br>- **Runtime:** uid and gid 10001, `ENTRYPOINT grenslan serve`, port 8443. | AD-423, S1, S4, S6 |
| Notices | `packaging/notices/` (see DEPENDENCIES.md) is checked during the build. Licence files of every Python package in both environments are copied, and all notices are installed under `/usr/share/doc/grenslan/`. SearXNG's complete source stays in `/opt/grenslan/searxng/src`. | AD-423, PRP-001 F05 |
| SearXNG temporary files | SearXNG puts its cache databases (`sxng_cache_*.db`) in `tempfile.gettempdir()`. The confined child now gets `TMPDIR` set to the private 0700 runtime directory. Before, they landed in the shared `/tmp`, readable by all and never removed. Earlier runs of the integration test had left six such files in the development host's `/tmp`; they were removed. | S1 |
| Operator diagnostics | A provider state transition now logs its first issue, for example `initializing -> unavailable (provider_unavailable: SearXNG cannot be confined on this host: ... In a container, run it with Grenslan's seccomp profile (docker/README.md).)`. Before, an operator saw only the state. Issue messages are required to be safe (PROVIDER_CONTRACT). The log line also escapes control characters and is bounded to 500 characters. | PC-010 |

Validation on 2026-11-27 (Docker Engine 29.8.2 on WSL2, Linux 5.15.167.4, x86_64, cgroup v1, no AppArmor):
- **Seccomp:** the profile was exercised directly, by a non-root process with no capabilities and `no-new-privileges`.
  - Under Docker's default, every namespace combination was refused (`EPERM`).
  - Under Grenslan's profile, only `CLONE_NEWUSER | CLONE_NEWNET` was allowed. Each flag alone, and the pair with `CLONE_NEWNS` or `CLONE_NEWPID` added, was still refused.
- **Image build:** `docker build --network host -f docker/Dockerfile -t grenslan:dev .` succeeded. The notices check passed inside the build, and licence files were copied for 43 Grenslan and 32 SearXNG packages.
- **`scripts/check.sh`:** passed with 1237 tests. New tests:
  - 16 for the notices tool;
  - 4 for the seccomp profile;
  - 2 for logged reasons;
  - extended assertions for SearXNG's `TMPDIR`, in a unit test and in the real-process integration test.
- **Integration test against real SearXNG:** fails without the `TMPDIR` change and passes with it.
- **Mutation checks:** nine weakenings of `notices.py check`, and three of the logged-reason change, were each caught. A fourth logged-reason weakening survived and showed that its state filter was redundant, so the filter was removed.

Isolated-endpoint smoke test, `docker/smoke-test.sh grenslan:dev`: 13 checks passed in 77 s.

| # | Check | Result |
|---|---|---|
| 1 | Image user | 10001:10001 |
| 2 | Docker's default seccomp | bundled SearXNG `unavailable`; the service still starts |
| 3 | Grenslan's profile | bundled SearXNG `ready` |
| 4 | Probe container to HTTPS ingress with verified TLS | 401 without a token, 200 `completed` for `capabilities_get` with one |
| 5 | Full TCP scan (1–65535) of the server from the probe | only 8443 open |
| 6 | Listening sockets in the server's network namespace | only 8443, besides Docker's embedded DNS resolver on 127.0.0.11, which `dockerd` places in every container on a user-defined network |
| 7 | Another uid inside the container connects to `searxng.sock` and `egress.sock` | refused: the runtime directory is 0700 and the sockets are 0600 |
| 8 | A process started with `grenslan.searxng.confine` | sees only `lo`; connections to 1.1.1.1, 172.17.0.1 and 169.254.169.254 fail as unreachable |
| 9a | Search over SearXNG's socket | 200; all three engines unresponsive, since the internal network has no route out |
| 9b | CONNECT through the egress proxy | 403 for `example.com:443`, `169.254.169.254:443`, `127.0.0.1:8443`, `grenslan:8443` and `en.wikipedia.org:80`; 502 for the listed `en.wikipedia.org:443`, which passes policy and then has no route |
| 9c | Name resolution on the smoke network | external names do not resolve |
| 10 | Docker socket | absent |
| 11 | `docker stop -t 30` | `stopping -> stopped` without a shutdown warning; exit status 0 in 3 s |

The smoke test was also run with Docker's default profile substituted for Grenslan's. Checks 3, 7, 8, 9a and 9b failed, the script exited 1, and no network or container was left behind.

Limitations of the container work:
- **Bridge network on the development host:** Docker's default bridge (`docker0`) does not exist here. Repairing it would mean restarting the Docker daemon, which runs other services, so it was left alone. Builds use `--network host`, and the smoke test uses its own internal network. The image does not depend on either.
- **Hosts not tested:** hosts that restrict unprivileged user namespaces, through AppArmor on Ubuntu 23.10 and later or `user.max_user_namespaces=0`, are expected to fail closed in the same way. arm64 and rootless Docker are also untested.
- **Build-stage packages:** the build stage installs `git` and `ca-certificates` from Debian at build time, unpinned. They are not in the runtime image.
- **Upstream TLS:** a completed upstream TLS exchange through the proxy, from inside the container, is not shown, for the same reason as the real-process test above. The smoke network has no route out by design.
- **Grenslan's own source:** `fetch-sources.sh` covers SearXNG's environment only. If an image is ever distributed, the source set must be extended to Grenslan's environment as well: OpenSSL in cryptography, and the crates of cryptography, pydantic-core and rpds-py.
- **Gate assessment:** the F05 gate assessment (F-G06, F-G13, F-G14, F-G17, F-G19) is still to be written.
