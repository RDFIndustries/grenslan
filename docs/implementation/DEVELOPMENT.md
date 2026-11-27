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

These are the same commands the CI workflow (`.github/workflows/ci.yml`) runs:

```shell
uv run --locked ruff check
uv run --locked ruff format --check
uv run --locked mypy
uv run --locked pytest
```

Ruff and mypy cover `src/` and `tests/`. `docs/` is excluded from linting because it holds the adopted declaration file `docs/contracts/PROVIDER_INTERFACES.py` and disposable preflight scripts, which are not package code.

## Layout

| Path | Contents |
|---|---|
| `src/grenslan/` | The `grenslan` package. Components are added as their work packages are implemented; there are no placeholder modules. |
| `tests/unit/` | Unit tests. `test_contract_registry.py` checks the integrity of the adopted contract files. |
| `docs/contracts/` | Authoritative adopted contracts and schemas. Runtime code reads or derives from these; it does not keep divergent copies. |
| `docs/implementation/` | Validation record, dependency inventory, this file, and reproducible preflight scripts under `preflight/`. |

## Secrets and test material

Never commit real credentials, private keys, tokens or production data. Tests and preflight scripts generate throwaway certificates and keys in temporary directories and delete them afterwards. `.gitignore` excludes `.env` files and `/secrets/`.
