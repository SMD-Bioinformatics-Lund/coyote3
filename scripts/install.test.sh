#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${ENV_FILE:-.coyote3_test_env}"
COMPOSE_FILE="deploy/compose/docker-compose.test.yml"

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "ERROR: ${ENV_FILE} not found. Create it from deploy/env/example.test.env" >&2
  exit 1
fi

./scripts/compose-with-version.sh --env-file "${ENV_FILE}" -f "${COMPOSE_FILE}" up -d --build

echo "Test stack is up."
