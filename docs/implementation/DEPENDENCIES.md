# Grenslan dependency inventory

Generated 2026-11-26 from the installed metadata of a `uv sync --locked` environment (Python 3.12.3, Linux x86_64) at the commit that introduced `uv.lock`, and updated when a dependency changes. Licences are as declared in each package's metadata (`License-Expression`, else trove classifiers). Declared metadata is a starting point for licence review, not a substitute for it.

Runtime packages are those `uv export --no-dev` includes. Dev packages are needed only for linting, type checking and tests and are not distributed with the service.

| Package | Version | Declared licence | Scope | Direct or transitive |
|---|---|---|---|---|
| annotated-types | 0.8.0 | MIT | runtime | transitive |
| anyio | 4.16.0 | MIT | runtime | direct |
| arrow | 1.4.0 | Apache Software License | runtime | transitive |
| attrs | 26.1.0 | MIT | runtime | transitive |
| cffi | 2.1.1 | MIT-0 | runtime | transitive |
| click | 8.5.1 | BSD-3-Clause | runtime | transitive |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause | runtime | direct |
| fqdn | 1.6.0 | MPL-2.0 | runtime | transitive |
| h11 | 0.16.0 | MIT License | runtime | transitive |
| httpcore2 | 2.16.2 | BSD-3-Clause | runtime | direct |
| httpx2 | 2.16.2 | BSD-3-Clause | runtime | transitive |
| idna | 3.20 | BSD-3-Clause | runtime | transitive |
| isoduration | 20.11.0 | ISC License (ISCL) | runtime | transitive |
| jsonpointer | 3.12 | BSD-3-Clause | runtime | transitive |
| jsonschema | 4.26.0 | MIT | runtime | direct |
| jsonschema-specifications | 2025.9.1 | MIT | runtime | transitive |
| lark | 1.3.1 | MIT License | runtime | transitive |
| mcp | 2.3.0 | MIT License | runtime | direct |
| mcp-types | 2.3.0 | MIT License | runtime | direct |
| opentelemetry-api | 1.45.2 | Apache-2.0 | runtime | transitive |
| pycparser | 3.12 | BSD-3-Clause | runtime | transitive |
| pydantic | 2.14.4 | MIT | runtime | transitive |
| pydantic-core | 2.50.5 | MIT | runtime | transitive |
| pyjwt | 2.15.1 | MIT | runtime | direct |
| python-dateutil | 4.0.0 | BSD-3-Clause | runtime | transitive |
| python-multipart | 0.0.34 | Apache-2.0 | runtime | transitive |
| pyyaml | 6.0.4 | MIT | runtime | direct |
| referencing | 0.37.0 | MIT | runtime | transitive |
| rfc3339-validator | 0.1.4 | MIT License | runtime | transitive |
| rfc3986-validator | 0.1.1 | MIT License | runtime | transitive |
| rfc3987-syntax | 1.1.0 | MIT | runtime | transitive |
| rpds-py | 2026.9.1 | MIT | runtime | transitive |
| six | 1.17.0 | MIT License | runtime | transitive |
| sse-starlette | 3.7.1 | BSD-3-Clause | runtime | transitive |
| starlette | 1.10.0 | BSD-3-Clause | runtime | direct |
| truststore | 0.10.5 | MIT | runtime | transitive |
| typing-extensions | 4.16.0 | PSF-2.0 | runtime | transitive |
| typing-inspection | 0.4.5 | MIT | runtime | transitive |
| tzdata | 2026.6 | Apache-2.0 | runtime | transitive |
| uri-template | 1.3.0 | MIT License | runtime | transitive |
| uvicorn | 0.54.0 | BSD-3-Clause | runtime | direct |
| webcolors | 25.10.0 | BSD License | runtime | transitive |
| ast-serialize | 0.13.1 | MIT | dev | transitive |
| iniconfig | 2.3.1 | MIT | dev | transitive |
| librt | 0.17.0 | MIT | dev | transitive |
| mypy | 2.4.1 | MIT | dev | direct |
| mypy-extensions | 1.2.0 | MIT | dev | transitive |
| packaging | 26.4 | Apache-2.0 OR BSD-2-Clause | dev | transitive |
| pathspec | 1.1.1 | Mozilla Public License 2.0 (MPL 2.0) | dev | transitive |
| pluggy | 1.7.0 | MIT License | dev | transitive |
| pygments | 2.21.0 | BSD-2-Clause | dev | transitive |
| pytest | 9.2.0 | MIT | dev | direct |
| pytest-asyncio | 1.5.0 | Apache-2.0 | dev | direct |
| ruff | 0.17.6 | MIT | dev | direct |
| types-jsonschema | 4.26.0.20261006 | Apache-2.0 | dev | direct |
| types-pyyaml | 6.0.12.20261122 | Apache-2.0 | dev | direct |

## Licence review notes

- No GPL, LGPL or AGPL licensed package is present. `jsonschema` is installed with the `format-nongpl` extra because the `format` extra depends on `rfc3987`, which is GPL-3.0-or-later.
- `fqdn` (runtime, via `jsonschema[format-nongpl]`) and `pathspec` (dev only, via `mypy`) are MPL-2.0, a file-level copyleft licence. Distributing unmodified MPL-2.0 files alongside Apache-2.0 code is permitted; modified MPL-2.0 files must remain available under MPL-2.0. Neither file is modified.
- `cryptography` is dual-licensed Apache-2.0 OR BSD-3-Clause, and `packaging` Apache-2.0 OR BSD-2-Clause.
- `typing_extensions` is PSF-2.0.
- `cryptography` is a direct runtime dependency: `grenslan tls new` uses it to issue a private CA and server certificate, and tests use it for throwaway TLS material. It was already locked at the same version through `mcp` and `pyjwt[crypto]`, so no package was added.
- `httpx2` is also declared as a direct dev dependency, at the version already locked for runtime. Tests use it as the HTTPS and MCP client. It adds no package to the lock.
- `pyyaml` (added for the operator configuration loader, PC-059) has no dependencies and ships CPython 3.12 manylinux wheels for x86_64 and aarch64. Only its safe loader is used, behind `grenslan.config.yaml_loader`, which additionally rejects duplicate keys, every explicit tag, anchors, aliases and merge keys.
- `pyjwt` (with its `crypto` extra, which uses `cryptography`) is a direct dependency for validating OAuth access tokens. It was already locked at the same version through `mcp`, so no package was added. Only the RS256 and ES256 verification paths are used, with keys supplied as configuration; PyJWT's key-set fetching client is not used.
- SearXNG (AGPL-3.0) is not a Python dependency of this package. Its distribution and corresponding-source obligations are tracked separately in the validation record.
- Not yet reviewed: licence texts and notice files that must ship in the container, and security advisories for each pinned version.

## Bundled SearXNG (separate environment)

SearXNG is a separately managed component (AD-423). It is not a Grenslan dependency, and nothing in Grenslan imports it. `packaging/searxng/install.sh` installs its complete source at the pinned commit (`packaging/searxng/SOURCE`) and its own virtual environment from `packaging/searxng/requirements.lock`. The lock is hash-verified, Linux-only, and identical for x86_64 and aarch64, and every version equals the official image of the same commit. Grenslan runs SearXNG only as a confined child process, through its HTTP interface on a Unix socket.

SearXNG itself: version `2026.9.21+df67eb6c2`, commit `df67eb6c2608c5b2f909ed7c42b0a4bd3823f78f`, licence AGPL-3.0-or-later. The installed tree keeps the full source, including `LICENSE`, as the corresponding source for the bundled build (S6).

Its environment, from installed metadata on 2026-11-27 (Python 3.12.3, Linux x86_64):

| Package | Version | Declared licence |
|---|---|---|
| annotated-doc | 0.0.5 | MIT |
| babel | 2.18.0 | BSD-3-Clause |
| blinker | 1.9.0 | MIT License |
| certifi | 2026.7.22 | MPL-2.0 |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| curl_cffi | 0.16.3 | MIT |
| flask | 3.1.3 | BSD-3-Clause |
| flask-babel | 4.0.0 | BSD-3-Clause |
| granian | 2.8.3 | BSD-3-Clause |
| isodate | 0.7.2 | BSD License |
| itsdangerous | 2.2.0 | BSD License |
| jinja2 | 3.1.6 | BSD License |
| lxml | 6.1.3 | BSD-3-Clause |
| markdown-it-py | 4.2.0 | MIT License |
| markupsafe | 3.0.3 | BSD-3-Clause |
| mdurl | 0.1.2 | MIT License |
| msgspec | 0.21.1 | BSD-3-Clause |
| pycparser | 3.0 | BSD-3-Clause |
| pygments | 2.21.0 | BSD-2-Clause |
| python-dateutil | 2.9.0.post0 | Dual License |
| pytz | 2026.3.post1 | MIT |
| pyyaml | 6.0.3 | MIT |
| rich | 15.0.0 | MIT |
| setproctitle | 1.3.7 | BSD-3-Clause |
| shellingham | 1.5.4 | ISC License |
| six | 1.17.0 | MIT |
| typer | 0.27.2 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| valkey | 6.1.1 | MIT |
| werkzeug | 3.1.8 | BSD-3-Clause |
| whitenoise | 6.12.0 | MIT |

Still to review before distribution in the container:
- `curl_cffi` wheels bundle a compiled curl-impersonate (curl with BoringSSL and other libraries), and `lxml` wheels bundle libxml2 and libxslt. Their bundled-library licences must be inventoried from the wheel contents.
- `python-dateutil` declares a dual licence (Apache-2.0 and BSD-3-Clause), and `certifi`'s CA bundle is MPL-2.0. Both are compatible with redistribution but need their notices.

