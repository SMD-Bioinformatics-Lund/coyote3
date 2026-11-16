#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

reuse_coverage=0
if [[ "${1:-}" == "--from-existing" ]]; then
  reuse_coverage=1
  shift
fi
if [[ "$#" -ne 0 ]]; then
  echo "Usage: $0 [--from-existing]" >&2
  exit 2
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
  elif [[ -x "$ROOT_DIR/.venv/bin/python" ]]; then
    PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: Could not find a Python interpreter. Set PYTHON_BIN explicitly." >&2
    exit 1
  fi
fi

# Threshold strategy:
# - Family defaults protect distinct runtime boundaries.
# - The clinical query policy has a stricter 75% branch-aware threshold.
# - Set UNIFORM_MIN=60 (or another value) to enforce the same threshold for all families.
#   Example:
#     UNIFORM_MIN=60 PYTHONPATH=. bash scripts/quality/run_family_coverage_gates.sh
CORE_MIN="${CORE_MIN:-75}"
SERVICES_MIN="${SERVICES_MIN:-55}"
ROUTERS_MIN="${ROUTERS_MIN:-60}"
CLINICAL_QUERY_MIN="${CLINICAL_QUERY_MIN:-75}"
CLINICAL_RULES_MIN="${CLINICAL_RULES_MIN:-100}"
UNIFORM_MIN="${UNIFORM_MIN:-}"

if [[ -n "${UNIFORM_MIN}" ]]; then
  CORE_MIN="${UNIFORM_MIN}"
  SERVICES_MIN="${UNIFORM_MIN}"
  ROUTERS_MIN="${UNIFORM_MIN}"
  CLINICAL_QUERY_MIN="${UNIFORM_MIN}"
  CLINICAL_RULES_MIN="${UNIFORM_MIN}"
fi

run_family_gate() {
  local label="$1"
  local include="$2"
  local minimum="$3"

  echo "[coverage-gates] ${label} >= ${minimum}%"
  "${PYTHON_BIN}" -m coverage report \
    --include="${include}" \
    --show-missing \
    --fail-under="${minimum}"
}

if [[ "$reuse_coverage" -eq 1 && ! -f .coverage ]]; then
  echo "ERROR: --from-existing requires a .coverage database in the repository root." >&2
  exit 2
fi

if [[ "$reuse_coverage" -eq 0 ]]; then
  "${PYTHON_BIN}" -m pytest -q \
    --cov=coyote_api --cov=coyote --cov=coyote_mongo --cov=coyote_relay --cov=coyote_atlas --cov=coyote_demo \
    --cov-config=.coveragerc --cov-report=
  reuse_coverage=1
fi

run_family_gate "core/src/coyote/domain" "core/src/coyote/domain/*" "${CORE_MIN}"
run_family_gate "core/src/coyote/application" "core/src/coyote/application/*" "${SERVICES_MIN}"
run_family_gate "api/src/coyote_api/interfaces/http" "api/src/coyote_api/interfaces/http/*" "${ROUTERS_MIN}"
run_family_gate "clinical query policy" "core/src/coyote/domain/dna/varqueries.py,core/src/coyote/domain/dna/cnvqueries.py,core/src/coyote/domain/dna/translocqueries.py,core/src/coyote/domain/rna/fusion_query_builder.py" "${CLINICAL_QUERY_MIN}"
run_family_gate "clinical reporting rules" "core/src/coyote/application/reporting/clinical_rules/*" "${CLINICAL_RULES_MIN}"

echo "[coverage-gates] All family gates passed."
