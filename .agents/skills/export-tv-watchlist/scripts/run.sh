#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUARDRAILS_SCRIPTS="$(cd "${SCRIPT_DIR}/../../evaluate-portfolio-guardrails/scripts" && pwd)"

if ! command -v python3 >/dev/null 2>&1; then
  echo "error: python3 is required but not found in PATH" >&2
  exit 1
fi

export PYTHONPATH="${GUARDRAILS_SCRIPTS}:${SCRIPT_DIR}:${PYTHONPATH:-}"
exec python3 "${SCRIPT_DIR}/export.py" "$@"
