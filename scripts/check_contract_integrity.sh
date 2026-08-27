#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif command -v python3.12 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3.12)"
  elif command -v python3 >/dev/null 2>&1; then
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
if rg -n "^[[:space:]]*print\\(" api \
  --glob '**/*.py' >/dev/null; then
  echo "ERROR: runtime code contains print() statements; use structured logging instead." >&2
  rg -n "^[[:space:]]*print\\(" api --glob '**/*.py' >&2
  exit 1
fi

echo "[check] forbid generic catch-all log messages"
if rg -n "An error occurred" api --glob '**/*.py' >/dev/null; then
  echo "ERROR: generic error log message found; include operation/collection context." >&2
  rg -n "An error occurred" api --glob '**/*.py' >&2
  exit 1
fi

echo "[check] forbid hardcoded user-home paths in runtime code"
if rg -n "/home/[A-Za-z0-9._-]+/" api \
  --glob '**/*.py' \
  --glob '!**/tests/**' >/dev/null; then
  echo "ERROR: hardcoded user-home path found in runtime code." >&2
  rg -n "/home/[A-Za-z0-9._-]+/" api \
    --glob '**/*.py' \
    --glob '!**/tests/**' >&2
  exit 1
fi

echo "[check] flag prohibited transitional markers in runtime code"
if rg -n "hidden bridging layer|fallback transitional helper" api --glob '**/*.py' >/dev/null; then
  echo "ERROR: transitional marker found in runtime code." >&2
  rg -n "hidden bridging layer|fallback transitional helper" api --glob '**/*.py' >&2
  exit 1
fi

echo "[check] validate seed bundle contract and assay consistency"
seed_check_args=(
  --seed-file demo_data/collections/all_collections_dummy
  --reference-seed-data api/config/bootstrap/rbac
  --reference-seed-data api/config/bootstrap/reference
)
"$PYTHON_BIN" scripts/validate_assay_consistency.py "${seed_check_args[@]}"

echo "[check] dependency exports match pyproject.toml"
"$PYTHON_BIN" scripts/check_dependency_consistency.py

echo "[check] shell script static analysis"
bash scripts/check_shell_quality.sh

echo "[check] docs internal links"
"$PYTHON_BIN" scripts/check_markdown_links.py

echo "[check] regenerate collection contracts doc"
preexisting_doc_changes=0
if command -v git >/dev/null 2>&1; then
  if ! git diff --quiet -- docs/api/collection_contracts.md || \
     ! git diff --cached --quiet -- docs/api/collection_contracts.md; then
    preexisting_doc_changes=1
  fi
fi
"$PYTHON_BIN" scripts/export_collection_contracts_doc.py

if command -v git >/dev/null 2>&1; then
  if [[ "$preexisting_doc_changes" -eq 1 ]]; then
    echo "[warn] docs/api/collection_contracts.md had preexisting local changes; skip clean-tree diff check."
  else
    echo "[check] collection contract doc is committed"
    if ! git diff --quiet -- docs/api/collection_contracts.md; then
      echo "ERROR: docs/api/collection_contracts.md changed. Commit regenerated contracts." >&2
      git --no-pager diff -- docs/api/collection_contracts.md >&2 || true
      exit 1
    fi
  fi
fi

echo "[check] regenerate system permission catalog"
preexisting_permission_doc_changes=0
if command -v git >/dev/null 2>&1; then
  if ! git diff --quiet -- docs/developer/permission_catalog.md || \
     ! git diff --cached --quiet -- docs/developer/permission_catalog.md; then
    preexisting_permission_doc_changes=1
  fi
fi
"$PYTHON_BIN" scripts/export_permissions_reference.py

if command -v git >/dev/null 2>&1; then
  if [[ "$preexisting_permission_doc_changes" -eq 1 ]]; then
    echo "[warn] docs/developer/permission_catalog.md had preexisting local changes; skip clean-tree diff check."
  else
    echo "[check] system permission catalog is committed"
    if ! git diff --quiet -- docs/developer/permission_catalog.md; then
      echo "ERROR: docs/developer/permission_catalog.md changed. Commit the regenerated catalog." >&2
      git --no-pager diff -- docs/developer/permission_catalog.md >&2 || true
      exit 1
    fi
  fi
fi

echo "[ok] contract integrity checks passed"
