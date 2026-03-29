#!/usr/bin/env bash
set -euo pipefail

#
# Copyright (c) 2025 Coyote3 Project Authors
# All rights reserved.
#
# This source file is part of the Coyote3 codebase.
# The Coyote3 project provides a framework for genomic data analysis,
# interpretation, reporting, and clinical diagnostics.
#
# Unauthorized use, distribution, or modification of this software or its
# components is strictly prohibited without prior written permission from
# the copyright holders.
#
#

echo "Starting Coyote3 Staging Deployment..."

SCRIPT_PATH="$(realpath "$0")"
APP_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"
COMPOSE_FILE="$APP_DIR/deploy/compose/docker-compose.stage.yml"
ENV_FILE="$APP_DIR/.coyote3_stage_env"
COMPOSE_WRAPPER="$APP_DIR/scripts/compose-with-version.sh"

if [[ -f "$ENV_FILE" ]]; then
    echo ".coyote3_stage_env file found. Loading environment variables..."
    set -a
    # shellcheck disable=SC1090
    source "$ENV_FILE"
    set +a
else
    echo "No .coyote3_stage_env file found in project root."
    read -r -p "Enter the file path to load environment variables or type N/No to continue without: " env_path
    if [[ "$env_path" =~ ^([Nn]|[Nn][Oo])$ ]]; then
        echo "Continuing without environment variables."
    elif [[ -f "$env_path" ]]; then
        echo "File found at $env_path. Loading environment variables..."
        ENV_FILE="$env_path"
        set -a
        # shellcheck disable=SC1090
        source "$env_path"
        set +a
    else
        echo "File not found at $env_path. Exiting."
        exit 1
    fi
fi

COYOTE3_VERSION="$(python3 "$APP_DIR/coyote/__version__.py")"
export COYOTE3_VERSION
echo "Deploying Coyote3 version: ${COYOTE3_VERSION}-stage"

GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export GIT_COMMIT BUILD_TIME
echo "Git commit: $GIT_COMMIT"
echo "Build time:  $BUILD_TIME"

if ! docker network inspect coyote3-stage-net >/dev/null 2>&1; then
    echo "Creating external docker network: coyote3-stage-net"
    docker network create coyote3-stage-net >/dev/null
fi

SERVICES="$("$COMPOSE_WRAPPER" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" config --services | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
echo "Environment: staging"
echo "Compose file: $COMPOSE_FILE"
echo "Env file: $ENV_FILE"
echo "Services: $SERVICES"
"$COMPOSE_WRAPPER" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

echo "Deployment Complete!"
stage_host="${COYOTE3_STAGE_HOST:-localhost}"
echo "UI:  http://${stage_host}:${COYOTE3_STAGE_WEB_PORT:-8005}${SCRIPT_NAME:-/coyote3}"
echo "API: http://${stage_host}:${COYOTE3_STAGE_API_PORT:-8006}"
