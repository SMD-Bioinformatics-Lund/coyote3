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
compose_file=""
is_down_action=0
has_remove_volumes=0
for arg in "$@"; do
  if [[ "$arg" == "-f" || "$arg" == "--file" ]]; then
    has_compose_file=1
  fi
done

for ((i=1; i<=$#; i++)); do
  current="${!i}"
  if [[ "$current" == "-f" || "$current" == "--file" ]]; then
    next=$((i+1))
    compose_file="${!next:-}"
  fi
  if [[ "$current" == "--env-file" ]]; then
    next=$((i+1))
    env_file="${!next:-}"
  fi
  if [[ "$current" == "up" || "$current" == "start" ]]; then
    is_deploy_action=1
  fi
  if [[ "$current" == "down" ]]; then
    is_down_action=1
  fi
  if [[ "$current" == "-v" || "$current" == "--volumes" ]]; then
    has_remove_volumes=1
  fi
done

if [[ "$is_deploy_action" -eq 1 && -n "$env_file" ]]; then
  "$VALIDATE_SCRIPT" --env-file "$env_file"
fi

if [[ -z "$compose_file" ]]; then
  compose_file="$DEFAULT_COMPOSE_FILE"
fi
if [[ "$compose_file" != /* ]]; then
  compose_file="$APP_DIR/$compose_file"
fi
PROD_COMPOSE_FILE="$APP_DIR/deploy/compose/docker-compose.yml"
if [[ "$is_down_action" -eq 1 && "$has_remove_volumes" -eq 1 && "$compose_file" == "$PROD_COMPOSE_FILE" ]]; then
  if [[ "${COYOTE3_ALLOW_PROD_VOLUME_PRUNE:-0}" != "1" ]]; then
    echo "ERROR: refusing 'down -v/--volumes' for production compose without explicit override." >&2
    echo "Set COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1 only when intentional." >&2
    exit 2
  fi
fi

if [[ "$has_compose_file" -eq 1 ]]; then
  exec "${COMPOSE_BIN[@]}" "$@"
fi

exec "${COMPOSE_BIN[@]}" -f "$DEFAULT_COMPOSE_FILE" "$@"
