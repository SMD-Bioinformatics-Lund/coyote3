
#!/usr/bin/env bash
set -Eeuo pipefail

#
# Copyright (c) 2025 Coyote3 Project Authors
# All rights reserved.
#
# Coyote3 Production Deployment Script
#

DEFAULT_ENV_FILE=".coyote3_env"
ENV_FILE=""

container_name="coyote3_app"
redis_container="redis_coyote3"
docker_network="coyote3-net"

usage() {
    echo "Usage: $(basename "$0") [-e ENV_FILE]"
    echo
    echo "Options:"
    echo "  -e, --env-file FILE   Specify environment file"
    echo "  -h, --help            Show help"
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--env-file)
            [[ $# -ge 2 && -n "$2" ]] || {
                echo "ERROR: Missing environment file."
                exit 1
            }
            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: Unknown option: $1"
            usage
            exit 1
            ;;
    esac
done

# Project directory
SCRIPT_PATH="$(realpath "$0")"
APP_DIR="$(dirname "$(dirname "$SCRIPT_PATH")")"
cd "$APP_DIR"

# Resolve environment file
ENV_FILE="${ENV_FILE:-$DEFAULT_ENV_FILE}"

[[ -f "$ENV_FILE" ]] || {
    echo "ERROR: Environment file not found: $ENV_FILE"
    exit 1
}

ENV_FILE="$(realpath "$ENV_FILE")"

echo "Using environment file: $ENV_FILE"

# Load environment variables
# Only source trusted configuration files.
set -a
source "$ENV_FILE"
set +a

# Build Docker environment arguments from variables
# explicitly assigned in the environment file.
docker_env_args=()
declare -A seen_vars=()

while IFS= read -r line || [[ -n "$line" ]]; do
    if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?([A-Za-z_][A-Za-z0-9_]*)= ]]; then
        var="${BASH_REMATCH[2]}"

        if [[ -z "${seen_vars[$var]:-}" ]]; then
            docker_env_args+=(-e "$var")
            seen_vars["$var"]=1
        fi
    fi
done < "$ENV_FILE"

# Validate required configuration
required_vars=(
    SECRET_KEY
    COYOTE3_FERNET_KEY
    FLASK_MONGO_HOST
    FLASK_MONGO_PORT
    COYOTE3_DB_NAME
    CACHE_REDIS_URL
    APP_DNS
    PORT_NBR
)

for var in "${required_vars[@]}"; do
    [[ -n "${!var:-}" ]] || {
        echo "ERROR: Missing required variable: $var"
        exit 1
    }
done

[[ "${FLASK_DEBUG:-}" == "0" ]] || {
    echo "ERROR: FLASK_DEBUG must be 0."
    exit 1
}

[[ "${DEVELOPMENT:-}" == "0" ]] || {
    echo "ERROR: DEVELOPMENT must be 0."
    exit 1
}

[[ "${TESTING:-}" == "0" ]] || {
    echo "ERROR: TESTING must be 0."
    exit 1
}

SCRIPT_NAME="${SCRIPT_NAME:-/coyote3}"

# Validate port
if [[ ! "$PORT_NBR" =~ ^[0-9]+$ ]] ||
   (( 10#$PORT_NBR < 1 || 10#$PORT_NBR > 65535 )); then
    echo "ERROR: Invalid PORT_NBR: $PORT_NBR"
    exit 1
fi

# Application version
version="$(python "$APP_DIR/coyote/__version__.py")"
image_name="coyote3:$version"

GIT_COMMIT="$(git rev-parse --short HEAD 2>/dev/null || echo unknown)"
BUILD_TIME="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

# Preserve existing SECRET_KEY -> FLASK_SECRET_KEY mapping.
export FLASK_SECRET_KEY="$SECRET_KEY"

echo "----------------------------------------"
echo "Coyote3 Production Deployment"
echo "----------------------------------------"
echo "Version:    $version"
echo "Image:      $image_name"
echo "Container:  $container_name"
echo "Port:       $PORT_NBR"
echo "Path:       $SCRIPT_NAME"
echo "Commit:     $GIT_COMMIT"
echo "----------------------------------------"

# Validate Docker
docker info >/dev/null 2>&1 || {
    echo "ERROR: Docker is unavailable."
    exit 1
}

# Ensure network exists
if ! docker network inspect "$docker_network" >/dev/null 2>&1; then
    docker network create "$docker_network"
fi

# Build application image
echo "Building Docker image..."

docker build \
    --no-cache \
    --network host \
    --build-arg GIT_COMMIT="$GIT_COMMIT" \
    --build-arg BUILD_TIME="$BUILD_TIME" \
    --target "$container_name" \
    -t "$image_name" \
    .

# Start Redis if required
echo "Checking Redis..."

if docker container inspect "$redis_container" >/dev/null 2>&1; then
    if [[ "$(docker inspect -f '{{.State.Running}}' "$redis_container")" != "true" ]]; then
        docker start "$redis_container"
    fi

    if [[ "$(docker inspect -f "{{if index .NetworkSettings.Networks \"$docker_network\"}}true{{else}}false{{end}}" "$redis_container")" != "true" ]]; then
        docker network connect "$docker_network" "$redis_container"
    fi
else
    docker run -d \
        --name "$redis_container" \
        --network "$docker_network" \
        --restart unless-stopped \
        -p 5817:6379 \
        ramsainanduri/redis:7.4.3
fi

# Preserve existing production container for rollback
backup_container=""
rollback_needed=false

rollback() {
    local error_code=$?
    trap - ERR
    set +e

    echo "ERROR: Deployment failed."

    if [[ "$rollback_needed" == true ]]; then
        docker rm -f "$container_name" >/dev/null 2>&1 || true

        if [[ -n "$backup_container" ]] &&
           docker container inspect "$backup_container" >/dev/null 2>&1; then

            echo "Restoring previous production container..."

            if docker rename "$backup_container" "$container_name"; then
                if docker start "$container_name"; then
                    echo "Previous production container restored."
                else
                    echo "ERROR: Rollback container failed to start."
                fi
            else
                echo "ERROR: Unable to rename backup container."
            fi
        fi
    fi

    exit "$error_code"
}

trap rollback ERR

if docker container inspect "$container_name" >/dev/null 2>&1; then
    backup_container="${container_name}_backup_$(date +%Y%m%d%H%M%S)_$$"

    echo "Preserving previous production container..."

    docker rename "$container_name" "$backup_container"
    rollback_needed=true
    docker stop "$backup_container"
fi

# Start new application
echo "Starting production container..."

rollback_needed=true

docker run -d \
    "${docker_env_args[@]}" \
    -e FLASK_SECRET_KEY \
    -e SCRIPT_NAME="$SCRIPT_NAME" \
    -e TZ="Europe/Stockholm" \
    -e GIT_COMMIT="$GIT_COMMIT" \
    -e BUILD_TIME="$BUILD_TIME" \
    --dns "$APP_DNS" \
    -v /data/coyote3/logs:/app/logs \
    -v /access:/access \
    -v /media:/media \
    -v /data:/data \
    -v /fs1:/fs1 \
    -v /mnt/clarity:/mnt/clarity \
    -p "${PORT_NBR}:8000" \
    --name "$container_name" \
    --restart always \
    --network "$docker_network" \
    "$image_name"

# Basic startup verification
echo "Verifying application startup..."

sleep 5

if [[ "$(docker inspect -f '{{.State.Running}}' "$container_name")" != "true" ]]; then
    echo "ERROR: Application container is not running."
    false
fi

# Success: remove previous container
rollback_needed=false
trap - ERR

if [[ -n "$backup_container" ]]; then
    docker rm "$backup_container" || true
fi

echo "----------------------------------------"
echo "Coyote3 Production Deployment Complete"
echo "----------------------------------------"
echo "Version:    $version"
echo "Container:  $container_name"
echo "Port:       $PORT_NBR"
echo "URL:        https://mtlucmds1.lund.skane.se${SCRIPT_NAME}"
echo "----------------------------------------"
