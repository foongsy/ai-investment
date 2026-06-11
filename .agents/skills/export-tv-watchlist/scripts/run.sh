#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../../.." && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but not found in PATH" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "error: curl is required but not found in PATH" >&2
  exit 1
fi

if ! command -v jq >/dev/null 2>&1; then
  echo "error: jq is required but not found in PATH" >&2
  exit 1
fi

if [[ "${1:-}" != "--no-fastio" && "${*}" != *"--no-fastio"* ]]; then
  if ! command -v fastio >/dev/null 2>&1; then
    FASTIO_LOCAL="${REPO_ROOT}/node_modules/.bin/fastio"
    if [[ ! -x "${FASTIO_LOCAL}" ]]; then
      if ! command -v npm >/dev/null 2>&1; then
        echo "error: fastio CLI not found; install with npm install -g @vividengine/fastio-cli or use --no-fastio" >&2
        exit 1
      fi
      echo "Installing local fastio CLI..." >&2
      (cd "${REPO_ROOT}" && npm install --no-save @vividengine/fastio-cli)
    fi
  fi
fi

exec python3 "${SCRIPT_DIR}/export.py" "$@"
