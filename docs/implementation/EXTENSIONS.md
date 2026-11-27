# Installing an approved provider extension

An extension is a provider implementation that is not shipped with Grenslan, for example an adapter for a private repository or a specialized search service. This guide is for operators and extension developers. The rules come from PC-004 and the approved registration specification, `PROVIDER-REGISTRATION.md`.

Only the operator can install an extension, by building a container image. No tool, request or configuration value can install, load or activate code. Configuration can only select an implementation that the image already registers, by its implementation ID.

## 1. What an extension provides

An extension is a Python distribution that provides:

1. **A provider class** implementing the family interface from `docs/contracts/PROVIDER_INTERFACES.py`: `describe()`, `initialize()`, `health()`, `shutdown()`, and the method for each declared capability (`search` for `search.query`, and so on; the full mapping is `METHOD_BY_CAPABILITY` in `src/grenslan/providers/registry.py`). Browser providers also need `close_session`.
2. **A factory** that receives `InstanceSettings` (the configured provider ID and its validated settings) and only constructs the provider. It must do no I/O: it also runs during `check-config`, and connection work belongs in `initialize()`.
3. **An `Implementation`** registration:

   ```python
   from pathlib import Path

   from grenslan.providers.registry import Implementation

   def implementation() -> Implementation:
       return Implementation(
           implementation_id="example_search",
           family="search",
           factory=ExampleSearchProvider.from_settings,
           manifest=Path(__file__).with_name("manifest.json"),
           settings_schema=SETTINGS_SCHEMA,  # JSON Schema for this implementation's adapter settings, or None
       )
   ```

4. **A dependency manifest** (`manifest.json`, schema `src/grenslan/providers/MANIFEST_SCHEMA.json`). Its `manifest_id` must equal the description's `dependency_manifest_id`. Its identity, version, family, contract version and platforms must equal the description. It lists:
   - the required Python distributions and their exact versions;
   - every binary, model-weight file or browser build the provider runs or loads, each with its SHA-256 digest;
   - license notices, as paths relative to the manifest;
   - known limitations.

   Platform names are `linux-x86_64`, `linux-aarch64` and `any`.
5. **Documentation and tests:** the implementation ID, family, capabilities, settings, license evidence, and tests of its declared behaviour and failure modes.

## 2. What Grenslan checks at registration

Registration happens at startup and in `grenslan check-config`, for every provider that configuration enables. Any failure stops startup before the port is bound, with a message naming the provider:

- the declared implementation ID and family match the registration, and the contract version is 1.0;
- the declared capabilities are in the family and unique, and each has a callable method;
- the manifest is strict JSON and valid, and it matches the declaration;
- the running platform is supported;
- each listed distribution is installed at its listed version;
- each listed file has its recorded digest, so a modified or replaced executable fails;
- each license notice exists.

Disabled providers are not created or verified. Python package files are trusted through the image build and are not rehashed at startup.

## 3. Installing it

Build a derived image:

1. Install the extension and its dependencies with pinned versions and hashes, for example `pip install --require-hashes -r extension-requirements.txt`.
2. Add a launcher module that passes the extension, together with the built-in list, to Grenslan's command:

   ```python
   """Grenslan with the approved example_search extension."""

   import sys

   from grenslan.cli import main
   from grenslan.providers.builtin import builtin_implementations
   from example_extension import implementation

   raise SystemExit(main(sys.argv[1:], implementations=[*builtin_implementations(), implementation()]))
   ```

3. Use the launcher as the container command, for example `python -m grenslan_site serve`.
4. Select the implementation in the provider configuration (`implementation: example_search`), with its settings and network scope. Then run `check-config` through the launcher.

Nothing is discovered automatically: installed packages and entry points are never scanned. Removing the extension from the launcher removes it from the service.

## 4. Worked example

The test suite uses this pattern with its fixture search provider:

- `tests/support/fixture_providers.py` is the provider and its registration;
- `tests/support/manifests/fixture.json` is its manifest;
- `tests/support/example_launcher.py` is the launcher.

`tests/unit/test_cli.py` shows that `check-config` accepts a configuration selecting the fixture through the launcher, and rejects it through the plain `grenslan` command. Tests in `tests/unit/providers/` show that a manifest mismatch, an unsupported platform or a modified pinned file stops registration.
