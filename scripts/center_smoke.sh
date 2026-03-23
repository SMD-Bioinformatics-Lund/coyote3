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
    [--skip-file-check] \
    [--no-stage-files]

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
STAGE_FILES=1
PYTHON_BIN="${PYTHON_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    --skip-file-check) SKIP_FILE_CHECK=1; shift ;;
    --no-stage-files) STAGE_FILES=0; shift ;;
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

if [[ "$STAGE_FILES" -eq 1 ]]; then
  API_TARGET="$("$PYTHON_BIN" - <<'PY' "$API_BASE_URL"
from urllib.parse import urlparse
import sys
u = urlparse(sys.argv[1])
host = (u.hostname or "").lower()
port = u.port or (443 if u.scheme == "https" else 80)
print(f"{host}:{port}")
PY
  )"
  API_HOST="${API_TARGET%%:*}"
  API_PORT="${API_TARGET##*:}"
  if [[ "$API_HOST" == "localhost" || "$API_HOST" == "127.0.0.1" ]] && command -v docker >/dev/null 2>&1; then
    SMOKE_DOCKER_API_CONTAINER="$(docker ps --filter "publish=${API_PORT}" --format '{{.Names}}' | head -n 1 || true)"
    export SMOKE_DOCKER_API_CONTAINER
  fi
fi

echo "[step] health check"
curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null

echo "[step] local ingest spec validation"
if [[ "$SKIP_FILE_CHECK" -eq 1 ]]; then
  PYTHONPATH=. "$PYTHON_BIN" scripts/validate_ingest_spec.py --yaml "$YAML_FILE" >/dev/null
else
  PYTHONPATH=. "$PYTHON_BIN" scripts/validate_ingest_spec.py --yaml "$YAML_FILE" --check-files >/dev/null
fi

echo "[step] submit ingest sample-bundle"
PY_PAYLOAD="$({
"$PYTHON_BIN" - <<'PY' "$YAML_FILE" "$STAGE_FILES"
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import yaml

yaml_path = Path(sys.argv[1]).resolve()
stage_files = sys.argv[2] == "1"
payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

if stage_files:
    candidates = [
        Path("/data/coyote3/smoke_ingest"),
        Path("/access/coyote3/smoke_ingest"),
        Path("/media/coyote3/smoke_ingest"),
        Path("/fs1/coyote3/smoke_ingest"),
        Path("/tmp/coyote3/smoke_ingest"),
    ]
    stage_root = None
    for candidate in candidates:
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            stage_root = candidate
            break
        except OSError:
            continue
    if stage_root is None:
        raise SystemExit(
            "No writable staging root found. Set --no-stage-files and provide API-visible paths."
        )

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    stage_dir = stage_root / run_id
    stage_dir.mkdir(parents=True, exist_ok=True)

    file_fields = (
        "vcf_files",
        "cnv",
        "cov",
        "transloc",
        "biomarkers",
        "fusion_files",
        "expression_path",
        "classification_path",
        "qc",
        "cnvprofile",
    )
    sentinels = {"", "no_update", "NO_UPDATE"}

    for field in file_fields:
        value = payload.get(field)
        if value is None:
            continue
        value_str = str(value).strip()
        if value_str in sentinels:
            continue

        src = Path(value_str)
        if not src.is_absolute():
            rel_candidates = [
                (yaml_path.parent / src).resolve(),
                (Path.cwd() / src).resolve(),
            ]
            found = next((p for p in rel_candidates if p.exists()), None)
            src = found or rel_candidates[0]

        if not src.exists():
            continue

        dst_name = src.name
        dst = stage_dir / dst_name
        if dst.exists():
            dst = stage_dir / f"{field}_{dst_name}"
        shutil.copy2(src, dst)
        payload[field] = str(dst)

    container = os.environ.get("SMOKE_DOCKER_API_CONTAINER", "").strip()
    if container:
        subprocess.run(
            ["docker", "exec", container, "mkdir", "-p", str(stage_dir)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["docker", "cp", f"{stage_dir}/.", f"{container}:{stage_dir}"],
            check=True,
            stdout=subprocess.DEVNULL,
        )

# Smoke should be repeatable across runs; enable auto-suffix when sample name exists.
payload["increment"] = True

yaml_content = yaml.safe_dump(payload, sort_keys=False)
print(json.dumps({"yaml_content": yaml_content, "update_existing": False}))
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
