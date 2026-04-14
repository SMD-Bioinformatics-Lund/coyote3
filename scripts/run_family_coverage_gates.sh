#!/usr/bin/env bash
set -euo pipefail

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
# - Current defaults preserve existing CI behavior.
# - Set UNIFORM_MIN=60 (or another value) to enforce the same threshold for all families.
#   Example:
#     UNIFORM_MIN=60 PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
CORE_MIN="${CORE_MIN:-30}"
SERVICES_MIN="${SERVICES_MIN:-55}"
ROUTERS_MIN="${ROUTERS_MIN:-60}"
BLUEPRINTS_MIN="${BLUEPRINTS_MIN:-52}"
UNIFORM_MIN="${UNIFORM_MIN:-}"

if [[ -n "${UNIFORM_MIN}" ]]; then
  CORE_MIN="${UNIFORM_MIN}"
  SERVICES_MIN="${UNIFORM_MIN}"
  ROUTERS_MIN="${UNIFORM_MIN}"
  BLUEPRINTS_MIN="${UNIFORM_MIN}"
fi

echo "[coverage-gates] api/core >= ${CORE_MIN}%"
"${PYTHON_BIN}" -m pytest -q tests/unit tests/api tests/integration \
  --cov=api.core \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-fail-under="${CORE_MIN}"

echo "[coverage-gates] api/services >= ${SERVICES_MIN}%"
"${PYTHON_BIN}" -m pytest -q tests/unit tests/api \
  --cov=api.services \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-fail-under="${SERVICES_MIN}"

echo "[coverage-gates] api/routers >= ${ROUTERS_MIN}%"
"${PYTHON_BIN}" -m pytest -q tests/api tests/integration \
  --cov=api.routers \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-fail-under="${ROUTERS_MIN}"

echo "[coverage-gates] coyote/blueprints >= ${BLUEPRINTS_MIN}%"
"${PYTHON_BIN}" -m pytest -q tests/ui tests/integration \
  --cov=coyote.blueprints \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-fail-under="${BLUEPRINTS_MIN}"

echo "[coverage-gates] All family gates passed."
