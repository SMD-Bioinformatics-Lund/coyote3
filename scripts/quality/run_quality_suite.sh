#!/usr/bin/env bash
# SPDX-FileCopyrightText: 2026 Ram Nanduri
# SPDX-License-Identifier: GPL-3.0-only

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-${VIRTUAL_ENV:+$VIRTUAL_ENV/bin/python}}"
if [[ -z "${PYTHON_BIN:-}" && -x "$ROOT_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
fi
if [[ -z "${PYTHON_BIN:-}" || ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3 || command -v python)"
fi

if [[ -z "${PYTHON_BIN:-}" ]]; then
  echo "ERROR: Python interpreter not found. Set PYTHON_BIN." >&2
  exit 2
fi

# Child checks may change directories; preserve a caller's relative interpreter
# selection as the same virtual environment throughout the suite.
PYTHON_BIN="$("$PYTHON_BIN" -c 'import sys; print(sys.executable)')"

echo "[quality] Backend tests"
PYTHONPATH=. "$PYTHON_BIN" -m pytest -q core/tests tests/unit tests/integration tests/smoke adapters/mongo/tests api/tests services/atlas/tests services/demo/tests \
  --cov=coyote_api --cov=coyote --cov=coyote_mongo --cov=coyote_atlas --cov=coyote_demo \
  --cov-config=.coveragerc \
  --cov-report=term-missing \
  --cov-report=xml:coverage.xml

echo "[quality] Backend coverage gates"
PYTHON_BIN="$PYTHON_BIN" PYTHONPATH=. \
  bash scripts/quality/run_family_coverage_gates.sh --from-existing

echo "[quality] Strict Python type boundary"
PYTHONPATH=. "$PYTHON_BIN" -m mypy

echo "[quality] Independent package coverage gates"
PYTHON_BIN="$PYTHON_BIN" bash scripts/quality/run_package_tests.sh all --coverage

echo "[quality] Contract and repository checks"
PYTHON_BIN="$PYTHON_BIN" bash scripts/quality/check_contract_integrity.sh

echo "[quality] Frontend lint and build"
npm --prefix frontend run lint
npm --prefix frontend run test:coverage
PYTHON_BIN="$PYTHON_BIN" npm --prefix frontend run build:verified

echo "[quality] Documentation lint"
npm run docs:lint

echo "[quality] Strict documentation build"
"$PYTHON_BIN" -m mkdocs build --strict --site-dir "$ROOT_DIR/site"
"$PYTHON_BIN" scripts/docs/check_built_site.py "$ROOT_DIR/site"

echo "[quality] Frontend browser tests"
npm --prefix frontend run test:e2e

if [[ -n "${COMPOSE_FILES:-${COMPOSE_FILE:-}}" ]]; then
  read -r -a compose_files <<< "${COMPOSE_FILES:-${COMPOSE_FILE}}"
  compose_args=()
  for compose_file in "${compose_files[@]}"; do
    compose_args+=("-f" "$compose_file")
  done
  echo "[quality] Compose configuration: ${compose_files[*]}"
  docker compose --env-file "${COMPOSE_ENV_FILE:-deploy/env/example.env}" "${compose_args[@]}" config --quiet
fi

echo "[quality] All checks passed"
