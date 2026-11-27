# Provider registration: manifests, platforms, integrity and extensions

**Status:** Draft for maintainer approval, 2026-11-27. Not yet an implementation requirement.
**Scope:** What the registry validates when it registers an implementation, beyond its declaration and methods, and how an operator installs an approved extension.
**Authority:** PC-004 (operator-controlled registration), PC-056 (lifecycle and registration validation), the registry requirements in PROVIDER_CONTRACT.md ("Registration validates implementation identity, declared family, contract version, capability-to-method compatibility, approved build/dependency manifest and platform"; "Extension registration requires documented package/adapter entrypoint, …, platform support, approved settings schema, actual integrity and license evidence, tests and operator approval"), AD-404, AD-419, AD-422, AD-425; PRP-001 F04 and gate F-G15; T-433, T-459.

The adopted contracts require manifest, platform and integrity validation but do not define the manifest format, the platform names, how integrity is verified, or how an extension is installed. This document proposes decisions R1–R5 (Section 6). Identity, family, contract version and capability-to-method checks are already implemented (`src/grenslan/providers/registry.py`).

## 1. Dependency manifest

**R1.** Every registered implementation, built-in or extension, has one manifest: a JSON file named by the description's `dependency_manifest_id`. The registration supplies it, and it is checked against the implementation's self-description.

```json
{
  "manifest_version": "1.0",
  "manifest_id": "searxng-1",
  "implementation_id": "searxng",
  "implementation_version": "0.1.0",
  "family": "search",
  "contract_version": "1.0",
  "supported_platforms": ["linux-x86_64", "linux-aarch64"],
  "distributions": [
    { "name": "httpx2", "version": "2.16.2", "license": "BSD-3-Clause" }
  ],
  "files": [
    { "path": "/usr/local/bin/example-tool", "sha256": "…", "license": "MIT", "role": "binary" }
  ],
  "license_notices": ["licenses/searxng-client.txt"],
  "known_limitations": ["Results depend on the configured SearXNG engines."]
}
```

- `distributions` lists the Python distributions the implementation needs. Their versions must equal the installed versions; a mismatch fails registration. The lock file stays the source of the pins.
- `files` lists every executable or data file outside Python packages that the implementation runs or loads: binaries, model weights, browser builds. Each carries a SHA-256 digest.
- `license_notices` are paths inside the package to notices that must ship in the container.
- Unknown members are rejected. Values are bounded in count and length.

Built-in manifests live in the package (`src/grenslan/providers/manifests/`) and are covered by the repository's license and dependency review.

## 2. Platform

**R2.** Platform names are `linux-x86_64` and `linux-aarch64`, the container targets, plus `any` for implementations with no platform-specific code or files. The running platform is derived from the operating system and machine (`amd64` is normalized to `x86_64`, `arm64` to `aarch64`). An implementation whose manifest and description do not both list the running platform or `any` fails registration with a message naming the provider and the platform.

## 3. Integrity verification

**R3.** At registration, which happens during startup and `check-config`, the registry:

1. checks that the manifest's identity, family, contract version, version and platforms equal the self-description;
2. checks the installed version of each listed distribution;
3. hashes each listed file and compares its digest, reading in bounded chunks. A missing, unreadable or modified file fails registration with the provider and the manifest path of the file, never its content. This is the "modified pinned executable fails required verification" of T-433;
4. checks that the listed license notices exist.

Any failure is a configuration error that stops startup before the port is bound, but only if the provider is enabled in configuration. A disabled provider's implementation is not verified. Verification is not repeated at runtime; files are replaced by rebuilding the image and restarting.

Python package files are trusted through the image build (pinned lock and hashes at install time) and are not rehashed at startup. Rehashing every installed file would slow every start and would not stop an attacker who can already write to the image.

## 4. Extension installation

**R4.** An operator installs an extension by building a derived container image that:

1. installs the extension's Python distribution with pinned, hash-checked dependencies;
2. adds an operator-written launcher module that calls Grenslan's entry point with the extension's `Implementation` added to the built-in list, for example:

```python
from grenslan.cli import main
from grenslan.providers.builtin import builtin_implementations
from example_extension import implementation

raise SystemExit(main(implementations=[*builtin_implementations(), implementation()]))
```

3. uses that launcher as the container command.

R4 adds the `implementations` argument to `grenslan.cli.main` and the `builtin_implementations()` list used above; neither exists yet.

Registration stays explicit, in code, and under operator control. Nothing is discovered: installed packages and entry points are never scanned, and configuration still selects only implementation IDs. A consumer cannot install, activate or reconfigure anything, because no tool or configuration value loads code (T-459).

The extension's documentation must give its implementation ID, family, capabilities, settings schema, manifest, license evidence and tests, as the Provider Contract requires. Grenslan's documentation gains an extension guide with a worked fixture extension used by the test suite.

## 5. Alternative considered for R4

Entry points discovered from installed packages (`grenslan.providers` group), activated only when an operator approval file lists the implementation ID, distribution and manifest digest. This avoids a launcher module, but brings in discovery and a second approval file, and makes "what is installed" decide what can load. The contract says a plugin framework is unnecessary, so R4 is recommended.

## 6. Decisions requested

| ID | Proposal | Main alternative |
|---|---|---|
| R1 | One JSON manifest per implementation, packaged with it, checked against the description. | Manifest data inside `ProviderDescription` only, with nothing to check it against. |
| R2 | Platforms `linux-x86_64`, `linux-aarch64` and `any`. | Free-form platform strings, which cannot be checked. |
| R3 | At registration, verify distribution versions, file digests and license notices for enabled providers; verification failure stops startup. Python package files rely on the image build. | Rehash every installed Python file at each start. |
| R4 | Extensions via a derived image and an operator-written launcher; no discovery. | Entry-point discovery gated by an approval file (Section 5). |
| R5 | `check-config` performs the same registration, including verification, without initializing providers. | `check-config` validates configuration only. |
