#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEMO_DIR="$SCRIPT_DIR/demo_pbit"
ZIP_OUT="$SCRIPT_DIR/demo_pbit.zip"

cd "$DEMO_DIR"
rm -f "$ZIP_OUT"
zip -r "$ZIP_OUT" pbit >/dev/null
echo "Created: $ZIP_OUT"
