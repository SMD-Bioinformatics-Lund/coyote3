#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON_BIN:-/home/ram/.virtualenvs/coyote3/bin/python}"

echo "[tests] Running full suite with coverage"
"${PYTHON_BIN}" -m pytest \
  --cov=api \
  --cov=coyote \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-report=html \
  tests

echo "[tests] Coverage HTML report: .coverage_html/index.html"
