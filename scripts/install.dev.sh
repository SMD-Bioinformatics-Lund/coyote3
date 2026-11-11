
#!/usr/bin/env bash
set -Eeuo pipefail

#
# Copyright (c) 2025 Coyote3 Project Authors
# All rights reserved.
#
# Coyote3 Development Deployment Script
#

# ------------------------------------------
# Configuration
# ------------------------------------------

DEFAULT_ENV_FILE=".coyote3_dev_env"
ENV_FILE=""

container_name="coyote3_dev_app"
redis_container="redis_coyote3_dev"
docker_network="coyote3-dev-net"

redis_port=8820
redis_image="ramsainanduri/redis:7.4.3"

backup_container=""
rollback_needed=false
previous_container_running=false

# ------------------------------------------
# Utilities
# ------------------------------------------

log() {
    printf '[INFO] %s\n' "$*"
}

warn() {
    printf '[WARN] %s\n' "$*" >&2
}

die() {
    printf '[ERROR] %s\n' "$*" >&2
    exit 1
}

container_exists() {
    docker container inspect "$1" >/dev/null 2>&1
}

container_running() {
    [[ "$(docker inspect -f '{{.State.Running}}' "$1")" == "true" ]]
}

usage() {
    cat <<EOF
Coyote3 Development Deployment

Usage: $(basename "$0") [-e ENV_FILE]

Options:
  -e, --env-file FILE   Specify environment file
  -h, --help            Show help

Examples:
  $(basename "$0")
  $(basename "$0") -e .coyote3_dev_env
  $(basename "$0") --env-file /path/to/development.env
EOF
}

# ------------------------------------------
# Parse arguments
# ------------------------------------------

while [[ $# -gt 0 ]]; do
    case "$1" in
        -e|--env-file)
            [[ $# -ge 2 && -n "$2" ]] ||
                die "Missing environment file path."

            ENV_FILE="$2"
            shift 2
            ;;
        -h|--help)
            usage
            exit 0
            ;;
        *)
            die "Unknown option: $1"
            ;;
    esac
done

# ------------------------------------------
# Resolve project directory dynamically
# ------------------------------------------

# Assumes:
# coyote3/
# ├── scripts/
# │   └── install.dev.sh
# ├── coyote/
# ├── config/
# ├── config.py
# └── Dockerfile.dev

SCRIPT_DIR="$(
    cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &&
    pwd -P
)"

APP_DIR="$(
    cd -- "$SCRIPT_DIR/.." &&
    pwd -P
)"

cd "$APP_DIR"

log "Project directory: $APP_DIR"

# ------------------------------------------
# Resolve environment file
# ------------------------------------------

if [[ -z "$ENV_FILE" ]]; then
    ENV_FILE="$APP_DIR/$DEFAULT_ENV_FILE"
elif [[ "$ENV_FILE" != /* ]]; then
    # Resolve relative paths from the caller's
    # working directory, not the project root.
    # Preserve the path before resolving it.
    ENV_FILE="$OLDPWD/$ENV_FILE"
fi

[[ -f "$ENV_FILE" ]] ||
    die "Environment file not found: $ENV_FILE"

ENV_FILE="$(realpath "$ENV_FILE")"

log "Using environment file: $ENV_FILE"

# ------------------------------------------
# Load environment configuration
# ------------------------------------------

# Source only trusted Bash configuration files.
# All variables are exported for Docker forwarding.
set -a
source "$ENV_FILE"
set +a

# Build Docker arguments from variables
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

# ------------------------------------------
# Validate environment configuration
# ------------------------------------------

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
    [[ -n "${!var:-}" ]] ||
        die "Missing required variable: $var"
done

[[ "$PORT_NBR" =~ ^[0-9]+$ ]] ||
    die "PORT_NBR must be numeric."

(( 10#$PORT_NBR >= 1 && 10#$PORT_NBR <= 65535 )) ||
    die "Invalid PORT_NBR: $PORT_NBR"

SCRIPT_NAME="${SCRIPT_NAME:-/coyote3_dev}"

[[ "$SCRIPT_NAME" == /* ]] ||
    die "SCRIPT_NAME must start with /."

# Preserve SECRET_KEY -> FLASK_SECRET_KEY mapping.
# COYOTE3_FERNET_KEY stays in the environment file.
export FLASK_SECRET_KEY="$SECRET_KEY"

# ------------------------------------------
# Validate required project files
# ------------------------------------------

required_paths=(
    "$APP_DIR/Dockerfile.dev"
    "$APP_DIR/coyote"
    "$APP_DIR/coyote/__version__.py"
    "$APP_DIR/config"
    "$APP_DIR/config.py"
    "$APP_DIR/logging_setup.py"
    "$APP_DIR/gunicorn.conf.py"
    "$APP_DIR/docs"
    "$APP_DIR/LICENSE.txt"
    "$APP_DIR/README.md"
    "$APP_DIR/CHANGELOG.md"
)

for path in "${required_paths[@]}"; do
    [[ -e "$path" ]] ||
        die "Required project path not found: $path"
done

# ------------------------------------------
# Resolve application version
# ------------------------------------------

version="$(python "$APP_DIR/coyote/__version__.py")"

[[ -n "$version" ]] ||
    die "Could not determine application version."

version="${version}-dev"
image_name="coyote3:$version"

GIT_COMMIT="$(
    git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null ||
    echo unknown
)"

BUILD_TIME="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"

echo
echo "----------------------------------------"
echo "Coyote3 Development Deployment"
echo "----------------------------------------"
echo "Project:    $APP_DIR"
echo "Version:    $version"
echo "Image:      $image_name"
echo "Container:  $container_name"
echo "Network:    $docker_network"
echo "Port:       $PORT_NBR"
echo "Path:       $SCRIPT_NAME"
echo "Commit:     $GIT_COMMIT"
echo "Build time: $BUILD_TIME"
echo "----------------------------------------"

# ------------------------------------------
# Validate Docker
# ------------------------------------------

command -v docker >/dev/null 2>&1 ||
    die "Docker is not installed."

docker info >/dev/null 2>&1 ||
    die "Docker daemon is unavailable."

# ------------------------------------------
# Prevent simultaneous deployments
# ------------------------------------------

command -v flock >/dev/null 2>&1 ||
    die "flock is required."

exec 9>/tmp/coyote3-dev-deployment.lock

flock -n 9 ||
    die "Another development deployment is running."

# ------------------------------------------
# Ensure Docker network exists
# ------------------------------------------

if ! docker network inspect "$docker_network" >/dev/null 2>&1; then

    log "Creating Docker network: $docker_network"

    docker network create "$docker_network"
fi

# ------------------------------------------
# Build Docker image
# ------------------------------------------

log "Building Docker image: $image_name"

docker build \
    --no-cache \
    --network host \
    --build-arg GIT_COMMIT="$GIT_COMMIT" \
    --build-arg BUILD_TIME="$BUILD_TIME" \
    --target "$container_name" \
    -t "$image_name" \
    -f "$APP_DIR/Dockerfile.dev" \
    "$APP_DIR"

log "Docker image built successfully."

# ------------------------------------------
# Start Redis
# ------------------------------------------

log "Checking Redis container..."

if container_exists "$redis_container"; then

    if ! container_running "$redis_container"; then
        log "Starting existing Redis container..."
        docker start "$redis_container"
    else
        log "Redis is already running."
    fi

    network_attached="$(
        docker inspect \
            --format "{{if index .NetworkSettings.Networks \"$docker_network\"}}true{{else}}false{{end}}" \
            "$redis_container"
    )"

    if [[ "$network_attached" != "true" ]]; then

        log "Connecting Redis to $docker_network..."

        docker network connect \
            "$docker_network" \
            "$redis_container"
    fi

else
    log "Creating Redis container..."

    docker run -d \
        --name "$redis_container" \
        --network "$docker_network" \
        --restart unless-stopped \
        -p "${redis_port}:6379" \
        "$redis_image"
fi

# ------------------------------------------
# Rollback handler
# ------------------------------------------

rollback() {
    local error_code=$?

    trap - ERR
    set +e

    warn "Deployment failed (exit code $error_code)."

    if [[ "$rollback_needed" == true ]]; then

        warn "Rolling back development deployment..."

        if container_exists "$container_name"; then
            docker rm -f "$container_name" ||
                warn "Could not remove failed container."
        fi

        if [[ -n "$backup_container" ]] &&
           container_exists "$backup_container"; then

            if docker rename \
                "$backup_container" \
                "$container_name"; then

                if [[ "$previous_container_running" == true ]]; then

                    if docker start "$container_name"; then
                        log "Previous development container restored."
                    else
                        warn "Previous container failed to start."
                    fi

                else
                    log "Previous stopped container restored."
                fi

            else
                warn "Could not restore previous container name."
                warn "Backup container: $backup_container"
            fi

        else
            warn "No previous container available for rollback."
        fi
    fi

    exit "$error_code"
}

trap rollback ERR

# ------------------------------------------
# Preserve existing development container
# ------------------------------------------

if container_exists "$container_name"; then

    backup_container="${container_name}_backup_$(date -u +%Y%m%d%H%M%S)_$$"

    if container_running "$container_name"; then
        previous_container_running=true
    fi

    log "Preserving existing container..."

    docker rename \
        "$container_name" \
        "$backup_container"

    rollback_needed=true

    if [[ "$previous_container_running" == true ]]; then
        docker stop "$backup_container"
    fi
fi

# ------------------------------------------
# Start new development container
# ------------------------------------------

log "Starting development container..."

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
    -v "$APP_DIR/coyote:/app/coyote" \
    -v "$APP_DIR/config:/app/config" \
    -v "$APP_DIR/config.py:/app/config.py" \
    -v "$APP_DIR/logging_setup.py:/app/logging_setup.py" \
    -v "$APP_DIR/gunicorn.conf.py:/app/gunicorn.conf.py" \
    -v "$APP_DIR/docs:/app/docs" \
    -v "$APP_DIR/LICENSE.txt:/app/LICENSE.txt" \
    -v "$APP_DIR/README.md:/app/README.md" \
    -v "$APP_DIR/CHANGELOG.md:/app/CHANGELOG.md" \
    -p "${PORT_NBR}:8000" \
    --name "$container_name" \
    --restart always \
    --network "$docker_network" \
    "$image_name"

# ------------------------------------------
# Tailwind CSS development watcher
# ------------------------------------------

tailwind_container="coyote3_dev_tailwind"

log "Starting Tailwind CSS watcher..."

if docker container inspect "$tailwind_container" >/dev/null 2>&1; then
    docker rm -f "$tailwind_container"
fi

docker run -d \
    --name "$tailwind_container" \
    --network "$docker_network" \
    --restart unless-stopped \
    -v "$APP_DIR:/app" \
    -v coyote3_dev_node_modules:/app/node_modules \
    -w /app \
    node:20-alpine \
    sh -c 'npm install && exec npx @tailwindcss/cli \
        -i ./coyote/static/css/tailwind.input.css \
        -o ./coyote/static/css/tailwind.css \
        --watch=always'

# ------------------------------------------
# Verify application startup
# ------------------------------------------

log "Verifying container startup..."

sleep 5

if ! container_running "$container_name"; then

    warn "Development container is not running."
    docker logs --tail 30 "$container_name" >&2 || true

    false
fi


# ------------------------------------------
# Deployment successful
# ------------------------------------------

rollback_needed=false
trap - ERR

if [[ -n "$backup_container" ]] &&
   container_exists "$backup_container"; then

    log "Removing previous development container."
    docker rm "$backup_container" || true
fi

echo
echo "----------------------------------------"
echo "Coyote3 Development Deployment Complete"
echo "----------------------------------------"
echo "Project:    $APP_DIR"
echo "Version:    $version"
echo "Container:  $container_name"
echo "Port:       $PORT_NBR"
echo "URL:        https://mtlucmds1.lund.skane.se${SCRIPT_NAME}"
echo "----------------------------------------"
