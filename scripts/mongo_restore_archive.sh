#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Restore a MongoDB compressed archive using mongorestore in a container.

Usage:
  scripts/mongo_restore_archive.sh \
    --mongo-uri mongodb://localhost:27017 \
    --db coyote3 \
    --archive /data/coyote3/backups/mongo/coyote3_20260311T000000Z.archive.gz \
    --drop \
    --confirm RESTORE_PATIENT_DATA

Safety:
  --confirm RESTORE_PATIENT_DATA is mandatory.
EOF
}

MONGO_URI=""
DB_NAME=""
ARCHIVE_PATH=""
DROP_FLAG=0
CONFIRM=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mongo-uri) MONGO_URI="$2"; shift 2 ;;
    --db) DB_NAME="$2"; shift 2 ;;
    --archive) ARCHIVE_PATH="$2"; shift 2 ;;
    --drop) DROP_FLAG=1; shift ;;
    --confirm) CONFIRM="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[error] unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$MONGO_URI" || -z "$DB_NAME" || -z "$ARCHIVE_PATH" ]]; then
  echo "[error] --mongo-uri, --db, and --archive are required"
  usage
  exit 2
fi

if [[ "$CONFIRM" != "RESTORE_PATIENT_DATA" ]]; then
  echo "[error] restore blocked. pass: --confirm RESTORE_PATIENT_DATA"
  exit 3
fi

if [[ ! -f "$ARCHIVE_PATH" ]]; then
  echo "[error] archive not found: $ARCHIVE_PATH"
  exit 4
fi

ARCHIVE_DIR="$(cd "$(dirname "$ARCHIVE_PATH")" && pwd)"
ARCHIVE_FILE="$(basename "$ARCHIVE_PATH")"

drop_opt=""
if [[ "$DROP_FLAG" -eq 1 ]]; then
  drop_opt="--drop"
fi

echo "[warn] restore target db=${DB_NAME} uri=${MONGO_URI}"
echo "[warn] archive=${ARCHIVE_PATH}"
echo "[info] starting restore"

docker run --rm \
  -v "${ARCHIVE_DIR}:/backup:ro" \
  mongo:7.0 \
  sh -lc "mongorestore --uri='${MONGO_URI}' --archive='/backup/${ARCHIVE_FILE}' --gzip --nsInclude='${DB_NAME}.*' ${drop_opt}"

echo "[ok] restore complete"
