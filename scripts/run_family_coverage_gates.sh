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

# Baseline thresholds; ratchet upward as coverage improves.
CORE_MIN="${CORE_MIN:-30}"
SERVICES_MIN="${SERVICES_MIN:-55}"
ROUTERS_MIN="${ROUTERS_MIN:-60}"
BLUEPRINTS_MIN="${BLUEPRINTS_MIN:-52}"

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
