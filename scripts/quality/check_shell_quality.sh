#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
mapfile -d '' shell_scripts < <(rg --files --null --glob '*.sh' scripts)
"$SHELLCHECK_BIN" install.sh "${shell_scripts[@]}"

echo "[ok] shell quality checks passed"
