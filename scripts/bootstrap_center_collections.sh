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
    [--reference-seed-data <path>] \
    [--seed-actor <email>] \
    [--with-optional] \
    [--skip-existing] \
    [--strict-no-retry]

Options:
  --api-base-url   Base API URL, e.g. http://localhost:8006
  --bearer-token   Existing API bearer token
  --username       API username/email (password mode)
  --password       API password (password mode)
  --seed-file      Seed directory path containing one <collection>.json file per collection
                   default: tests/fixtures/db_dummy/all_collections_dummy
  --reference-seed-data  Directory containing compressed NDJSON reference pack files
                   (for example hgnc_genes.seed.ndjson.gz, roles.seed.ndjson.gz)
  --seed-actor     Value used for created_by/updated_by seed metadata.
                   default: --username value, otherwise admin@coyote3.local
  --with-optional  Seed optional knowledge collections after required baseline
  --skip-existing  Ignore duplicate key conflicts while seeding
  --strict-no-retry  Fail immediately on first collection seed error (no auto retry)

Notes:
  - This is intended for first-time center bootstrap.
  - Inserts are not upserts.
  - By default, first failed write is retried once with ignore_duplicates=true.
  - Use --skip-existing for idempotent reruns.
  - Use --strict-no-retry to disable retry and fail immediately.
  - `users` collection is intentionally skipped; bootstrap first admin/user separately.
USAGE
}

API_BASE_URL=""
BEARER_TOKEN=""
USERNAME=""
PASSWORD=""
SEED_FILE="tests/fixtures/db_dummy/all_collections_dummy"
REFERENCE_SEED_DATA=""
SEED_ACTOR=""
WITH_OPTIONAL=0
SKIP_EXISTING=0
STRICT_NO_RETRY=0
PYTHON_BIN="${PYTHON_BIN:-}"
SEED_BUNDLE_DIR=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
    --bearer-token) BEARER_TOKEN="$2"; shift 2 ;;
    --username) USERNAME="$2"; shift 2 ;;
    --password) PASSWORD="$2"; shift 2 ;;
    --seed-file) SEED_FILE="$2"; shift 2 ;;
    --reference-seed-data) REFERENCE_SEED_DATA="$2"; shift 2 ;;
    --seed-actor) SEED_ACTOR="$2"; shift 2 ;;
    --with-optional) WITH_OPTIONAL=1; shift ;;
    --skip-existing) SKIP_EXISTING=1; shift ;;
    --strict-no-retry) STRICT_NO_RETRY=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$API_BASE_URL" ]]; then
  echo "ERROR: --api-base-url is required" >&2
  usage
  exit 2
fi

if [[ ! -d "$SEED_FILE" ]]; then
  echo "ERROR: seed source not found: $SEED_FILE" >&2
  exit 2
fi
if [[ -n "$REFERENCE_SEED_DATA" && ! -d "$REFERENCE_SEED_DATA" ]]; then
  echo "ERROR: reference seed data source not found: $REFERENCE_SEED_DATA" >&2
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

if [[ -z "$SEED_ACTOR" ]]; then
  if [[ -n "$USERNAME" ]]; then
    SEED_ACTOR="$USERNAME"
  else
    SEED_ACTOR="admin@coyote3.local"
  fi
fi
SEED_NOW="$("$PYTHON_BIN" -c '
from datetime import datetime, timezone
print(datetime.now(timezone.utc).isoformat())
')"

SEED_BUNDLE_DIR="$(mktemp -d)"
trap 'rm -rf "$SEED_BUNDLE_DIR"' EXIT

echo "[step] preparing seed bundle from ${SEED_FILE}"

"$PYTHON_BIN" -c '
import json
import gzip
import sys
from pathlib import Path

source = Path(sys.argv[1])
dest_dir = Path(sys.argv[2])
seed_actor = sys.argv[3]
seed_time = sys.argv[4]
reference_seed_data = Path(sys.argv[5]) if len(sys.argv) > 5 and sys.argv[5] else None

def load_seed(path: Path) -> dict[str, list[dict]]:
    payload: dict[str, list[dict]] = {}
    for file in sorted(path.glob("*.json")):
        value = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(value, list):
            raise SystemExit(f"Collection seed file must contain a JSON list: {file}")
        payload[file.stem] = value
    return payload

def load_reference_seed_pack(path: Path) -> dict[str, list[dict]]:
    required_pack = {
        "hgnc_genes": "hgnc_genes.seed.ndjson.gz",
        "permissions": "permissions.seed.ndjson.gz",
        "refseq_canonical": "refseq_canonical.seed.ndjson.gz",
        "roles": "roles.seed.ndjson.gz",
        "vep_metadata": "vep_metadata.seed.ndjson.gz",
    }

    def load_ndjson_gzip(file_path: Path) -> list[dict]:
        docs: list[dict] = []
        with gzip.open(file_path, "rt", encoding="utf-8") as handle:
            for line in handle:
                text = line.strip()
                if not text:
                    continue
                value = json.loads(text)
                if not isinstance(value, dict):
                    raise SystemExit(
                        f"Reference seed file must contain JSON objects per line: {file_path}"
                    )
                docs.append(value)
        return docs

    payload: dict[str, list[dict]] = {}
    for collection, filename in required_pack.items():
        file_path = path / filename
        if not file_path.exists():
            raise SystemExit(f"Missing reference seed file: {file_path}")
        payload[collection] = load_ndjson_gzip(file_path)
    return payload

def normalize_extended_json(value):
    if isinstance(value, dict):
        if set(value.keys()) == {"$date"}:
            return value.get("$date")
        if set(value.keys()) == {"$oid"}:
            return value.get("$oid")
        return {k: normalize_extended_json(v) for k, v in value.items()}
    if isinstance(value, list):
        return [normalize_extended_json(v) for v in value]
    return value

def lower_business_keys(seed: dict[str, list[dict]]) -> None:
    lowercase_fields = {
        "permissions": ("permission_id",),
        "roles": ("role_id",),
        "users": ("username", "email", "role", "assay_groups", "assays", "permissions", "deny_permissions"),
        "asp_configs": ("aspc_id", "assay_name", "asp_group"),
        "assay_specific_panels": ("asp_id", "assay_name", "asp_group"),
        "insilico_genelists": ("isgl_id", "diagnosis", "assay_groups", "assays"),
        "blacklist": ("assay_group", "assay"),
        "samples": ("assay", "subpanel"),
    }

    def normalize_item(value):
        if isinstance(value, str):
            return value.strip().lower()
        if isinstance(value, list):
            return [normalize_item(item) for item in value]
        return value

    for collection, fields in lowercase_fields.items():
        for doc in seed.get(collection, []) or []:
            if not isinstance(doc, dict):
                continue
            for field in fields:
                if field in doc and doc[field] is not None:
                    doc[field] = normalize_item(doc[field])

def stamp_docs(seed: dict[str, list[dict]]) -> None:
    for docs in seed.values():
        if not isinstance(docs, list):
            continue
        for i, doc in enumerate(docs):
            if isinstance(doc, dict):
                normalized_doc = normalize_extended_json(doc)
                docs[i] = normalized_doc
                doc = normalized_doc
                doc["created_by"] = seed_actor
                doc["updated_by"] = seed_actor
                doc["created_on"] = seed_time
                doc["updated_on"] = seed_time

seed = load_seed(source)
if reference_seed_data is not None:
    seed.update(load_reference_seed_pack(reference_seed_data))
lower_business_keys(seed)
stamp_docs(seed)

for collection, docs in seed.items():
    (dest_dir / f"{collection}.json").write_text(
        json.dumps(docs, ensure_ascii=False), encoding="utf-8"
    )

print(f"[ok] normalized seed bundle: {dest_dir}")
' "$SEED_FILE" "$SEED_BUNDLE_DIR" "$SEED_ACTOR" "$SEED_NOW" "$REFERENCE_SEED_DATA"

echo "[step] validating source seed naming"
if [[ -n "$REFERENCE_SEED_DATA" ]]; then
  "$PYTHON_BIN" scripts/validate_assay_consistency.py \
    --seed-file "$SEED_FILE" \
    --reference-seed-data "$REFERENCE_SEED_DATA"
else
  "$PYTHON_BIN" scripts/validate_assay_consistency.py \
    --seed-file "$SEED_FILE"
fi

echo "[step] validating assay consistency in seed directory"
"$PYTHON_BIN" scripts/validate_assay_consistency.py --seed-file "$SEED_BUNDLE_DIR"

required_collections=(
  permissions
  roles
  refseq_canonical
  hgnc_genes
  vep_metadata
  asp_configs
  assay_specific_panels
)

optional_collections=(
  insilico_genelists
  civic_genes
  civic_variants
  cosmic
  hpaexpr
  iarc_tp53
  oncokb_actionable
  oncokb_genes
)

collection_count() {
  "$PYTHON_BIN" -c '
import json
import sys
from pathlib import Path

seed_dir = Path(sys.argv[1])
collection = sys.argv[2]
path = seed_dir / f"{collection}.json"
value = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
print(len(value) if isinstance(value, list) else 0)
' "$SEED_BUNDLE_DIR" "$1"
}

write_payload_file() {
  local collection="$1"
  local ignore_duplicates="${2:-0}"
  local out_file="$3"
  "$PYTHON_BIN" -c '
import json
import sys
from pathlib import Path

seed_dir = Path(sys.argv[1])
collection = sys.argv[2]
ignore_duplicates = str(sys.argv[3]).strip() == "1"
path = seed_dir / f"{collection}.json"
docs = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
payload = {"collection": collection, "documents": docs}
if ignore_duplicates:
    payload["ignore_duplicates"] = True
print(json.dumps(payload, separators=(",", ":")))
' "$SEED_BUNDLE_DIR" "$collection" "$ignore_duplicates" >"$out_file"
}

post_bulk() {
  local collection="$1"
  local payload_file="$2"
  local resp_file
  resp_file="$(mktemp)"

  local status
  status="$(curl -sS -o "$resp_file" -w "%{http_code}" \
    -X POST "${API_BASE_URL%/}/api/v1/internal/ingest/collection/bulk" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer ${BEARER_TOKEN}" \
    --data-binary "@${payload_file}")"

  # When caller did not request skip-existing, retry once with duplicate-tolerant
  # mode. Internal API may return generic 500 payloads, so duplicate details are
  # not always visible at this layer.
  if [[ "$status" -lt 200 || "$status" -ge 300 ]]; then
    if [[ "$SKIP_EXISTING" -eq 0 && "$STRICT_NO_RETRY" -eq 0 ]]; then
      echo "[warn] ${collection}: initial seed attempt failed; retrying with ignore_duplicates=true"
      local retry_payload_file
      retry_payload_file="$(mktemp)"
      write_payload_file "$collection" "1" "$retry_payload_file"
      status="$(curl -sS -o "$resp_file" -w "%{http_code}" \
        -X POST "${API_BASE_URL%/}/api/v1/internal/ingest/collection/bulk" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer ${BEARER_TOKEN}" \
        --data-binary "@${retry_payload_file}")"
      rm -f "$retry_payload_file"
    fi
  fi

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
  local payload_file
  count="$(collection_count "$collection")"
  if [[ "$count" -eq 0 ]]; then
    echo "[skip] ${collection}: no docs in ${SEED_FILE}"
    return 0
  fi
  echo "[step] seeding ${collection} (${count} docs)"
  payload_file="$(mktemp)"
  write_payload_file "$collection" "$SKIP_EXISTING" "$payload_file"
  post_bulk "$collection" "$payload_file"
  rm -f "$payload_file"
}

echo "[step] API health check"
curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null

echo "[step] seeding required baseline collections"
for collection in "${required_collections[@]}"; do
  seed_one "$collection"
done

users_count="$(collection_count "users")"
if [[ "$users_count" -gt 0 ]]; then
  echo "[info] users collection present in seed directory (${users_count} docs) but intentionally skipped."
  echo "[info] first admin/user bootstrap is handled separately via scripts/bootstrap_local_admin.py or admin UI."
fi

if [[ "$WITH_OPTIONAL" -eq 1 ]]; then
  echo "[step] seeding optional knowledge collections"
  for collection in "${optional_collections[@]}"; do
    seed_one "$collection"
  done
fi

echo "[ok] baseline collection bootstrap completed"
