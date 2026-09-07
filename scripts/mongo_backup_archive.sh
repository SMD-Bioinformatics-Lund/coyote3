#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Create a compressed MongoDB backup archive using mongodump in a container.

Usage:
  scripts/mongo_backup_archive.sh \
    --mongo-uri mongodb://backup-user:secret@mongo.example.internal:27017/admin?authSource=admin\&replicaSet=coyote3-rs \
    --out-dir /data/coyote3/backups/mongo

Optional:
  --label nightly
  --docker-network coyote3-mongo-net
EOF
}

MONGO_URI=""
OUT_DIR=""
LABEL=""
DOCKER_NETWORK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mongo-uri) MONGO_URI="$2"; shift 2 ;;
    --out-dir) OUT_DIR="$2"; shift 2 ;;
    --label) LABEL="$2"; shift 2 ;;
    --docker-network) DOCKER_NETWORK="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "[error] unknown arg: $1"; usage; exit 2 ;;
  esac
done

if [[ -z "$MONGO_URI" || -z "$OUT_DIR" ]]; then
  echo "[error] --mongo-uri and --out-dir are required"
  usage
  exit 2
fi

mkdir -p "$OUT_DIR"
ts="$(date -u +%Y%m%dT%H%M%SZ)"
safe_label=""
if [[ -n "$LABEL" ]]; then
  safe_label="_$(echo "$LABEL" | tr -cd 'A-Za-z0-9._-')"
fi

archive_file="coyote3_mongodb_${ts}${safe_label}.archive.gz"
archive_path="${OUT_DIR}/${archive_file}"
partial_file=".${archive_file}.partial"
partial_path="${OUT_DIR}/${partial_file}"
meta_path="${archive_path}.meta"
partial_meta_path="${meta_path}.partial"

cleanup() {
  rm -f "$partial_path" "$partial_meta_path"
}
trap cleanup EXIT

echo "[info] creating backup archive: $archive_path"

docker_args=(--rm -v "${OUT_DIR}:/backup")
if [[ -n "$DOCKER_NETWORK" ]]; then
  docker_args+=(--network "$DOCKER_NETWORK")
fi

docker run "${docker_args[@]}" mongo:8.2 \
  mongodump --uri="$MONGO_URI" --archive="/backup/${partial_file}" --gzip --oplog --readPreference=primary

gzip -t "$partial_path"
sha256="$(sha256sum "$partial_path" | awk '{print $1}')"

cat > "$partial_meta_path" <<EOF
created_at_utc=${ts}
archive_file=${archive_file}
sha256=${sha256}
host=$(hostname)
mongo_tools_image=mongo:8.2
consistency=oplog
restore_option=--oplogReplay
EOF

mv "$partial_path" "$archive_path"
mv "$partial_meta_path" "$meta_path"
trap - EXIT

echo "[ok] backup complete"
echo "[ok] sha256=${sha256}"
echo "[ok] metadata=${meta_path}"
