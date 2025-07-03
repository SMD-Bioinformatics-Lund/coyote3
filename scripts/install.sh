#!/bin/bash

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
# This script builds and runs the Coyote3 Docker container with custom settings.
# It automatically sources environment variables, stops any running container,
# and starts the app with a fresh image.
# ------------------------------------------

echo "Starting Coyote3 Deployment..."

# Source the .env file if it exists
if [[ -f ".coyote3_env" ]]; then
    echo ".coyote3_env file found. Loading environment variables..."
    source .coyote3_env
else
    echo "No .coyote3_env file found in project root. Continuing without it."
fi

# Set application context path (adjust if hosted under a different subpath)
SCRIPT_NAME="/coyote3"

# Read the application version from Python module
SCRIPT_PATH=$(realpath "$0")
APP_DIR=$(dirname "$(dirname "$SCRIPT_PATH")")
version=$(python "$APP_DIR/coyote/__version__.py")
echo "Deploying Coyote3 version: $version"

# Define Docker image and container names
image_name="coyote3:$version"
container_name="coyote3_app"

# Optional: Uncomment this to force rebuild without cache
# echo "Building Docker image: $image_name"
docker build --no-cache --network host --target $container_name -t "$image_name" .

# Stop and remove any existing container with the same name
echo "Stopping and removing existing container (if any)..."
docker stop "$container_name" >/dev/null 2>&1
docker rm "$container_name" >/dev/null 2>&1

# build redis image if it does not exist
docker inspect redis_coyote3 >/dev/null 2>&1 \
    && docker start redis_coyote3 \
    || docker run -d --name redis_coyote3 --network coyote3-net --restart=unless-stopped -p 5817:6379 ramsainanduri/redis:7.4.3


# Start the Docker container
echo "Starting Docker container: $container_name"
docker run \
    -e FLASK_MONGO_HOST=${FLASK_MONGO_HOST} \
    -e FLASK_MONGO_PORT=${FLASK_MONGO_PORT} \
    -e FLASK_DEBUG=${FLASK_DEBUG} \
    -e SCRIPT_NAME="${SCRIPT_NAME}" \
    -e FLASK_SECRET_KEY="${SECRET_KEY}" \
    -e TZ='Europe/Stockholm' \
    --dns "${APP_DNS}" \
    -v /data/coyote3/logs:/app/logs \
    -v /access:/access \
    -v /media:/media \
    -v /data:/data \
    -v /fs1:/fs1 \
    -v /mnt/clarity:/mnt/clarity \
    -p "${PORT_NBR}:8000" \
    --name "$container_name" \
    --restart=always \
    --network coyote3-net \
    -d \
    "$image_name"

# Final message
echo "Deployment Complete!"
echo "Access Coyote3 at: https://mtlucmds1.lund.skane.se$SCRIPT_NAME"

