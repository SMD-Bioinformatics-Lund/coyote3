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
  INTERNAL_API_TOKEN
  PASSWORD_TOKEN_SALT
  REDIS_PASSWORD
)

# The explicit app URI supersedes the shared legacy value. Auxiliary URIs may
# intentionally inherit it, but every supplied URI must be free of placeholders.
if grep -qE '^COYOTE3_MONGO_URI=.+$' "$ENV_FILE"; then
  required+=(COYOTE3_MONGO_URI)
else
  required+=(MONGO_URI)
fi
for key in IDENTITY_MONGO_URI KNOWLEDGEBASE_MONGO_URI BAM_MONGO_URI; do
  if grep -qE "^${key}=.+$" "$ENV_FILE"; then
    required+=("$key")
  fi
done

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
    if [[ "$key" == "IDENTITY_MONGO_URI" || "$key" == "KNOWLEDGEBASE_MONGO_URI" || "$key" == "BAM_MONGO_URI" ]]; then
      continue
    fi
    echo "[error] empty required key: $key"
    errors=1
    continue
  fi
  if [[ "$value" == *"CHANGE_ME"* ]]; then
    echo "[error] placeholder detected for $key"
    errors=1
  fi
  if [[ "$key" == "REDIS_PASSWORD" && ! "$value" =~ ^[a-fA-F0-9]{64,}$ ]]; then
    echo "[error] REDIS_PASSWORD must contain at least 64 hexadecimal characters"
    errors=1
  fi
done

# LDAP configuration is validated when LDAP login is attempted. This allows
# the API to start and local authentication to remain available while a center
# completes or repairs its LDAP settings. Supplied secrets must still never be
# placeholders.
line="$(grep -E '^LDAP_SECRET=' "$ENV_FILE" | tail -n1 || true)"
if [[ -n "$line" ]]; then
  value="${line#*=}"
  value="${value#\"}"; value="${value%\"}"
  value="${value#\'}"; value="${value%\'}"
  if [[ "$value" == *"CHANGE_ME"* ]]; then
    echo "[error] placeholder detected for LDAP_SECRET"
    errors=1
  fi
fi

if [[ "$errors" -ne 0 ]]; then
  echo "[fail] env validation failed for: $ENV_FILE"
  exit 1
fi

echo "[ok] env validation passed: $ENV_FILE"
