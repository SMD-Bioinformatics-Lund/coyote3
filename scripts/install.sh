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

# ------------------------------------------
# Coyote3 Deployment Script
# ------------------------------------------
# This script deploys the Coyote3 stack using docker compose.
# It exports version/build metadata and starts all services defined in
# deploy/compose/docker-compose.yml.
# ------------------------------------------

echo "Starting Coyote3 Production Deployment..."

# Resolve repository root from this script location
SCRIPT_PATH="$(realpath "$0")"
APP_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"
COMPOSE_FILE="$APP_DIR/deploy/compose/docker-compose.yml"
ENV_FILE="$APP_DIR/.coyote3_env"
COMPOSE_WRAPPER="$APP_DIR/scripts/compose-with-version.sh"
PROFILE_ARGS=()

if [[ "${USE_LOCAL_MONGO:-0}" == "1" ]]; then
    PROFILE_ARGS=(--profile with-mongo)
fi

# Source env file (mandatory for production deploy)
if [[ ! -f "$ENV_FILE" ]]; then
    echo "ERROR: .coyote3_env is required for production deployment: $ENV_FILE" >&2
    echo "Create it from deploy/env/example.prod.env and set real values." >&2
    exit 1
fi
echo ".coyote3_env file found. Loading environment variables..."
set -a
# shellcheck disable=SC1090
source "$ENV_FILE"
set +a

# Read and export compose build/runtime metadata
if [[ -z "${COYOTE3_VERSION:-}" ]]; then
    COYOTE3_VERSION="$(python3 "$APP_DIR/coyote/__version__.py")"
    export COYOTE3_VERSION
fi
if [[ -z "${COYOTE3_VERSION:-}" ]]; then
    echo "ERROR: COYOTE3_VERSION is required for production deployment." >&2
    exit 1
fi
echo "Deploying Coyote3 version: $COYOTE3_VERSION"

# GIT Commit and build time
GIT_COMMIT=$(git rev-parse --short HEAD 2>/dev/null || echo "unknown")
BUILD_TIME=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
export GIT_COMMIT BUILD_TIME
echo "Git commit: $GIT_COMMIT"
echo "Build time:  $BUILD_TIME"

# Ensure external compose network exists
if ! docker network inspect coyote3-net >/dev/null 2>&1; then
    echo "Creating external docker network: coyote3-net"
    docker network create coyote3-net >/dev/null
fi

SERVICES="$("$COMPOSE_WRAPPER" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" config --services | tr '\n' ' ' | sed 's/[[:space:]]*$//')"
echo "Environment: production"
echo "Compose file: $COMPOSE_FILE"
echo "Env file: $ENV_FILE"
if [[ "${USE_LOCAL_MONGO:-0}" == "1" ]]; then
    echo "Profile: with-mongo (enabled)"
fi
echo "Services: $SERVICES"
"$COMPOSE_WRAPPER" --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "${PROFILE_ARGS[@]}" up -d --build

# Final message
echo "Deployment Complete!"
echo "UI:  https://mtlucmds1.lund.skane.se/coyote3"
echo "DOC: http://mtlucmds1.lund.skane.se:5821"
echo "API: http://mtlucmds1.lund.skane.se:5818"
