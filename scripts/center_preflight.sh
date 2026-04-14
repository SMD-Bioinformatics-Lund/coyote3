#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Validate a center deployment setup before first run.

Usage:
  scripts/center_preflight.sh --env-file <path> --compose-file <path> [--seed-file <path>] [--yaml-file <path>] [--reference-seed-data <path>]

Example:
  scripts/center_preflight.sh \
    --env-file .coyote3_stage_env \
    --compose-file deploy/compose/docker-compose.stage.yml
USAGE
}

ENV_FILE=""
COMPOSE_FILE=""
SEED_FILE=""
YAML_FILE=""
REFERENCE_SEED_DATA=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --seed-file) SEED_FILE="$2"; shift 2 ;;
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    --reference-seed-data) REFERENCE_SEED_DATA="$2"; shift 2 ;;
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
for key in COYOTE3_DB MONGO_URI CACHE_REDIS_URL SECRET_KEY INTERNAL_API_TOKEN LDAP_SECRET CORS_ORIGINS; do
  if ! grep -qE "^${key}=" "$ENV_FILE"; then
    echo "ERROR: missing key in env file: $key" >&2
    exit 1
  fi
done

echo "[check] mongo URI consistency"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
    exit 2
  fi
fi

echo "[check] python version"
echo "Using Python: $PYTHON_BIN"
"$PYTHON_BIN" --version
echo "Env file: $ENV_FILE"
if ! "$PYTHON_BIN" --version >/dev/null 2>&1; then
  echo "ERROR: Python interpreter is not runnable: $PYTHON_BIN" >&2
  exit 2
fi

"$PYTHON_BIN" -c '
import sys
from urllib.parse import parse_qs, unquote, urlparse

env_file = sys.argv[1]
data = {}
with open(env_file, "r", encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip("'"'"'\"")

db = data.get("COYOTE3_DB", "")
uri = data.get("MONGO_URI", "")
app_user = data.get("MONGO_APP_USER", "")
app_password = data.get("MONGO_APP_PASSWORD", "")
if not db or not uri:
    raise SystemExit("ERROR: COYOTE3_DB and MONGO_URI must be set")

parsed = urlparse(uri)
uri_db = parsed.path.lstrip("/")
if uri_db and uri_db != db:
    raise SystemExit(f"ERROR: MONGO_URI db '"'"'{uri_db}'"'"' does not match COYOTE3_DB '"'"'{db}'"'"'.")

qs = parse_qs(parsed.query)
auth_source = (qs.get("authSource") or [""])[0]
if auth_source and auth_source != db:
    raise SystemExit(f"ERROR: MONGO_URI authSource '"'"'{auth_source}'"'"' does not match COYOTE3_DB '"'"'{db}'"'"'.")

if app_user and parsed.username and unquote(parsed.username) != app_user:
    raise SystemExit(f"ERROR: MONGO_URI username '"'"'{unquote(parsed.username)}'"'"' does not match MONGO_APP_USER '"'"'{app_user}'"'"'.")

if app_password and parsed.password and unquote(parsed.password) != app_password:
    raise SystemExit("ERROR: MONGO_URI password does not match MONGO_APP_PASSWORD. If password has special chars, URL-encode it in MONGO_URI.")
' "$ENV_FILE"

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

if [[ -n "$SEED_FILE" ]]; then
  if [[ ! -e "$SEED_FILE" ]]; then
    echo "ERROR: seed source not found: $SEED_FILE" >&2
    exit 2
  fi
  echo "[check] seed dependency and assay consistency"
  PYTHON_BIN="${PYTHON_BIN:-}"
  if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python)"
    else
      echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
      exit 2
    fi
  fi
  cmd=("$PYTHON_BIN" scripts/validate_assay_consistency.py --seed-file "$SEED_FILE")
  if [[ -n "$REFERENCE_SEED_DATA" ]]; then
    if [[ ! -d "$REFERENCE_SEED_DATA" ]]; then
      echo "ERROR: reference seed data source not found: $REFERENCE_SEED_DATA" >&2
      exit 2
    fi
    cmd+=(--reference-seed-data "$REFERENCE_SEED_DATA")
  fi
  if [[ -n "$YAML_FILE" ]]; then
    if [[ ! -f "$YAML_FILE" ]]; then
      echo "ERROR: yaml file not found: $YAML_FILE" >&2
      exit 2
    fi
    cmd+=(--yaml "$YAML_FILE")
  fi
  "${cmd[@]}"
fi

echo "[ok] preflight passed"
