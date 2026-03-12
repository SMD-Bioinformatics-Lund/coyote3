#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Create required external Docker volumes for Mongo persistence.

Usage:
  scripts/create_external_mongo_volumes.sh [all|prod|dev|portable]

Defaults to: all
EOF
}

target="${1:-all}"
if [[ "$target" == "-h" || "$target" == "--help" ]]; then
  usage
  exit 0
fi

create_volume() {
  local name="$1"
  if docker volume inspect "$name" >/dev/null 2>&1; then
    echo "[ok] volume already exists: $name"
  else
    docker volume create "$name" >/dev/null
    echo "[ok] volume created: $name"
  fi
}

case "$target" in
  all)
    create_volume "${COYOTE3_MONGO_VOLUME:-coyote3-prod-mongo-data}"
    create_volume "${COYOTE3_DEV_MONGO_VOLUME:-coyote3-dev-mongo-data}"
    create_volume "${COYOTE3_PORTABLE_MONGO_VOLUME:-coyote3-portable-mongo-data}"
    ;;
  prod)
    create_volume "${COYOTE3_MONGO_VOLUME:-coyote3-prod-mongo-data}"
    ;;
  dev)
    create_volume "${COYOTE3_DEV_MONGO_VOLUME:-coyote3-dev-mongo-data}"
    ;;
  portable)
    create_volume "${COYOTE3_PORTABLE_MONGO_VOLUME:-coyote3-portable-mongo-data}"
    ;;
  *)
    echo "[error] invalid target: $target"
    usage
    exit 2
    ;;
esac

echo "[done] external Mongo volume setup complete"
