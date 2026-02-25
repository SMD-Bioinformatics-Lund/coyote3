#!/usr/bin/env bash
set -euo pipefail

SCRIPT_PATH="$(realpath "$0")"
APP_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"

export COYOTE3_VERSION="$(python3 "$APP_DIR/coyote/__version__.py")"
echo "Using COYOTE3_VERSION=${COYOTE3_VERSION}"

exec docker-compose "$@"
