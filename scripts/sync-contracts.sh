#!/usr/bin/env bash
# Copy the adopted canonical schemas into the package. docs/contracts/ is
# authoritative; tests fail if a packaged copy differs byte for byte.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
cp "$ROOT/docs/contracts/TOOL_SCHEMAS.json" "$ROOT/src/grenslan/contracts/TOOL_SCHEMAS.json"
cp "$ROOT/docs/contracts/PROVIDER_CONFIG_SCHEMA.json" "$ROOT/src/grenslan/config/PROVIDER_CONFIG_SCHEMA.json"
