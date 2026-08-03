#!/usr/bin/env bash
set -euo pipefail

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
#     UNIFORM_MIN=60 PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
CORE_MIN="${CORE_MIN:-75}"
SERVICES_MIN="${SERVICES_MIN:-55}"
ROUTERS_MIN="${ROUTERS_MIN:-60}"
CLINICAL_QUERY_MIN="${CLINICAL_QUERY_MIN:-75}"
UNIFORM_MIN="${UNIFORM_MIN:-}"

if [[ -n "${UNIFORM_MIN}" ]]; then
  CORE_MIN="${UNIFORM_MIN}"
  SERVICES_MIN="${UNIFORM_MIN}"
  ROUTERS_MIN="${UNIFORM_MIN}"
  CLINICAL_QUERY_MIN="${UNIFORM_MIN}"
fi

run_family_gate() {
  local label="$1"
  local include="$2"
  local minimum="$3"
  shift 3

  echo "[coverage-gates] ${label} >= ${minimum}%"
  if [[ "$reuse_coverage" -eq 0 ]]; then
    "${PYTHON_BIN}" -m pytest -q "$@" \
      --cov=api \
      --cov-config=.coveragerc \
      --cov-report=
  fi
  "${PYTHON_BIN}" -m coverage report \
    --include="${include}" \
    --show-missing \
    --fail-under="${minimum}"
}

if [[ "$reuse_coverage" -eq 1 && ! -f .coverage ]]; then
  echo "ERROR: --from-existing requires a .coverage database in the repository root." >&2
  exit 2
fi

run_family_gate "api/domain/core" "api/domain/core/*" "${CORE_MIN}" \
  tests/unit tests/api tests/integration
run_family_gate "api/application" "api/application/*" "${SERVICES_MIN}" \
  tests/unit tests/api
run_family_gate "api/interfaces/http" "api/interfaces/http/*" "${ROUTERS_MIN}" \
  tests/api tests/integration
run_family_gate "clinical query policy" "api/domain/core/dna/varqueries.py,api/domain/core/dna/cnvqueries.py,api/domain/core/dna/translocqueries.py,api/domain/core/rna/fusion_query_builder.py" "${CLINICAL_QUERY_MIN}" \
  tests/unit/test_dna_varqueries.py \
  tests/unit/test_query_strategy_builders.py \
  tests/unit/test_dna_structural_service.py \
  tests/unit/workflows/test_workflow_services.py

echo "[coverage-gates] All family gates passed."
