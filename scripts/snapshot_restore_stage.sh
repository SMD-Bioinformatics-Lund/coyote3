#!/usr/bin/env bash
set -euo pipefail

# Stage wrapper around snapshot_restore_dev.sh with stage defaults.
# Required arg is still passed through: --source-db <name>

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

exec "$SCRIPT_DIR/snapshot_restore_dev.sh" \
  --target-uri "${TARGET_URI:-mongodb://localhost:47017}" \
  --target-db "${TARGET_DB:-coyote3_stage}" \
  "$@"
