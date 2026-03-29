#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
    exit 2
  fi
fi

echo "[check] forbid deprecated db_documents imports"
if rg -n "api\\.contracts\\.db_documents|from api\\.contracts import db_documents" api scripts tests >/dev/null; then
  echo "ERROR: deprecated db_documents import path found." >&2
  rg -n "api\\.contracts\\.db_documents|from api\\.contracts import db_documents" api scripts tests >&2
  exit 1
fi

echo "[check] forbid stdout debug prints in runtime code"
if rg -n "^[[:space:]]*print\\(" api coyote \
  --glob '**/*.py' \
  --glob '!coyote/static/vendor/**' \
  --glob '!coyote/__version__.py' >/dev/null; then
  echo "ERROR: runtime code contains print() statements; use structured logging instead." >&2
  rg -n "^[[:space:]]*print\\(" api coyote \
    --glob '**/*.py' \
    --glob '!coyote/static/vendor/**' \
    --glob '!coyote/__version__.py' >&2
  exit 1
fi

echo "[check] forbid generic catch-all log messages"
if rg -n "An error occurred" api coyote \
  --glob '**/*.py' \
  --glob '!coyote/static/**' \
  --glob '!coyote/templates/**' >/dev/null; then
  echo "ERROR: generic error log message found; include operation/collection context." >&2
  rg -n "An error occurred" api coyote \
    --glob '**/*.py' \
    --glob '!coyote/static/**' \
    --glob '!coyote/templates/**' >&2
  exit 1
fi

echo "[check] forbid hardcoded user-home paths in runtime code"
if rg -n "/home/[A-Za-z0-9._-]+/" api coyote \
  --glob '**/*.py' \
  --glob '!**/tests/**' >/dev/null; then
  echo "ERROR: hardcoded user-home path found in runtime code." >&2
  rg -n "/home/[A-Za-z0-9._-]+/" api coyote \
    --glob '**/*.py' \
    --glob '!**/tests/**' >&2
  exit 1
fi

echo "[check] flag compatibility-shim markers in runtime code"
if rg -n "compatibility shim|compat shim|legacy fallback shim" api coyote \
  --glob '**/*.py' \
  --glob '!coyote/static/**' \
  --glob '!coyote/templates/**' >/dev/null; then
  echo "ERROR: compatibility shim marker found in runtime code." >&2
  rg -n "compatibility shim|compat shim|legacy fallback shim" api coyote \
    --glob '**/*.py' \
    --glob '!coyote/static/**' \
    --glob '!coyote/templates/**' >&2
  exit 1
fi

echo "[check] validate seed bundle contract and assay consistency"
seed_check_args=(
  --seed-file tests/fixtures/db_dummy/all_collections_dummy
)
if [[ -d tests/data/seed_data ]]; then
  seed_check_args+=(--reference-seed-data tests/data/seed_data)
fi
"$PYTHON_BIN" scripts/validate_assay_consistency.py "${seed_check_args[@]}"

echo "[check] shell script static analysis"
bash scripts/check_shell_quality.sh

echo "[check] docs internal links"
"$PYTHON_BIN" scripts/check_markdown_links.py

echo "[check] regenerate collection contracts doc"
preexisting_doc_changes=0
if command -v git >/dev/null 2>&1; then
  if ! git diff --quiet -- docs/api/collection-contracts.md || \
     ! git diff --cached --quiet -- docs/api/collection-contracts.md; then
    preexisting_doc_changes=1
  fi
fi
"$PYTHON_BIN" scripts/export_collection_contracts_doc.py

if command -v git >/dev/null 2>&1; then
  if [[ "$preexisting_doc_changes" -eq 1 ]]; then
    echo "[warn] docs/api/collection-contracts.md had preexisting local changes; skip clean-tree diff check."
  else
    echo "[check] collection contract doc is committed"
    if ! git diff --quiet -- docs/api/collection-contracts.md; then
      echo "ERROR: docs/api/collection-contracts.md changed. Commit regenerated contracts." >&2
      git --no-pager diff -- docs/api/collection-contracts.md >&2 || true
      exit 1
    fi
  fi
fi

echo "[ok] contract integrity checks passed"
