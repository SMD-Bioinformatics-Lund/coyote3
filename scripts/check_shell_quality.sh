#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

SHELLCHECK_BIN="${SHELLCHECK_BIN:-}"
if [[ -z "$SHELLCHECK_BIN" ]]; then
  if command -v shellcheck >/dev/null 2>&1; then
    SHELLCHECK_BIN="$(command -v shellcheck)"
  elif [[ -x "${ROOT_DIR}/.venv/bin/shellcheck" ]]; then
    SHELLCHECK_BIN="${ROOT_DIR}/.venv/bin/shellcheck"
  fi
fi

if [[ -z "$SHELLCHECK_BIN" ]]; then
  echo "ERROR: shellcheck is required for shell quality checks." >&2
  echo "Install shellcheck (apt/brew) or pip-install shellcheck-py in the project venv." >&2
  exit 2
fi

echo "[check] shellcheck on scripts"
"$SHELLCHECK_BIN" scripts/*.sh

echo "[ok] shell quality checks passed"
