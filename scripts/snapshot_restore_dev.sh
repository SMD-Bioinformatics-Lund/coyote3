#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PYTHON_BIN:-}" ]]; then
  if [[ -n "${VIRTUAL_ENV:-}" && -x "${VIRTUAL_ENV}/bin/python" ]]; then
    PYTHON_BIN="${VIRTUAL_ENV}/bin/python"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: Could not find a Python interpreter. Set PYTHON_BIN explicitly." >&2
    exit 1
  fi
fi
SNAPSHOT_SCRIPT="${SNAPSHOT_SCRIPT:-scripts/create_mongo_snapshot.py}"

SOURCE_URI="mongodb://localhost:27017"
SOURCE_DB=""
TARGET_DB="coyote3_dev"
TARGET_URI=""
SAMPLE_COUNT="60"
SEED="42"
OUTPUT_DIR="snapshots"
COLLECTIONS_CONFIG="config/coyote3_collections.toml"
CONFIG_SECTION=""
DROP_TARGET="1"
FRESH_SNAPSHOT="0"
SAMPLE_LIST_FILE=""
SAMPLE_NAMES=()
SAMPLE_IDS=()

usage() {
  cat <<'EOF'
Usage:
  scripts/snapshot_restore_dev.sh --source-db <db> [options]

Required:
  --source-db <name>              Source database to snapshot.

Optional:
  --source-uri <uri>              Source Mongo URI (default: mongodb://localhost:27017)
  --target-uri <uri>              Target/dev Mongo URI (default: mongodb://localhost:37017)
  --target-db <name>              Target/dev DB name (default: coyote3_dev)
  --sample-count <n>              Mixed-assay sample count when explicit list not provided (default: 60)
  --seed <n>                      Random seed (default: 42)
  --output-dir <dir>              Snapshot base dir (default: snapshots)
  --collections-config <path>     Collections TOML (default: config/coyote3_collections.toml)
  --config-section <name>         TOML section override (default: source db name)
  --sample-list-file <path>       Newline-delimited sample selectors (name or _id)
  --sample-name <name>            Explicit sample name (repeatable)
  --sample-id <id>                Explicit sample _id (repeatable)
  --keep-target-data              Do not wipe target collections before insert
  --fresh-snapshot                Remove existing snapshot artifacts in --output-dir before creating a new one
  --python-bin <path>             Python executable override

Example:
  scripts/snapshot_restore_dev.sh \
    --source-uri mongodb://localhost:5818 \
    --source-db coyote3 \
    --target-uri mongodb://localhost:37017 \
    --target-db coyote3_dev \
    --sample-count 60
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-uri) SOURCE_URI="$2"; shift 2 ;;
    --source-db) SOURCE_DB="$2"; shift 2 ;;
    --target-uri) TARGET_URI="$2"; shift 2 ;;
    --target-db) TARGET_DB="$2"; shift 2 ;;
    --sample-count) SAMPLE_COUNT="$2"; shift 2 ;;
    --seed) SEED="$2"; shift 2 ;;
    --output-dir) OUTPUT_DIR="$2"; shift 2 ;;
    --collections-config) COLLECTIONS_CONFIG="$2"; shift 2 ;;
    --config-section) CONFIG_SECTION="$2"; shift 2 ;;
    --sample-list-file) SAMPLE_LIST_FILE="$2"; shift 2 ;;
    --sample-name) SAMPLE_NAMES+=("$2"); shift 2 ;;
    --sample-id) SAMPLE_IDS+=("$2"); shift 2 ;;
    --keep-target-data) DROP_TARGET="0"; shift ;;
    --fresh-snapshot) FRESH_SNAPSHOT="1"; shift ;;
    --python-bin) PYTHON_BIN="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$SOURCE_DB" ]]; then
  echo "ERROR: --source-db is required" >&2
  usage
  exit 2
fi

if [[ -z "$TARGET_URI" ]]; then
  target_port="${COYOTE3_DEV_MONGO_PORT:-37017}"
  if [[ -n "${MONGO_APP_USER:-}" && -n "${MONGO_APP_PASSWORD:-}" ]]; then
    TARGET_URI="mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:${target_port}/${TARGET_DB}?authSource=${TARGET_DB}"
  else
    TARGET_URI="mongodb://localhost:${target_port}"
  fi
fi

if [[ "$FRESH_SNAPSHOT" == "1" ]]; then
  if [[ -z "$OUTPUT_DIR" || "$OUTPUT_DIR" == "/" || "$OUTPUT_DIR" == "." ]]; then
    echo "ERROR: refusing to clean unsafe output dir: '$OUTPUT_DIR'" >&2
    exit 2
  fi
  if [[ -d "$OUTPUT_DIR" ]]; then
    echo "[step] removing existing snapshots under $OUTPUT_DIR"
    rm -rf "${OUTPUT_DIR:?}/"*
  fi
fi

SNAPSHOT_ARGS=(
  "$PYTHON_BIN" "$SNAPSHOT_SCRIPT"
  --mongo-uri "$SOURCE_URI"
  --db "$SOURCE_DB"
  --sample-count "$SAMPLE_COUNT"
  --seed "$SEED"
  --output-dir "$OUTPUT_DIR"
  --collections-config "$COLLECTIONS_CONFIG"
)
if [[ -n "$CONFIG_SECTION" ]]; then
  SNAPSHOT_ARGS+=(--config-section "$CONFIG_SECTION")
fi
if [[ -n "$SAMPLE_LIST_FILE" ]]; then
  SNAPSHOT_ARGS+=(--sample-list-file "$SAMPLE_LIST_FILE")
fi
for name in "${SAMPLE_NAMES[@]}"; do
  SNAPSHOT_ARGS+=(--sample-name "$name")
done
for sid in "${SAMPLE_IDS[@]}"; do
  SNAPSHOT_ARGS+=(--sample-id "$sid")
done

echo "[step] creating snapshot from ${SOURCE_URI}/${SOURCE_DB}"
SNAPSHOT_OUTPUT="$("${SNAPSHOT_ARGS[@]}")"
echo "$SNAPSHOT_OUTPUT"
SNAPSHOT_DIR="$(echo "$SNAPSHOT_OUTPUT" | awk -F= '/^SNAPSHOT_DIR=/{print $2}' | tail -n1)"
if [[ -z "$SNAPSHOT_DIR" ]]; then
  echo "ERROR: could not parse SNAPSHOT_DIR from snapshot output" >&2
  exit 1
fi

echo "[step] restoring snapshot into ${TARGET_URI}/${TARGET_DB}"
export SNAPSHOT_DIR TARGET_URI TARGET_DB DROP_TARGET PYTHON_BIN
"$PYTHON_BIN" - <<'PY'
import json
import os
from pathlib import Path

from bson import json_util
from pymongo import MongoClient

snapshot_dir = Path(os.environ["SNAPSHOT_DIR"])
target_uri = os.environ["TARGET_URI"]
target_db = os.environ["TARGET_DB"]
drop_target = os.environ.get("DROP_TARGET", "1") == "1"

manifest_path = snapshot_dir / "manifest.json"
manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

client = MongoClient(target_uri, serverSelectionTimeoutMS=7000)
client.admin.command("ping")
db = client[target_db]

total_docs = 0
for entry in manifest.get("collections", []):
    if not entry.get("exists") or not entry.get("file"):
        continue
    collection = str(entry["collection"])
    file_path = snapshot_dir / str(entry["file"])
    if not file_path.exists():
        continue

    coll = db[collection]
    if drop_target:
        coll.delete_many({})

    docs = []
    with file_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            docs.append(json_util.loads(line))
    if docs:
        coll.insert_many(docs, ordered=False)
    total_docs += len(docs)
    print(f"[ok] restored {collection}: {len(docs)} docs")

print(f"[ok] restore complete db={target_db} total_docs={total_docs}")
PY

echo "[ok] snapshot+restore done"
