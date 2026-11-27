# Grenslan service configuration (ingress, authentication and diagnostics)

**Status:** Approved by the maintainer, 2026-11-27 (decisions D1–D8). Normative for the implementation.
**Scope:** The operator configuration that `PROVIDER_CONFIG_SCHEMA.json` deliberately excludes: TLS, listening address, ingress policy, consumer credentials, the MCP-compatible OAuth profile, tool exposure profiles and security-event limits (PROVIDER_CONTRACT.md PC-059; PRP-001 F04: "validate separate ingress/auth configuration").
**Authority:** AD-428 (secure transport, certificate replacement), AD-429 (profiles), ARCHITECTURE.md §16.4 (validated YAML, environment overrides, protected secrets, controlled restart), TC-042–043, TC-048, TC-049; PRP-001 F03–F04 and gates F-G03–F-G05.

Section 9 lists decisions D1–D8. The JSON Schema derived from Section 3 is `src/grenslan/config/SERVICE_CONFIG_SCHEMA.json`; a reviewed sample is `examples/service.yaml`.

## 1. Files

**D1.** Grenslan reads two YAML files:

| File | Contents | Schema |
|---|---|---|
| Service configuration, default `/etc/grenslan/service.yaml` | This document. | `src/grenslan/config/SERVICE_CONFIG_SCHEMA.json` |
| Provider configuration, default `/etc/grenslan/providers.yaml` | Providers, routing, scopes, limits and cache. | The adopted `PROVIDER_CONFIG_SCHEMA.json`, unchanged |

The adopted provider schema rejects unknown top-level keys. Keeping service settings in their own file avoids amending an adopted contract. It also keeps consumer credentials apart from provider credentials, which have a different purpose, scope and audience.

`GRENSLAN_SERVICE_CONFIG` and `GRENSLAN_PROVIDER_CONFIG` override the two paths. Both files use the existing restricted YAML loader: no duplicate keys, tags, anchors, aliases or merge keys, and size and depth bounds. Both are validated together before the service admits any request.

## 2. Example

Values are a starting point to be reviewed per deployment, not production defaults.

```yaml
config_version: "1.0"

listen:
  host: 0.0.0.0            # inside the container; publish the port only where intended
  port: 8443

tls:
  certificate_file: /run/secrets/grenslan_tls_cert.pem
  private_key_file: /run/secrets/grenslan_tls_key.pem

ingress:
  allowed_hosts: [grenslan, localhost]
  allowed_origins: []      # browser page origins allowed to call Grenslan, e.g. https://zygos.lan
  max_request_bytes: 1048576
  argument_limits:
    max_string_chars: 65536
    max_array_items: 1000
    max_depth: 32

tools:
  profile: full            # basic | technical | advanced | full | a custom profile name
  custom_profiles:
    search_only: [web_search, image_search]

credentials:
  qor:
    application_id: qor
    token_sha256: 3f1e...c9a0            # SHA-256 of the token, 64 lowercase hex digits
    permissions: [web_search, image_search, capabilities_get]
    delegation: true
  zygos:
    application_id: zygos
    token_sha256: 8b2d...41f7
    permissions: [web_search, image_search, capabilities_get]
    delegation: false
    profile: search_only
    identity:
      user_id: zygos-owner

oauth:                     # omit the section to disable access tokens
  resource: https://grenslan:8443/mcp
  leeway_seconds: 30
  max_token_lifetime_seconds: 3600
  issuers:
    qor_oidc:
      issuer: https://qor.lan/
      application_id: qor
      jwks_file: /etc/grenslan/keys/qor-jwks.json
      scopes:
        grenslan.search: [web_search, image_search]
      user_claim: sub

security_events:
  max_events_per_window: 100
  window_seconds: 60
```

## 3. Fields

Every section and field is required unless marked optional. Unknown keys are rejected at every level. Identifiers (credential and issuer keys, `application_id`, profile names) match `^[a-z][a-z0-9_.-]{0,127}$`. Identity values match the TC-048 identity pattern already enforced for delegation headers.

| Path | Type and constraints | Notes |
|---|---|---|
| `config_version` | `"1.0"` | |
| `listen.host` | IP address or host name | Address inside the container. |
| `listen.port` | integer 1–65535 | |
| `tls.certificate_file`, `tls.private_key_file` | absolute paths | Read at startup. A missing, unreadable or mismatched pair prevents admission (AD-428). Replaced by changing the files and restarting. Any issuer may supply them; without one, `grenslan tls new` creates them (Section 8). |
| `ingress.allowed_hosts` | nonempty list of host names or IP literals, without port | Matched against `Host`, case-insensitively. |
| `ingress.allowed_origins` | list of origins `scheme://host[:port]`, `https` or `http` | These are browser page origins, not Grenslan's own transport. A request whose `Origin` is not listed gets 403; requests without `Origin` are unaffected. |
| `ingress.max_request_bytes` | integer ≥ 1 | REST and MCP bodies. |
| `ingress.argument_limits.max_string_chars`, `.max_array_items`, `.max_depth` | integers ≥ 1 | TC-049 bounds applied before schema validation. |
| `tools.profile` | `basic`, `technical`, `advanced`, `full` or a custom profile name | Default exposure. |
| `tools.custom_profiles` | optional map of profile name → nonempty list of tool names | Names may not reuse a built-in profile name. Capability and operation tools are always included (TC-043). |
| `credentials` | map of credential ID → credential; may be empty | |
| `credentials.*.application_id` | identifier | Several credentials may share a namespace (rotation overlap). |
| `credentials.*.token_sha256` | 64 lowercase hex digits; unique across credentials | See D2. |
| `credentials.*.permissions` | nonempty list of registered tool names, no duplicates | |
| `credentials.*.delegation` | boolean | Permits the `Grenslan-*-Id` headers (TC-048). |
| `credentials.*.profile` | optional profile name | Narrows exposure for this credential. It never grants permissions. |
| `credentials.*.identity.user_id`, `.agent_id`, `.instance_id` | optional identity values | Fixed context when the request does not delegate. |
| `oauth` | optional section | Absent: access tokens are not accepted and no metadata document is published. |
| `oauth.resource` | `https` URL without query or fragment | Token audience and metadata `resource`. Its host must be in `ingress.allowed_hosts`. |
| `oauth.leeway_seconds` | integer ≥ 0 | |
| `oauth.max_token_lifetime_seconds` | integer ≥ 1 | |
| `oauth.issuers` | nonempty map of issuer ID → issuer; `issuer` values unique | |
| `oauth.issuers.*.issuer` | `https` URL | Must equal the token's `iss` exactly. |
| `oauth.issuers.*.application_id` | identifier | |
| `oauth.issuers.*.jwks_file` | absolute path to a JSON Web Key Set (`{"keys": [...]}`) of public signing keys | See D4. Private or symmetric key material is refused. |
| `oauth.issuers.*.scopes` | map of scope → nonempty list of registered tool names | |
| `oauth.issuers.*.user_claim` | claim name, or `null` | |
| `security_events.max_events_per_window`, `.window_seconds` | integer ≥ 1, number > 0 | Rate limit per event kind. |

There are no numeric defaults. Every limit is stated by the operator, and the shipped sample supplies reviewed starting values. This follows the rule against fabricated defaults that affect security.

## 4. Consumer credentials

**D2.** The configuration holds only the SHA-256 digest of each consumer token, never the token. Grenslan ships `grenslan credential new`, which generates a token from 32 random bytes and prints it once, with the `token_sha256` line to paste into the configuration. The operator hands the token to the consumer.

Because the token is high-entropy, its digest is not useful to an attacker and needs no secret store. The configuration file should still be readable only by Grenslan's user.

The alternative is a `secret_ref` to a file holding the raw token, as the illustrative configuration in ARCHITECTURE.md §16.4 suggests. It is not recommended: Grenslan would then hold raw tokens it never needs.

## 5. Live credential and issuer reload

**D3.** `SIGHUP` re-reads and fully validates the service file and the referenced key-set files.

- **If valid:** credentials and OAuth issuers (including re-read keys) are replaced atomically. In-flight work whose credential, issuer or key was removed or changed is cancelled; all other work continues. This is the revocation path F03 and F-G05 require without a restart.
- **If invalid:** nothing changes, and the problems are logged as on startup.
- **Changes needing a restart:** `listen`, `tls`, `ingress`, `tools`, `security_events`, adding the `oauth` section, and `oauth.resource`, `oauth.leeway_seconds` and `oauth.max_token_lifetime_seconds`. These are reported in the log and not applied.
- **Removing the `oauth` section** removes every issuer, so all access tokens are revoked at once. The metadata document is withdrawn at the next restart.

A controlled restart also applies everything. The provider file is not reloaded by `SIGHUP`; provider changes need a restart (PC-056: "Reconfiguration and controlled restart are sufficient").

## 6. OAuth key sets

**D4.** Issuer signing keys come from a local JWKS file per issuer. Grenslan never fetches a JWKS URI at runtime, so deployments stay suitable for restricted networks with no runtime downloads (AGENTS.md §4). Key rotation means replacing the file and sending `SIGHUP`. A future approved option may add a bounded, scoped fetch through the outbound enforcement layer.

## 7. Environment overrides

**D5.** Only the scalar and list settings below can be overridden. Credentials, issuers and profiles cannot, because they are structured security policy and belong in the reviewed file.

| Variable | Setting | Format |
|---|---|---|
| `GRENSLAN_SERVICE_CONFIG`, `GRENSLAN_PROVIDER_CONFIG` | file paths | path |
| `GRENSLAN_LISTEN_HOST` | `listen.host` | string |
| `GRENSLAN_LISTEN_PORT` | `listen.port` | decimal integer |
| `GRENSLAN_TLS_CERTIFICATE_FILE`, `GRENSLAN_TLS_PRIVATE_KEY_FILE` | `tls.*` | path |
| `GRENSLAN_ALLOWED_HOSTS`, `GRENSLAN_ALLOWED_ORIGINS` | `ingress.allowed_hosts`, `ingress.allowed_origins` | comma-separated; empty string means an empty list |
| `GRENSLAN_MAX_REQUEST_BYTES` | `ingress.max_request_bytes` | decimal integer |
| `GRENSLAN_TOOLS_PROFILE` | `tools.profile` | string |

Rules:
- Overrides are applied to the parsed file and then validated by the same schema and checks; problems name the variable, not its value.
- Any other variable starting with `GRENSLAN_` is an error, so a misspelt override can't be silently ignored.
- The provider file has no environment overrides in the foundation. Any added later get the same treatment.

## 8. Commands

**D6.**
- `grenslan check-config`: validates both files and the environment overrides, loads the TLS pair and key sets, reports every problem with its location, and exits nonzero on failure. It never prints secret values or digests.
- `grenslan serve`: performs the same validation, then starts HTTPS. Any validation failure stops startup before the port is bound.
- `grenslan credential new`: see D2.
- `grenslan tls new`: for deployments without their own certificate issuer. It creates an ECDSA P-256 server certificate for the given `--name` host names and IP addresses, signed by a new private CA, or by an existing CA given with `--ca-certificate` and `--ca-key` so that a replacement needs no new trust. `--days` (at most 825) and, for a new CA, `--ca-days` (at most 3650) are required, and the certificate cannot outlive its CA. Existing files are never overwritten; private keys are created owner-only. It prints the `tls` lines for this file; consumers trust the CA certificate. A new certificate takes effect at restart.

**D7.** The server runs as one process with one event loop. Uvicorn is already pinned; the container's process supervision is settled with packaging and F05 (SearXNG).

**D8.** Provider initialization, health checks and shutdown each run within a deadline taken from the provider configuration's global `timeout_ms`.

- **Invalid configuration** of any kind stops startup before the port is bound. Examples: an unknown implementation, a schema violation, or a declaration that does not match the implementation's methods.
- **A provider that fails to initialize** or later becomes unhealthy does not stop startup. Its state becomes `unavailable` or `degraded`. Every capability it alone serves is reported `unavailable` by `capabilities_get`, and requests needing that capability fail with an explicit issue. This is the explicit required-failure reporting of PC-056, and it keeps unrelated capabilities working.

## 9. Decisions

| ID | Proposal | Main alternative |
|---|---|---|
| D1 | Separate `service.yaml`; the provider file and its adopted schema are unchanged. | One file, which requires amending the adopted provider schema. |
| D2 | Token digests in configuration, plus a `credential new` command. | Raw tokens in secret files referenced by name. |
| D3 | `SIGHUP` reload of credentials and issuers only. | Restart for every change, which cancels unrelated work on revocation and does not meet F-G05. |
| D4 | Local JWKS files only. | Runtime JWKS fetch, a new outbound dependency. |
| D5 | Small override allowlist; unknown `GRENSLAN_*` variables are errors. | Generic `GRENSLAN__SECTION__KEY` mapping for every field. |
| D6 | `check-config`, `serve` and `credential new` commands. | Server start only. |
| D7 | Single process on Uvicorn. | Not applicable until packaging. |
| D8 | Lifecycle deadlines from the provider configuration's `timeout_ms`. Invalid configuration stops startup; provider failure makes only the affected capabilities `unavailable`. | Stop startup whenever any enabled provider fails to initialize. |
