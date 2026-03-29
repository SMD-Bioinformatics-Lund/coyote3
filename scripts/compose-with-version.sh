#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(realpath "$0")"
APP_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"
VALIDATE_SCRIPT="$APP_DIR/scripts/validate_env_secrets.sh"

COYOTE3_VERSION="$(python3 "$APP_DIR/coyote/__version__.py")"
export COYOTE3_VERSION
echo "Using COYOTE3_VERSION=${COYOTE3_VERSION}"

DEFAULT_COMPOSE_FILE="$APP_DIR/deploy/compose/docker-compose.yml"
if docker compose version >/dev/null 2>&1; then
  COMPOSE_BIN=(docker compose)
else
  COMPOSE_BIN=(docker-compose)
fi

has_compose_file=0
env_file=""
is_deploy_action=0
for arg in "$@"; do
  if [[ "$arg" == "-f" || "$arg" == "--file" ]]; then
    has_compose_file=1
  fi
done

for ((i=1; i<=$#; i++)); do
  current="${!i}"
  if [[ "$current" == "--env-file" ]]; then
    next=$((i+1))
    env_file="${!next:-}"
  fi
  if [[ "$current" == "up" || "$current" == "start" ]]; then
    is_deploy_action=1
  fi
done

if [[ "$is_deploy_action" -eq 1 && -n "$env_file" ]]; then
  "$VALIDATE_SCRIPT" --env-file "$env_file"
fi

if [[ "$has_compose_file" -eq 1 ]]; then
  exec "${COMPOSE_BIN[@]}" "$@"
fi

exec "${COMPOSE_BIN[@]}" -f "$DEFAULT_COMPOSE_FILE" "$@"
