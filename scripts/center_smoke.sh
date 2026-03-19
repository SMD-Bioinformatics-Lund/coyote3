#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Run an end-to-end center smoke check against a running Coyote3 API.

Usage:
  scripts/center_smoke.sh \
    --api-base-url <url> \
    (--bearer-token <token> | --username <user> --password <pass>) \
    --yaml-file <path>

Example:
  scripts/center_smoke.sh \
    --api-base-url http://localhost:6816 \
    --username "admin@your-center.org" \
    --password "CHANGE_ME" \
    --yaml-file tests/data/ingest_demo/generic_case_control.yaml
USAGE
}

API_BASE_URL=""
BEARER_TOKEN=""
USERNAME=""
PASSWORD=""
YAML_FILE=""
PYTHON_BIN="${PYTHON_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$API_BASE_URL" || -z "$YAML_FILE" ]]; then
  echo "ERROR: --api-base-url and --yaml-file are required" >&2
  usage
  exit 2
fi

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
    exit 2
  fi
fi

if [[ -z "$BEARER_TOKEN" ]]; then
  if [[ -z "$USERNAME" || -z "$PASSWORD" ]]; then
    echo "ERROR: provide either --bearer-token or --username/--password" >&2
    usage
    exit 2
  fi
  echo "[step] login and resolve bearer token"
  AUTH_JSON="$(PYTHONPATH=. "$PYTHON_BIN" scripts/api_login.py \
    --base-url "$API_BASE_URL" \
    --mode password \
    --username "$USERNAME" \
    --password "$PASSWORD" \
    --print-token)"
  BEARER_TOKEN="$("$PYTHON_BIN" - <<'PY' "$AUTH_JSON"
import json
import sys
print(json.loads(sys.argv[1]).get("session_token", ""))
PY
  )"
fi

if [[ -z "$BEARER_TOKEN" ]]; then
  echo "ERROR: could not resolve bearer token" >&2
  exit 1
fi

if [[ ! -f "$YAML_FILE" ]]; then
  echo "ERROR: yaml file not found: $YAML_FILE" >&2
  exit 2
fi

echo "[step] health check"
curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null

echo "[step] local ingest spec validation"
"$PYTHON_BIN" scripts/validate_ingest_spec.py --yaml "$YAML_FILE" --check-files >/dev/null

echo "[step] submit ingest sample-bundle"
PY_PAYLOAD="$({
"$PYTHON_BIN" - <<'PY' "$YAML_FILE"
import json
import sys
from pathlib import Path
import yaml
p = Path(sys.argv[1])
y = yaml.safe_load(p.read_text(encoding='utf-8'))
print(json.dumps({"yaml_content": p.read_text(encoding='utf-8'), "update_existing": False}))
PY
})"

RESP_FILE="$(mktemp)"
HTTP_CODE=$(curl -sS -o "$RESP_FILE" -w "%{http_code}" \
  -X POST "${API_BASE_URL%/}/api/v1/internal/ingest/sample-bundle" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${BEARER_TOKEN}" \
  --data "$PY_PAYLOAD")

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "[fail] ingest request failed with status $HTTP_CODE" >&2
  cat "$RESP_FILE" >&2
  rm -f "$RESP_FILE"
  exit 1
fi

echo "[ok] ingest request accepted"
cat "$RESP_FILE"
rm -f "$RESP_FILE"
