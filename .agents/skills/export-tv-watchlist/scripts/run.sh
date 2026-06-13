#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT"

if [[ -x "$ROOT/node_modules/.bin/fastio" ]]; then
  export FASTIO_BIN="$ROOT/node_modules/.bin/fastio"
elif command -v fastio >/dev/null 2>&1; then
  export FASTIO_BIN="fastio"
fi

exec python3 "$ROOT/.agents/skills/export-tv-watchlist/scripts/export.py" "$@"
