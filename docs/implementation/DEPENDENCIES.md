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

## Compiled code in Grenslan's environment

Identified on 2026-11-27 from the runtime environment `uv export --no-dev` installs, using the same methods as for SearXNG below. The development tools, such as ruff and mypy, are not part of the runtime or the image.

| Wheel | Compiled into it | Licences |
|---|---|---|
| cryptography 50.0.2 | OpenSSL 4.0.3, recorded with its hash in the wheel's `sbom.json`; 39 Rust crates in its CycloneDX SBOM | Apache-2.0 (OpenSSL); crates MIT and/or Apache-2.0 |
| pydantic-core 2.50.5 | 101 Rust crates, from its SBOM | Permissive (MIT, Apache-2.0, BSD, Unicode-3.0 and similar) |
| rpds-py 2026.9.1 | 17 Rust crates, from its SBOM | Permissive |
| pyyaml 6.0.4 | libyaml 0.2.6, built from its git tag by pyyaml's release workflow | MIT |
| cffi 2.1.1 | libffi 3.4.6 | MIT |

No LGPL or GPL code is compiled into Grenslan's environment.

### How notices are kept

`packaging/notices/` holds the notices for all compiled code in both environments:
- `native.lock`: each native library, the source archive its licence files come from (by hash), and the exact wheel versions that embed it. It also lists the compiled wheels that contain only their own code (markupsafe, msgspec, setproctitle).
- `native/`: those licence files, extracted from the verified archives.
- `crates.txt`: the licence files of every Rust crate in the installed wheels' SBOMs (272 crates across granian, cryptography, pydantic-core and rpds-py), with texts that repeat referenced instead of duplicated.
  - Each crate download is verified against the SBOM's hash where it has one. Otherwise it is verified against the `Cargo.lock` in the wheel's PyPI source distribution, itself verified against PyPI's hash.
  - The SBOMs list every platform's dependencies, so a few crates are never compiled on Linux. Two of those (`r-efi`, `wit-bindgen-rt`) ship no licence file; their declared licence is recorded instead.
- `notices.py`:
  - `collect` regenerates the notices. A second run produces identical output.
  - `check` runs during the image build. It fails unless every installed wheel with compiled code is accounted for at its exact version, every SBOM crate has a notice, no entry is stale, and every installed package has licence files.
  - `copy-python` copies each package's own licence files into the image.

The image installs all of this under `/usr/share/doc/grenslan/`, described by `docker/NOTICE.md`.

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

### Libraries compiled into SearXNG's wheels

Several wheels in the lock contain compiled third-party libraries, statically linked, with no separate shared objects. Each extension module links only the system C runtime dynamically (`libc`, `libm`, `libpthread`, `librt`, `libdl`, `libgcc_s`). The libraries below were identified on 2026-11-27 by three means:
- the build paths, version strings and exported symbols in the installed x86_64 binaries;
- the wheels' own licence files and SBOM;
- the build pins of the releases they come from.

**curl_cffi 0.16.3:** `_wrapper.abi3.so` is libcurl-impersonate v2.2.2 (github.com/lexiforest/curl-impersonate), pinned in curl_cffi's `Makefile`. The wheel ships only curl_cffi's own MIT `LICENSE`.

| Library | Version | Licence |
|---|---|---|
| curl (with curl-impersonate patches) | 8.21.0 | curl (MIT-style) |
| BoringSSL | commit `156c7b75ae9b8c3b3f847acf264f17594c3859fb` | Apache-2.0, with ISC and OpenSSL/SSLeay-derived portions |
| nghttp2 | 1.63.0 | MIT |
| ngtcp2 | 1.20.0 | MIT |
| nghttp3 | 1.15.0 | MIT |
| brotli | 1.2.0 | MIT |
| zstd | 1.5.7 | BSD-3-Clause (dual with GPL-2.0; used under BSD) |
| zlib | 1.3.1 | Zlib |
| libidn2 | 2.3.7 | LGPL-3.0-or-later OR GPL-2.0-or-later |
| libunistring subset, embedded in libidn2 | from libidn2 2.3.7 | LGPL-3.0-or-later OR GPL-2.0-or-later |

**lxml 6.1.3:** the wheel's `LICENSES.txt` lists the bundled libraries and their licences.

| Library | Version | Licence |
|---|---|---|
| libxml2 | 2.14.6 | MIT |
| libxslt and libexslt | 1.1.43 | MIT |
| zlib | 1.3.2 | Zlib |
| GNU libiconv | 1.18 | LGPL-2.1-or-later |

**Other wheels:**

| Wheel | Bundled library | Licence |
|---|---|---|
| granian 2.8.3 | 147 Rust crates, listed in the wheel's CycloneDX SBOM (`granian-2.8.3.dist-info/sboms/`) | All permissive: MIT and/or Apache-2.0 (most), plus BSD-2-Clause, BSD-3-Clause, ISC, 0BSD, Unlicense-or-MIT, Unicode-3.0 and Apache-2.0 WITH LLVM-exception. Every crate declares a licence. |
| pyyaml 6.0.3 | libyaml 0.2.5 | MIT |
| cffi 2.1.1 | libffi 3.4.6, the version cffi's Linux release workflow builds | MIT |

msgspec, markupsafe and setproctitle contain only their own code.

### Distribution obligations

- **Permissive components** (MIT, BSD, Apache-2.0, ISC, Zlib, curl and the Rust crates) require their copyright and licence notices to accompany the binaries. The wheels ship only their own package's licence, so the container must carry a third-party notices file covering the libraries above. That includes the Granian crate notices and the BoringSSL `LICENSE`. Apache-2.0 components also need any `NOTICE` files.
- **`python-dateutil`** (Apache-2.0 and BSD-3-Clause) and **`certifi`** (MPL-2.0, unmodified CA bundle) need their notices. MPL-2.0 also requires the source to be available, and it is the published package.
- **SearXNG** (AGPL-3.0-or-later): the complete source is installed alongside it (S6).
- **LGPL components statically linked:** libidn2 and its libunistring subset in curl_cffi, and GNU libiconv in lxml. The LGPL permits static linking, but anyone receiving the binary must be able to rebuild it with a modified version of the library. In practice that means providing:
  - the library's source;
  - the source and build scripts of the program it is linked into (curl_cffi and curl-impersonate, lxml);
  - the LGPL text.

  The official SearXNG image ships the same wheels. Grenslan meets this obligation by publishing the source, as recorded under "Source for bundled components" below.

### Source for bundled components

Decided by the maintainer on 2026-11-27: each release publishes the source of every component in the bundled SearXNG as a release asset on the GitHub Releases page, next to the container image it belongs to. It stays available for as long as that image is offered. That meets the AGPL and LGPL obligations for SearXNG, libidn2, libunistring and libiconv, and it lets anyone audit, modify or rebuild any part.

The source is not included in the container or committed to the repository. The basis:
- The obligation falls on whoever conveys the binaries. The repository contains no third-party binaries: `install.sh` fetches them at build time.
- GPL-3.0 §6(d) (applied by AGPL-3.0, and by LGPL-3.0 §4(d)) and LGPL-2.1 §6(d) let a distributor offer the source from the same place as the binary, or from another server with clear directions beside the binary.
- MPL-2.0 §3.2 requires telling recipients how to obtain the source.

The container must therefore carry:
- the licence texts: AGPL-3.0, GPL-3.0, LGPL-3.0, LGPL-2.1 and MPL-2.0;
- the permissive notices listed above;
- a statement of where the release's source is published.

Anyone who redistributes an image they built has the same obligation for their copy.

SearXNG's own source is installed with it (S6). Everything else is pinned by URL and SHA-256 in three locks under `packaging/searxng/`, and `fetch-sources.sh OUTDIR` downloads and verifies it into one source directory:

| Directory | Lock | Contents |
|---|---|---|
| `native/` | `sources.lock`, maintained by hand | Libraries compiled into the wheels: libcurl-impersonate v2.2.2 with curl, BoringSSL, nghttp2, ngtcp2, nghttp3, brotli, zstd, zlib and libidn2 (whose archive includes its libunistring subset); libxml2, libxslt, zlib and GNU libiconv for lxml; libyaml and libffi |
| `python/` | `sources-python.lock`, generated | The PyPI source distribution of every package in `requirements.lock` |
| `crates/` | `sources-crates.lock`, generated | Every crate in Granian's `Cargo.lock` (190), the same set `cargo vendor` uses, so Granian can be rebuilt on any platform |

`lock-sources.py` regenerates the two generated locks from `requirements.lock` and Granian's source distribution. Run it whenever the SearXNG pin changes.

Where each hash comes from:
- Python packages: PyPI's published hashes.
- Registry crates: the checksums in `Cargo.lock`.
- curl-impersonate's dependencies: its own `CMakeLists.txt`.
- libidn2 and libiconv: computed after checking their GNU signatures with `gpgv`. They were signed by Simon Josefsson and Bruno Haible respectively.
- The remaining native archives and the two git-sourced crates (`interprocess`, `tls-listener`): computed from GitHub archives of their release tag or locked commit. GitHub does not guarantee that such archives stay byte-identical. If one ever changes, the fetch fails and its hash must be checked again.

pip is not pinned. It comes with whichever Python creates the environment, and container packaging deals with it.

Verification on 2026-11-27:
- All 238 archives downloaded into the three directories (102 MB native, 28 MB Python, 43 MB crates) and matched their hashes. `SHA256SUMS` rechecked clean.
- A second run kept every file.
- Running the generator a second time produced identical locks.
- Each of these stopped the run with status 1 and left no files behind:
  - a wrong pinned hash;
  - a path escaping its directory (`native/../x`);
  - an unknown directory;
  - a malformed hash;
  - an `http` URL.
