#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Validate a local manifest and ingest it through a running Coyote3 API.
This writes sample data, using increment=true; it is not a read-only health check.

Usage:
  bash scripts/deployment/center_check.sh \
    --api-base-url <url> \
    (--bearer-token <token> | --username <user> [--password <pass>]) \
    [--provider <local|ldap>] \
    --yaml-file <path> \
    [--data-archive <zip>] \
    [--skip-file-check]

Example:
  bash scripts/deployment/center_check.sh \
    --api-base-url https://validation.example.org/coyote3 \
    --username validation.user --provider local \
    --yaml-file /validation/sample.yaml --data-archive /validation/inputs.zip

Omit --password for a hidden prompt. Without a ZIP, declared manifest paths must
already be readable by the API container. A terminal failed ingest exits nonzero.
USAGE
}

API_BASE_URL=""
BEARER_TOKEN=""
USERNAME=""
PASSWORD=""
PROVIDER="local"
YAML_FILE=""
DATA_ARCHIVE=""
SKIP_FILE_CHECK=0
PYTHON_BIN="${PYTHON_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url|--bearer-token|--username|--password|--provider|--yaml-file|--data-archive)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || { echo "Missing value for $1" >&2; exit 2; } ;;
  esac
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --provider) PROVIDER="$2"; shift 2 ;;
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    --data-archive) DATA_ARCHIVE="$2"; shift 2 ;;
    --skip-file-check) SKIP_FILE_CHECK=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ "$PROVIDER" != "local" && "$PROVIDER" != "ldap" ]]; then
  echo "ERROR: --provider must be local or ldap" >&2
  exit 2
fi

if [[ -z "$API_BASE_URL" || -z "$YAML_FILE" ]]; then
  echo "ERROR: --api-base-url and --yaml-file are required" >&2
  usage
  exit 2
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
YAML_FILE="$(realpath "$YAML_FILE")"
[[ -z "$DATA_ARCHIVE" ]] || DATA_ARCHIVE="$(realpath "$DATA_ARCHIVE")"
[[ -z "$DATA_ARCHIVE" || -f "$DATA_ARCHIVE" ]] || { echo "ZIP archive not found" >&2; exit 2; }
cd "$ROOT_DIR"
source scripts/deployment/python_runtime.sh
select_deployment_python "$ROOT_DIR"

if [[ -z "$BEARER_TOKEN" ]]; then
  if [[ -z "$USERNAME" ]]; then
    echo "ERROR: provide either --bearer-token or --username" >&2
    usage
    exit 2
  fi
  if [[ -z "$PASSWORD" ]]; then
    read -r -s -p "API password: " PASSWORD
    printf '\n' >&2
  fi
  echo "[step] login and resolve bearer token"
  AUTH_JSON="$(COYOTE_CENTER_CHECK_PASSWORD="$PASSWORD" PYTHONPATH=. "$PYTHON_BIN" scripts/ingest/api_login.py \
    --base-url "$API_BASE_URL" \
    --mode password \
    --username "$USERNAME" \
    --password-env COYOTE_CENTER_CHECK_PASSWORD \
    --provider "$PROVIDER" \
    --print-token)"
  BEARER_TOKEN="$("$PYTHON_BIN" -c '
import json
import sys
print(json.load(sys.stdin).get("session_token", ""))
' <<< "$AUTH_JSON")"
  unset PASSWORD AUTH_JSON
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
if [[ "$SKIP_FILE_CHECK" -eq 1 || -n "$DATA_ARCHIVE" ]]; then
  PYTHONPATH=. "$PYTHON_BIN" scripts/ingest/validate_ingest_spec.py --yaml "$YAML_FILE" >/dev/null
else
  PYTHONPATH=. "$PYTHON_BIN" scripts/ingest/validate_ingest_spec.py --yaml "$YAML_FILE" --check-files >/dev/null
fi

echo "[step] submit ingest sample-bundle upload"
COYOTE_CENTER_CHECK_TOKEN="$BEARER_TOKEN" PYTHONPATH=. "$PYTHON_BIN" - \
  "$API_BASE_URL" "$YAML_FILE" "$DATA_ARCHIVE" <<'PY'
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace
from scripts.ingest.submit_ingest_manifest import upload

token = os.environ["COYOTE_CENTER_CHECK_TOKEN"]
if any(char in token for char in '\r\n"\\'):
    raise SystemExit("Invalid API token")
options = SimpleNamespace(base_url=sys.argv[1].rstrip("/"), archive=sys.argv[3] or None,
                          timeout=1800, update_existing=False, increment=True,
                          auth="bearer", ca_bundle=None)
result = upload(options, Path(sys.argv[2]), token)
print(json.dumps(result, indent=2))
raise SystemExit(0 if result["status"] == "ok" else 1)
PY
