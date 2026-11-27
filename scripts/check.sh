#!/usr/bin/env bash
# Run every repository check: lock consistency, lint, formatting, strict
# typing and the test suite. Exits non-zero on the first failure.
set -euo pipefail
cd "$(dirname "$0")/.."
uv sync --locked
uv run --locked ruff check
uv run --locked ruff format --check
uv run --locked mypy
uv run --locked pytest "$@"
