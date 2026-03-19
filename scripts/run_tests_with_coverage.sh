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

echo "[tests] Running full suite with coverage"
"${PYTHON_BIN}" -m pytest \
  --cov=api \
  --cov=coyote \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-report=html \
  tests

echo "[tests] Coverage HTML report: .coverage_html/index.html"
