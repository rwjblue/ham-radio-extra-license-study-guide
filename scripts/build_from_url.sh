#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: $0 <source-url> [mode] [out-dir]"
  exit 1
fi

SOURCE_URL="$1"
MODE="${2:-literal}"
OUT_DIR="${3:-dist}"

uv run extra-facts build --source-url "$SOURCE_URL" --mode "$MODE" --out-dir "$OUT_DIR" --cache .cache
