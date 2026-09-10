#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(realpath "$0")"
APP_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"
VALIDATE_SCRIPT="$APP_DIR/scripts/validate_env_secrets.sh"

COYOTE3_VERSION="$(python3 "$APP_DIR/api/version.py")"
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
compose_args=()
for arg in "$@"; do
  compose_args+=("$arg")
  if [[ "$arg" == "-f" || "$arg" == "--file" ]]; then
    has_compose_file=1
  fi
done

set -- "${compose_args[@]}"

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
  if [[ "$current" == --env-file=* ]]; then
    env_file="${current#--env-file=}"
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

deployment_environment="$(python3 - "${env_file:-.env}" <<'PY'
import os
import pathlib
import re
import shlex
import sys

settings = {}
env_path = pathlib.Path(sys.argv[1])
if env_path.exists():
    for line in env_path.read_text().splitlines():
        if not re.match(r"^\s*(?:export\s+)?(?:ENV_NAME|LOG_LEVEL|CELERY_LOG_LEVEL)\s*=", line):
            continue
        tokens = shlex.split(line, comments=True)
        if tokens and tokens[0] == "export":
            tokens = tokens[1:]
        key, separator, candidate = " ".join(tokens).partition("=")
        settings[key.strip()] = candidate.strip()
for key in ("ENV_NAME", "LOG_LEVEL", "CELERY_LOG_LEVEL"):
    if key in os.environ:
        settings[key] = os.environ[key]
value = settings.get("ENV_NAME")
value = (value or "production").strip().lower()
value = {"development": "dev", "production": "prod", "testing": "test", "staging": "stage"}.get(value, value)
if value not in {"dev", "prod", "test", "stage"}:
    sys.exit("ENV_NAME must be development/dev, production/prod, testing/test, or staging/stage")
print(value)
level = settings.get("LOG_LEVEL") or ("INFO" if value == "prod" else "DEBUG")
celery_level = settings.get("CELERY_LOG_LEVEL") or level
for selected in (level, celery_level):
    selected = selected.upper()
    if selected not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL", "FATAL", "WARN"}:
        sys.exit("LOG_LEVEL and CELERY_LOG_LEVEL must be literal logging level names")
    print(selected)
PY
)"
readarray -t deployment_settings <<< "$deployment_environment"
export COYOTE3_IMAGE_TAG="${COYOTE3_VERSION}-${deployment_settings[0]}"
if [[ "${deployment_settings[0]}" == "prod" ]]; then
  export COYOTE3_IMAGE_TAG="$COYOTE3_VERSION"
fi
export LOG_LEVEL="${deployment_settings[1]}"
export CELERY_LOG_LEVEL="${deployment_settings[2]}"
echo "Using COYOTE3_IMAGE_TAG=${COYOTE3_IMAGE_TAG}"

if [[ "$is_deploy_action" -eq 1 && -n "$env_file" ]]; then
  bash "$VALIDATE_SCRIPT" --env-file "$env_file"
fi

if [[ -z "$compose_file" ]]; then
  compose_file="$DEFAULT_COMPOSE_FILE"
fi
if [[ "$compose_file" != /* ]]; then
  compose_file="$APP_DIR/$compose_file"
fi

if [[ "$is_down_action" -eq 1 && "$has_remove_volumes" -eq 1 ]]; then
  echo "ERROR: refusing 'down -v/--volumes': Coyote3 deployment data is never removed by this wrapper." >&2
  echo "Use 'down' without volume removal. Host-mounted MongoDB data is retained independently." >&2
  exit 2
fi

if [[ "$has_compose_file" -eq 1 ]]; then
  exec "${COMPOSE_BIN[@]}" "$@"
fi

exec "${COMPOSE_BIN[@]}" -f "$DEFAULT_COMPOSE_FILE" "$@"
