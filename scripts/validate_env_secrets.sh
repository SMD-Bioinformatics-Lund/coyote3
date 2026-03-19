#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Validate env file has no placeholder secrets before deployment.

Usage:
  scripts/validate_env_secrets.sh --env-file <path>
EOF
}

ENV_FILE=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$ENV_FILE" ]]; then
  echo "ERROR: --env-file is required" >&2
  exit 2
fi
if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 2
fi

# Required keys that must not be empty or placeholders.
required=(
  SECRET_KEY
  COYOTE3_FERNET_KEY
  INTERNAL_API_TOKEN
  API_SESSION_SALT
  MONGO_URI
)

errors=0
for key in "${required[@]}"; do
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 || true)"
  if [[ -z "$line" ]]; then
    echo "[error] missing required key: $key"
    errors=1
    continue
  fi
  value="${line#*=}"
  value="${value#\"}"; value="${value%\"}"
  value="${value#\'}"; value="${value%\'}"
  if [[ -z "$value" ]]; then
    echo "[error] empty required key: $key"
    errors=1
    continue
  fi
  if [[ "$value" == *"CHANGE_ME"* ]]; then
    echo "[error] placeholder detected for $key"
    errors=1
  fi
done

# Optional Mongo credentials if using compose-managed Mongo.
for key in MONGO_ROOT_PASSWORD MONGO_APP_PASSWORD; do
  line="$(grep -E "^${key}=" "$ENV_FILE" | tail -n1 || true)"
  if [[ -n "$line" ]]; then
    value="${line#*=}"
    value="${value#\"}"; value="${value%\"}"
    value="${value#\'}"; value="${value%\'}"
    if [[ "$value" == *"CHANGE_ME"* ]]; then
      echo "[error] placeholder detected for $key"
      errors=1
    fi
  fi
done

if [[ "$errors" -ne 0 ]]; then
  echo "[fail] env validation failed for: $ENV_FILE"
  exit 1
fi

echo "[ok] env validation passed: $ENV_FILE"
