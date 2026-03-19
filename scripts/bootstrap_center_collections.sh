#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Seed baseline center collections through internal bulk-ingest API in strict order.

Usage:
  scripts/bootstrap_center_collections.sh \
    --api-base-url <url> \
    (--bearer-token <token> | --username <user> --password <pass>) \
    [--seed-file <path>] \
    [--with-optional] \
    [--skip-existing]

Options:
  --api-base-url   Base API URL, e.g. http://localhost:8006
  --bearer-token   Existing API bearer token
  --username       API username/email (password mode)
  --password       API password (password mode)
  --seed-file      JSON file containing collection -> [docs] mapping
                   default: tests/fixtures/db_dummy/center_template_seed.json
  --with-optional  Seed optional knowledge collections after required baseline
  --skip-existing  Ignore duplicate key conflicts while seeding

Notes:
  - This is intended for first-time center bootstrap.
  - Inserts are not upserts.
  - Use --skip-existing for idempotent reruns.
USAGE
}

API_BASE_URL=""
BEARER_TOKEN=""
USERNAME=""
PASSWORD=""
SEED_FILE="tests/fixtures/db_dummy/center_template_seed.json"
WITH_OPTIONAL=0
SKIP_EXISTING=0
PYTHON_BIN="${PYTHON_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --seed-file) SEED_FILE="$2"; shift 2 ;;
    --with-optional) WITH_OPTIONAL=1; shift ;;
    --skip-existing) SKIP_EXISTING=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$API_BASE_URL" ]]; then
  echo "ERROR: --api-base-url is required" >&2
  usage
  exit 2
fi

if [[ ! -f "$SEED_FILE" ]]; then
  echo "ERROR: seed file not found: $SEED_FILE" >&2
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

echo "[step] validating assay consistency in seed file"
"$PYTHON_BIN" scripts/validate_assay_consistency.py --seed-file "$SEED_FILE"

required_collections=(
  permissions
  roles
  users
  asp_configs
  assay_specific_panels
  insilico_genelists
  refseq_canonical
  hgnc_genes
)

optional_collections=(
  civic_genes
  civic_variants
  oncokb_genes
  oncokb_actionable
  brcaexchange
  iarc_tp53
  cosmic
  vep_metadata
)

collection_count() {
  "$PYTHON_BIN" - "$SEED_FILE" "$1" <<'PY'
import json
import sys
from pathlib import Path

seed = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
value = seed.get(sys.argv[2], [])
print(len(value) if isinstance(value, list) else 0)
PY
}

make_payload() {
  "$PYTHON_BIN" - "$SEED_FILE" "$1" <<'PY'
import json
import sys
from pathlib import Path

seed = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
collection = sys.argv[2]
docs = seed.get(collection, [])
print(json.dumps({"collection": collection, "documents": docs}, separators=(",", ":")))
PY
}

post_bulk() {
  local collection="$1"
  local payload="$2"
  local resp_file
  resp_file="$(mktemp)"

  local status
  status="$(curl -sS -o "$resp_file" -w "%{http_code}" \
    -X POST "${API_BASE_URL%/}/api/v1/internal/ingest/collection/bulk" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${BEARER_TOKEN}" \
    --data "$payload")"

  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    echo "[fail] ${collection} seed failed (HTTP ${status})" >&2
    cat "$resp_file" >&2
    rm -f "$resp_file"
    exit 1
  fi

  echo "[ok] ${collection} seeded"
  cat "$resp_file"
  rm -f "$resp_file"
}

seed_one() {
  local collection="$1"
  local count
  local payload
  count="$(collection_count "$collection")"
  if [[ "$count" -eq 0 ]]; then
    echo "[skip] ${collection}: no docs in ${SEED_FILE}"
    return 0
  fi
  echo "[step] seeding ${collection} (${count} docs)"
  payload="$(make_payload "$collection")"
  if [[ "$SKIP_EXISTING" -eq 1 ]]; then
    payload="$("$PYTHON_BIN" - <<'PY' "$payload"
import json
import sys
p = json.loads(sys.argv[1])
p["ignore_duplicates"] = True
print(json.dumps(p, separators=(",", ":")))
PY
    )"
  fi
  post_bulk "$collection" "$payload"
}

echo "[step] API health check"
curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null

echo "[step] seeding required baseline collections"
for collection in "${required_collections[@]}"; do
  seed_one "$collection"
done

if [[ "$WITH_OPTIONAL" -eq 1 ]]; then
  echo "[step] seeding optional knowledge collections"
  for collection in "${optional_collections[@]}"; do
    seed_one "$collection"
  done
fi

echo "[ok] baseline collection bootstrap completed"
