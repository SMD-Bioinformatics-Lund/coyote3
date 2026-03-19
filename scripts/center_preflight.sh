#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Validate a center deployment setup before first run.

Usage:
  scripts/center_preflight.sh --env-file <path> --compose-file <path>

Example:
  scripts/center_preflight.sh \
    --env-file .coyote3_stage_env \
    --compose-file deploy/compose/docker-compose.stage.yml
USAGE
}

ENV_FILE=""
COMPOSE_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$ENV_FILE" || -z "$COMPOSE_FILE" ]]; then
  echo "ERROR: --env-file and --compose-file are required" >&2
  usage
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 2
fi

if [[ ! -f "$COMPOSE_FILE" ]]; then
  echo "ERROR: compose file not found: $COMPOSE_FILE" >&2
  exit 2
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed" >&2
  exit 2
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available" >&2
  exit 2
fi

echo "[check] validating secrets in env file"
bash scripts/validate_env_secrets.sh --env-file "$ENV_FILE"

echo "[check] validating compose render"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config -q

echo "[check] mandatory keys"
for key in COYOTE3_DB MONGO_URI CACHE_REDIS_URL SECRET_KEY INTERNAL_API_TOKEN COYOTE3_FERNET_KEY; do
  if ! grep -qE "^${key}=" "$ENV_FILE"; then
    echo "ERROR: missing key in env file: $key" >&2
    exit 1
  fi
done

echo "[check] endpoint ports"
for key in COYOTE3_WEB_PORT COYOTE3_API_PORT COYOTE3_STAGE_WEB_PORT COYOTE3_STAGE_API_PORT COYOTE3_DEV_WEB_PORT COYOTE3_DEV_API_PORT; do
  if grep -qE "^${key}=" "$ENV_FILE"; then
    val="$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 | cut -d'=' -f2- | tr -d "'\"")"
    if [[ -n "$val" && ! "$val" =~ ^[0-9]+$ ]]; then
      echo "ERROR: ${key} must be numeric, got: ${val}" >&2
      exit 1
    fi
  fi
done

echo "[ok] preflight passed"
