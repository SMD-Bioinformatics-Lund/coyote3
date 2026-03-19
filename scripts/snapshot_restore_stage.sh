#!/usr/bin/env bash
set -euo pipefail

# Stage wrapper around snapshot_restore_dev.sh with stage defaults.
# Required arg is still passed through: --source-db <name>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
stage_port="${COYOTE3_STAGE_MONGO_PORT:-47017}"
if [[ -n "${MONGO_APP_USER:-}" && -n "${MONGO_APP_PASSWORD:-}" ]]; then
  default_stage_uri="mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:${stage_port}/coyote3_stage?authSource=coyote3_stage"
else
  default_stage_uri="mongodb://localhost:${stage_port}"
fi

exec "$SCRIPT_DIR/snapshot_restore_dev.sh" \
  --target-uri "${TARGET_URI:-$default_stage_uri}" \
  --target-db "${TARGET_DB:-coyote3_stage}" \
  "$@"
