#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v shellcheck >/dev/null 2>&1; then
  echo "ERROR: shellcheck is required for shell quality checks." >&2
  echo "Install shellcheck and re-run." >&2
  exit 2
fi

echo "[check] shellcheck on scripts"
shellcheck scripts/*.sh

echo "[ok] shell quality checks passed"
