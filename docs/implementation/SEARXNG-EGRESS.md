# Bundled SearXNG: outbound enforcement and process design

**Status:** Option A and decisions S1–S6 approved by the maintainer, 2026-11-27 (S5: keep the external instance as an operator option). Tracker-URL removal decisions T1–T5 (Section 4) approved by the maintainer, 2026-11-27.
**Scope:** How the bundled SearXNG process is confined so that its outbound traffic obeys Grenslan's destination and disclosure policy, and how Grenslan configures and reaches it.
**Authority:** AD-423 (single primary container bundling SearXNG as a separately managed internal process; endpoint not exposed; no separate container mandatory), AD-370, the deployment decision requiring nonprivileged operation and no host socket, the configuration decision requiring that outbound SearXNG queries comply with provider and disclosure policy, AGENTS.md §4–5 (no runtime downloads; outbound restrictions enforced independently of the component); PRP-001 F05, gates F-G13, F-G14, F-G17.

The maintainer directed on 2026-11-26 that SearXNG's actual outbound requests be examined before an egress design was chosen. Section 1 records that examination; Section 3 proposes decisions S1–S6.

## 1. Observed behaviour

**Method.** `docs/implementation/preflight/searxng-egress/run.sh` runs the official image `searxng/searxng@sha256:1ef964f6dcc811a60e01049717b6e526b25a1c52935350143f04e0ae291b3dbd` (version `2026.9.21-df67eb6c2`) on a Docker `--internal` network with no route out. A probe container answers every DNS query with its own address and records each name, each TLS ClientHello's server name, each HTTP `Host`, and each proxy `CONNECT`. It then closes the connection. Nothing reached the internet. Each run records a startup window of 25 seconds, then one JSON search for a neutral query. Executed 2026-11-27.

| Run | Settings | Startup traffic | Search traffic |
|---|---|---|---|
| direct | defaults, JSON enabled | DNS and TLS to `cdn.jsdelivr.net`, `rules1.clearurls.xyz`, `rules2.clearurls.xyz` (ClearURLs tracker-rule download); DNS for `all.api.radio-browser.info` | DNS and TLS to the five default engines' hosts: `en.wikipedia.org`, `html.duckduckgo.com`, `query.wikidata.org`, `search.brave.com`, `www.google.com` |
| proxied | defaults plus `outgoing.proxies: all://` | **Same as direct: bypasses the proxy** | Every engine request was a `CONNECT host:443` through the proxy, with **no local DNS lookup** |
| restricted | proxied, tracker plugin `active: false`, radio browser `disabled: true` | **Still bypasses the proxy, as above** | As proxied |
| allowlisted | proxied, `engines.keep_only` of five engines, `plugins: {}` | **None** | As proxied; nothing else |

Findings:

1. **Startup downloads.** The `tracker_url_remover` plugin fetches ClearURLs rule lists from three hosts on initialization, outside the proxy setting. This is a runtime download that AGENTS.md §4 rules out.
2. **`active: false` and `disabled: true` do not unload anything.** Every listed plugin is initialized regardless of `active`. A disabled engine is loaded and initialized, and remains selectable by a query (for example the bang `!rb`), because "disabled" only sets the users' default. In this version a user `plugins:` section replaces the default plugin list, and `use_default_settings.engines.keep_only` removes every unlisted engine.
3. **Engine code can bypass the proxy.** The radio browser engine's `init()` calls `socket.getaddrinfo` directly. Proxy settings are cooperative. Each engine is separate code that may open connections of its own, now or in a later version.
4. **With an explicit engine list and no plugins**, all observed traffic used the proxy, and SearXNG did no DNS resolution of its own: the proxy received hostnames.
5. **Confinement inside a standard container.** Docker's default seccomp profile refuses `unshare(CLONE_NEWUSER | CLONE_NEWNET)` with `EPERM`, as root or not. With seccomp relaxed (diagnostic only), an unprivileged process in a new user and network namespace sees only `lo`, and outbound connections fail with "Network is unreachable".

Consequence: configuration alone can make SearXNG well-behaved, but cannot enforce it. Enforcement needs the operating system to deny the SearXNG process any route except Grenslan's policy proxy.

## 2. Options

**A. Namespace-confined process in the primary container (recommended).** Grenslan's supervisor starts SearXNG in a new user and network namespace that has only loopback. SearXNG's only way out is Grenslan's egress proxy, reached through a Unix socket. The proxy applies the same connection-level policy as every other provider: destination allowlist, resolved-address checks, no private or metadata addresses, and the engine-to-host mapping. Grenslan reaches SearXNG through a second Unix socket, so it has no TCP endpoint at all. This meets AD-423 and keeps the container non-root with no added capabilities. It does require operators to run the container with a Grenslan seccomp profile: Docker's default profile with namespace creation for an unprivileged user added. Browser sandboxing in a later milestone is expected to need the same profile, because Chromium's sandbox also uses user namespaces. If namespaces are unavailable, bundled SearXNG fails closed: `unavailable`, with an explicit reason.

**B. SearXNG in its own container on an internal-only network**, with Grenslan's proxy as its only route. This is the simplest strong enforcement and needs no seccomp change. But it makes a second container part of the reference deployment, which AD-423 rules out ("No separate SearXNG container … SHALL be mandatory"), so it would need an architecture change.

**C. Cooperative only:** the allowlisted configuration plus the proxy, with no operating-system enforcement. This does not meet the requirement to enforce outbound restrictions independently of the component. Not recommended, except as an explicit, documented, operator-chosen degraded mode, if one is wanted at all.

## 3. Decisions

| ID | Proposal |
|---|---|
| S1 | Option A: namespace-confined SearXNG process, egress only through Grenslan's policy proxy over a Unix socket, Grenslan-to-SearXNG over a Unix socket. Fail closed when namespaces are unavailable; no cooperative fallback. |
| S2 | Ship a Grenslan seccomp profile (Docker's default plus unprivileged user and network namespace creation) and document running with it. The container stays non-root with no added capabilities. |
| S3 | Grenslan generates SearXNG's settings from its own configuration. SearXNG is never configured by hand. The settings set: `engines.keep_only` from the operator's engine allowlist, so unlisted engines do not exist; `plugins: {}` (tracker removal and other plugins off, so no runtime download); JSON format only; limiter, image proxy and UI features off; `outgoing.proxies` pointing to the proxy relay. Each allowed engine is mapped to the hosts it may contact, and the proxy enforces that mapping. |
| S4 | SearXNG application server: Granian, as in the official image, bound to a Unix socket. uWSGI is not used. |
| S5 | An external SearXNG instance (AD-423) is reached through Grenslan's normal outbound enforcement as an approved endpoint. Its own upstream traffic is outside Grenslan's control, and the documentation says so. |
| S6 | The pinned SearXNG build is recorded by image digest and commit, and the corresponding source is available as AD-423 and the AGPL require. The exact packaging route is settled with the container work. |

Implementation can start now, before these decisions, on the parts every option needs: the in-process connection-level enforcement (from the egress spike), the egress proxy, and the SearXNG search adapter against a fixture server.

## 4. Tracker-URL removal (decisions T1–T5)

The maintainer wants tracker removal kept, with bundled rules. SearXNG's plugin instead downloads the ClearURLs rules at every start, which AGENTS.md §4 rules out and which fails in restricted deployments. The rules change every one to two weeks, so shipping them and updating them are separated:

| ID | Proposal |
|---|---|
| T1 | The image ships a pinned copy of the ClearURLs rules, recorded with source URL, commit, SHA-256 and licence notice. This is subject to verifying the rules' licence. |
| T2 | An optional service setting, `tracker_rules_file`, names an operator-maintained rules file that replaces the bundled copy. It is validated like the key-set files: strict JSON, bounded size, expected structure, every pattern compiled and bounded. |
| T3 | `grenslan tracker-rules update --output FILE`, run by the operator, fetches the current rules, validates them and replaces the file atomically. The operator schedules it (every one to two weeks). Restricted sites run it on a connected machine and copy the file. Grenslan never fetches the rules by itself. |
| T4 | `SIGHUP` reloads the rules. An invalid file changes nothing. |
| T5 | Grenslan applies the rules to search results from every provider; SearXNG's plugin list stays empty (S3). How a cleaned URL is represented in results, and whether the original is retained, is settled against the Tool Contract in F06. |
