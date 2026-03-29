#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Run an end-to-end center smoke check against a running Coyote3 API.

Usage:
  scripts/center_smoke.sh \
    --api-base-url <url> \
    (--bearer-token <token> | --username <user> --password <pass>) \
    --yaml-file <path> \
    [--skip-file-check]

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
SKIP_FILE_CHECK=0
PYTHON_BIN="${PYTHON_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    --skip-file-check) SKIP_FILE_CHECK=1; shift ;;
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
  BEARER_TOKEN="$("$PYTHON_BIN" -c '
import json
import sys
print(json.loads(sys.argv[1]).get("session_token", ""))
' "$AUTH_JSON")"
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
if [[ "$SKIP_FILE_CHECK" -eq 1 ]]; then
  PYTHONPATH=. "$PYTHON_BIN" scripts/validate_ingest_spec.py --yaml "$YAML_FILE" >/dev/null
else
  PYTHONPATH=. "$PYTHON_BIN" scripts/validate_ingest_spec.py --yaml "$YAML_FILE" --check-files >/dev/null
fi

echo "[step] collect data files referenced by YAML"
mapfile -t UPLOAD_FILES < <("$PYTHON_BIN" -c '
import sys
from pathlib import Path
import yaml

yaml_path = Path(sys.argv[1]).resolve()
payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
keys = (
    "vcf_files",
    "cnv",
    "cnvprofile",
    "cov",
    "transloc",
    "biomarkers",
    "lowcov",
    "fusion_files",
    "expression_path",
    "classification_path",
    "qc",
)
seen: set[str] = set()
for key in keys:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        continue
    src = Path(value.strip())
    if not src.is_absolute():
        rel_candidates = [
            (yaml_path.parent / src).resolve(),
            (Path.cwd() / src).resolve(),
        ]
        src = next((p for p in rel_candidates if p.exists()), rel_candidates[0])
    if not src.exists():
        continue
    text = str(src)
    if text not in seen:
        seen.add(text)
        print(text)
' "$YAML_FILE")

echo "[step] submit ingest sample-bundle upload"
CURL_ARGS=(
  -X POST "${API_BASE_URL%/}/api/v1/internal/ingest/sample-bundle/upload"
  -H "Authorization: Bearer ${BEARER_TOKEN}"
  -F "yaml_file=@${YAML_FILE};type=text/yaml"
  -F "update_existing=false"
  -F "increment=true"
)
for file_path in "${UPLOAD_FILES[@]}"; do
  CURL_ARGS+=(-F "data_files=@${file_path}")
done

RESP_FILE="$(mktemp)"
HTTP_CODE=$(curl -sS -o "$RESP_FILE" -w "%{http_code}" "${CURL_ARGS[@]}")

if [[ "$HTTP_CODE" -lt 200 || "$HTTP_CODE" -ge 300 ]]; then
  echo "[fail] ingest request failed with status $HTTP_CODE" >&2
  cat "$RESP_FILE" >&2
  rm -f "$RESP_FILE"
  exit 1
fi

echo "[ok] ingest request accepted"
cat "$RESP_FILE"
rm -f "$RESP_FILE"
