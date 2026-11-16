#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

# Run a package from its own directory so pytest and coverage use its configuration.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
selection="${1:-all}"
mode="${2:-}"
if [[ "$#" -gt 2 || ! "$selection" =~ ^(all|core|api|mongo|client)$ ||
      ! "$mode" =~ ^(--smoke|--coverage)?$ ]]; then
  echo "Usage: $0 [all|core|api|mongo|client] [--smoke|--coverage]" >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}}"
if [[ -z "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi
PYTHON_BIN="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"

if [[ "$selection" == all ]]; then
  projects=(core api mongo client)
else
  projects=("$selection")
fi

for project in "${projects[@]}"; do
  case "$project" in
    core) directory=core ;;
    api) directory=api ;;
    mongo) directory=adapters/mongo ;;
    client) directory=clients/python ;;
  esac
  arguments=(-q)
  case "$mode" in
    --smoke) arguments+=(tests/smoke) ;;
    --coverage)
      arguments+=(--cov --cov-config=pyproject.toml --cov-report=term-missing --cov-report=xml)
      ;;
  esac
  echo "[package-tests] $project ${mode:-full suite}"
  (
    cd "$ROOT_DIR/$directory"
    "$PYTHON_BIN" -m pytest "${arguments[@]}"
  )
done
