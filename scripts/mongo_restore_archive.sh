#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Restore a MongoDB compressed archive using mongorestore in a container.

Usage:
  scripts/mongo_restore_archive.sh \
    --mongo-uri mongodb://restore-user:secret@mongo.example.internal:27017/admin?authSource=admin\&replicaSet=coyote3-rs \
    --archive /data/coyote3/backups/mongo/coyote3_mongodb_20260311T000000Z.archive.gz \
    --drop \
    --confirm RESTORE_PATIENT_DATA

Safety:
  --confirm RESTORE_PATIENT_DATA is mandatory.
Optional:
  --docker-network coyote3-mongo-net
EOF
}

MONGO_URI=""
ARCHIVE_PATH=""
DROP_FLAG=0
CONFIRM=""
DOCKER_NETWORK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mongo-uri) MONGO_URI="$2"; shift 2 ;;
    --archive) ARCHIVE_PATH="$2"; shift 2 ;;
    --drop) DROP_FLAG=1; shift ;;
    --confirm) CONFIRM="$2"; shift 2 ;;
    --docker-network) DOCKER_NETWORK="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[error] unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$MONGO_URI" || -z "$ARCHIVE_PATH" ]]; then
  echo "[error] --mongo-uri and --archive are required"
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

gzip -t "$ARCHIVE_PATH"
if [[ -f "${ARCHIVE_PATH}.meta" ]]; then
  expected_sha256="$(awk -F= '$1 == "sha256" { print $2 }' "${ARCHIVE_PATH}.meta")"
  if [[ -n "$expected_sha256" ]]; then
    actual_sha256="$(sha256sum "$ARCHIVE_PATH" | awk '{print $1}')"
    if [[ "$actual_sha256" != "$expected_sha256" ]]; then
      echo "[error] archive checksum does not match ${ARCHIVE_PATH}.meta" >&2
      exit 5
    fi
  fi
fi

drop_opt=""
if [[ "$DROP_FLAG" -eq 1 ]]; then
  drop_opt="--drop"
fi

echo "[warn] restore target uri=${MONGO_URI}"
echo "[warn] archive=${ARCHIVE_PATH}"
echo "[warn] this restores the complete MongoDB archive, including the oplog. Use a dedicated recovery target."
echo "[info] starting restore"

docker_args=(--rm -v "${ARCHIVE_DIR}:/backup:ro")
if [[ -n "$DOCKER_NETWORK" ]]; then
  docker_args+=(--network "$DOCKER_NETWORK")
fi

docker run "${docker_args[@]}" mongo:8.2 \
  mongorestore --uri="$MONGO_URI" --archive="/backup/${ARCHIVE_FILE}" --gzip --oplogReplay ${drop_opt}

echo "[ok] restore complete"
