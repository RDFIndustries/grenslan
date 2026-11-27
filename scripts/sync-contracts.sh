#!/usr/bin/env bash
# Copy the adopted canonical tool registry into the package. docs/contracts/
# is authoritative; tests/unit/contracts/test_registry.py fails if the
# packaged copy differs byte for byte.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cp "$ROOT/docs/contracts/TOOL_SCHEMAS.json" "$ROOT/src/grenslan/contracts/TOOL_SCHEMAS.json"
