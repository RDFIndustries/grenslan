# Grenslan development setup

This describes the local development workflow for the v0.1 foundation milestone. It does not describe a deployment. Grenslan does not yet provide a running service.

## Requirements

- Linux (the foundation reference environment is Ubuntu 24.04, x86_64).
- Python 3.12. `pyproject.toml` declares `requires-python = ">=3.12,<3.13"`.
- uv 0.13.10 or a later 0.13 release. `pyproject.toml` enforces this through `[tool.uv] required-version`, so an older uv refuses to operate on the project. Upgrade a standalone uv installation with `uv self update`.
- OpenSSL command-line tool, only for the preflight scripts that create throwaway test certificates.

## Install

```shell
uv sync --locked
```

`uv.lock` pins every transitive dependency with SHA-256 hashes. `--locked` fails rather than silently re-resolving if `pyproject.toml` and `uv.lock` disagree. After one online install, the same environment can be recreated without network access:

```shell
uv sync --frozen --offline
```

Direct dependencies are pinned exactly in `pyproject.toml`. To change one, edit the pin, run `uv lock`, and record the new version, licence and reason in `docs/implementation/DEPENDENCIES.md` before committing.

## Checks

Run all checks before committing:

```shell
scripts/check.sh
```

It verifies the lock (`uv sync --locked`), then runs `ruff check`, `ruff format --check`, `mypy` and `pytest`, stopping at the first failure. Extra arguments are passed to pytest, for example `scripts/check.sh -k registry`. The repository has no hosted CI workflow; any CI system can run the same script.

Tests marked `integration` start a real Uvicorn server over HTTPS on a loopback port, using a throwaway private CA generated per test. They need no network access beyond loopback and run as part of `pytest`; `scripts/check.sh -m "not integration"` runs only the unit tests.

Ruff and mypy cover `src/` and `tests/`. `docs/` is excluded from linting because it holds the adopted declaration file `docs/contracts/PROVIDER_INTERFACES.py` and disposable preflight scripts, which are not package code.

## Layout

| Path | Contents |
|---|---|
| `src/grenslan/` | The `grenslan` package. Components are added as their work packages are implemented; there are no placeholder modules. |
| `tests/unit/` | Unit tests, grouped by package area. `contracts/test_adopted_contract_files.py` checks the integrity of the adopted contract files. |
| `tests/integration/` | Tests against a running HTTPS server (`ingress/` covers REST and MCP). |
| `tests/support/` | Shared, sanitized test fixtures (`minimal_requests.py`, `config_fixtures.py`, `tls_fixtures.py` for a throwaway CA and server certificate, `ingress_fixtures.py` for a running server with test credentials, `jwt_fixtures.py` for throwaway signing keys and access tokens), importable from any test. |
| `scripts/` | `check.sh` (all checks) and `sync-contracts.sh` (copies the adopted tool registry and provider configuration schema into the package). |
| `docs/contracts/` | Authoritative adopted contracts and schemas. Runtime code reads or derives from these. The one packaged copy, `src/grenslan/contracts/TOOL_SCHEMAS.json`, must stay byte-identical; a test fails if it diverges, and `scripts/sync-contracts.sh` refreshes it. |
| `docs/implementation/` | Validation record, dependency inventory, this file, and reproducible preflight scripts under `preflight/`. |

## Secrets and test material

Never commit real credentials, private keys, tokens or production data. Tests and preflight scripts generate throwaway certificates and keys in temporary directories and delete them afterwards. `.gitignore` excludes `.env` files and `/secrets/`.
