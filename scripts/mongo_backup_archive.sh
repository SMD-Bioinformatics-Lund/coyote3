#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Create a compressed MongoDB backup archive using mongodump in a container.

Usage:
  scripts/mongo_backup_archive.sh \
    --mongo-uri mongodb://localhost:27017 \
    --db coyote3 \
    --out-dir /data/coyote3/backups/mongo

Optional:
  --label nightly
  --docker-network coyote3-dev-net
EOF
}

MONGO_URI=""
DB_NAME=""
OUT_DIR=""
LABEL=""
DOCKER_NETWORK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mongo-uri) MONGO_URI="$2"; shift 2 ;;
    --db) DB_NAME="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --docker-network) DOCKER_NETWORK="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[error] unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$MONGO_URI" || -z "$DB_NAME" || -z "$OUT_DIR" ]]; then
  echo "[error] --mongo-uri, --db, and --out-dir are required"
  usage
  exit 2
fi

mkdir -p "$OUT_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
safe_label=""
if [[ -n "$LABEL" ]]; then
  safe_label="_$(echo "$LABEL" | tr -cd 'A-Za-z0-9._-')"
fi

archive_file="${DB_NAME}_${ts}${safe_label}.archive.gz"
archive_path="${OUT_DIR}/${archive_file}"

echo "[info] creating backup archive: $archive_path"

docker_args=(--rm -v "${OUT_DIR}:/backup")
if [[ -n "$DOCKER_NETWORK" ]]; then
  docker_args+=(--network "$DOCKER_NETWORK")
fi

docker run "${docker_args[@]}" mongo:7.0 \
  sh -lc "mongodump --uri='${MONGO_URI}' --db='${DB_NAME}' --archive='/backup/${archive_file}' --gzip --readPreference=primary"

sha256="$(sha256sum "$archive_path" | awk '{print $1}')"
meta_path="${archive_path}.meta"

cat > "$meta_path" <<EOF
created_at_utc=${ts}
db_name=${DB_NAME}
archive_file=${archive_file}
sha256=${sha256}
host=$(hostname)
EOF

echo "[ok] backup complete"
echo "[ok] sha256=${sha256}"
echo "[ok] metadata=${meta_path}"
