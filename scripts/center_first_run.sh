#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Run first-time center bootstrap end-to-end:
preflight -> compose up -> admin bootstrap -> baseline seed -> ingest check.

Usage:
  scripts/center_first_run.sh \
    --env-file <path> \
    --compose-file <path> \
    [--compose-profile <name>] \
    [--with-mongo] \
    [--with-proxy] \
    --api-base-url <url> \
    --admin-username <username> \
    --admin-email <email> \
    --admin-password <password> \
    [--seed-file <path>] \
    [--seed-data-pack <path>] \
    [--use-default-seed-data-pack] \
    [--yaml-file <path>] \
    [--with-optional] \
    [--skip-existing] \
    [--strict-no-retry] \
    [--teardown]
USAGE
}

ENV_FILE=""
COMPOSE_FILE=""
COMPOSE_PROFILES=()
API_BASE_URL=""
ADMIN_USERNAME=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
MONGO_URI_OVERRIDE=""
SEED_FILE="tests/fixtures/db_dummy/all_collections_dummy"
SEED_DATA_PACK=""
YAML_FILE="tests/data/ingest_demo/generic_case_control.yaml"
WITH_OPTIONAL=0
SKIP_EXISTING=1
STRICT_NO_RETRY=0
TEARDOWN=0
PYTHON_BIN="${PYTHON_BIN:-}"

MONGO_URI=""
COYOTE3_DB=""
MONGO_ROOT_USERNAME=""
MONGO_ROOT_PASSWORD=""
MONGO_APP_USER=""
MONGO_APP_PASSWORD=""

extract_env() {
  local key="$1"
  (grep -E "^${key}=" "$ENV_FILE" || true) | tail -n1 | cut -d'=' -f2- | tr -d "'\""
}

clear_shell_overrides_from_env_file() {
  if [[ ! -f "$ENV_FILE" ]]; then
    return 0
  fi

  local line=""
  local key=""
  while IFS= read -r line || [[ -n "$line" ]]; do
    [[ -z "$line" ]] && continue
    [[ "$line" =~ ^[[:space:]]*# ]] && continue
    [[ "$line" != *=* ]] && continue
    key="${line%%=*}"
    key="${key#"${key%%[![:space:]]*}"}"
    key="${key%"${key##*[![:space:]]}"}"
    [[ -z "$key" ]] && continue
    unset "$key" || true
  done <"$ENV_FILE"
}

resolve_python_bin() {
  if [[ -n "$PYTHON_BIN" ]]; then
    return 0
  fi
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
    exit 2
  fi
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --env-file) ENV_FILE="$2"; shift 2 ;;
      --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
      --compose-profile) COMPOSE_PROFILES+=("$2"); shift 2 ;;
      --with-mongo) COMPOSE_PROFILES+=("with-mongo"); shift ;;
      --with-proxy) COMPOSE_PROFILES+=("with-proxy"); shift ;;
      --api-base-url) API_BASE_URL="$2"; shift 2 ;;
      --admin-username) ADMIN_USERNAME="$2"; shift 2 ;;
      --admin-email) ADMIN_EMAIL="$2"; shift 2 ;;
      --admin-password) ADMIN_PASSWORD="$2"; shift 2 ;;
      --mongo-uri) MONGO_URI_OVERRIDE="$2"; shift 2 ;;
      --seed-file) SEED_FILE="$2"; shift 2 ;;
      --seed-data-pack) SEED_DATA_PACK="$2"; shift 2 ;;
      --use-default-seed-data-pack) SEED_DATA_PACK="tests/data/seed_data"; shift ;;
      --yaml-file) YAML_FILE="$2"; shift 2 ;;
      --with-optional) WITH_OPTIONAL=1; shift ;;
      --skip-existing) SKIP_EXISTING=1; shift ;;
      --strict-no-retry) STRICT_NO_RETRY=1; shift ;;
      --teardown) TEARDOWN=1; shift ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
    esac
  done
}

validate_args() {
  if [[ -z "$ENV_FILE" || -z "$COMPOSE_FILE" || -z "$API_BASE_URL" || -z "$ADMIN_USERNAME" || -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
    echo "ERROR: required arguments are missing" >&2
    usage
    exit 2
  fi

  if [[ -n "$SEED_DATA_PACK" && ! -d "$SEED_DATA_PACK" ]]; then
    echo "ERROR: seed data pack directory not found: $SEED_DATA_PACK" >&2
    exit 2
  fi

  if [[ "$STRICT_NO_RETRY" -eq 1 && "$SKIP_EXISTING" -eq 0 ]]; then
    echo "ERROR: --strict-no-retry is incompatible with default center_first_run ordering." >&2
    echo "Reason: bootstrap_local_admin runs before collection seeding and pre-creates RBAC docs" >&2
    echo "(permissions/roles), so strict seeding fails on duplicate keys." >&2
    echo "Use one of:" >&2
    echo "  1) remove --strict-no-retry (default single retry behavior), or" >&2
    echo "  2) keep --strict-no-retry and add --skip-existing." >&2
    exit 2
  fi
}

resolve_version() {
  local env_file_version=""
  env_file_version="$(extract_env COYOTE3_VERSION)"

  if [[ -n "$env_file_version" ]]; then
    export COYOTE3_VERSION="$env_file_version"
    echo "[info] using COYOTE3_VERSION from env file: $COYOTE3_VERSION"
    return 0
  fi

  if [[ -n "${COYOTE3_VERSION:-}" ]]; then
    return 0
  fi
  if [[ ! -f "coyote/__version__.py" ]]; then
    return 0
  fi

  local resolved_version=""
  if resolved_version="$("$PYTHON_BIN" coyote/__version__.py 2>/dev/null)"; then
    resolved_version="$(echo "$resolved_version" | tr -d "[:space:]")"
    if [[ -n "$resolved_version" ]]; then
      export COYOTE3_VERSION="$resolved_version"
      echo "[info] COYOTE3_VERSION not set; using detected version: $COYOTE3_VERSION"
    fi
  fi
}

load_env_runtime_values() {
  MONGO_URI="$(extract_env MONGO_URI)"
  COYOTE3_DB="$(extract_env COYOTE3_DB)"
  MONGO_ROOT_USERNAME="$(extract_env MONGO_ROOT_USERNAME)"
  MONGO_ROOT_PASSWORD="$(extract_env MONGO_ROOT_PASSWORD)"
  MONGO_APP_USER="$(extract_env MONGO_APP_USER)"
  MONGO_APP_PASSWORD="$(extract_env MONGO_APP_PASSWORD)"

  if [[ -z "$MONGO_URI" || -z "$COYOTE3_DB" ]]; then
    echo "ERROR: ENV file must contain MONGO_URI and COYOTE3_DB" >&2
    exit 2
  fi

  if [[ -n "$MONGO_URI_OVERRIDE" ]]; then
    MONGO_URI="$MONGO_URI_OVERRIDE"
  fi
}

validate_profile_requirements() {
  local profile=""
  local has_with_mongo=1
  for profile in "${COMPOSE_PROFILES[@]}"; do
    if [[ "$profile" == "with-mongo" ]]; then
      has_with_mongo=0
      break
    fi
  done

  if [[ "$MONGO_URI" =~ @coyote3_mongo:27017/ ]] && [[ "$has_with_mongo" -ne 0 ]]; then
    echo "ERROR: MONGO_URI points to coyote3_mongo, but --compose-profile with-mongo was not provided." >&2
    echo "Add: --compose-profile with-mongo" >&2
    exit 2
  fi
}

rewrite_internal_mongo_uri_for_host() {
  if [[ ! "$MONGO_URI" =~ @coyote3(_.*)?_mongo:27017/ ]]; then
    return 0
  fi

  local stage_mongo_port dev_mongo_port test_mongo_port prod_mongo_port target_port
  stage_mongo_port="$(extract_env COYOTE3_STAGE_MONGO_PORT)"
  dev_mongo_port="$(extract_env COYOTE3_DEV_MONGO_PORT)"
  test_mongo_port="$(extract_env COYOTE3_TEST_MONGO_PORT)"
  prod_mongo_port="$(extract_env COYOTE3_MONGO_PORT)"
  target_port="${stage_mongo_port:-${dev_mongo_port:-${test_mongo_port:-${prod_mongo_port:-8008}}}}"
  MONGO_URI="$(echo "$MONGO_URI" | sed -E "s#@[^/]+:27017/#@localhost:${target_port}/#")"
}

bootstrap_mongo_app_user() {
  local stage_port dev_port test_port prod_port target_port admin_uri
  local max_attempts
  stage_port="$(extract_env COYOTE3_STAGE_MONGO_PORT)"
  dev_port="$(extract_env COYOTE3_DEV_MONGO_PORT)"
  test_port="$(extract_env COYOTE3_TEST_MONGO_PORT)"
  prod_port="$(extract_env COYOTE3_MONGO_PORT)"
  target_port="${stage_port:-${dev_port:-${test_port:-${prod_port:-8008}}}}"

  if [[ -z "$MONGO_ROOT_USERNAME" || -z "$MONGO_ROOT_PASSWORD" || -z "$MONGO_APP_USER" || -z "$MONGO_APP_PASSWORD" ]]; then
    echo "ERROR: missing mongo root/app credentials in env file; cannot guarantee app-user authentication." >&2
    echo "Required: MONGO_ROOT_USERNAME, MONGO_ROOT_PASSWORD, MONGO_APP_USER, MONGO_APP_PASSWORD" >&2
    return 2
  fi

  if [[ "$MONGO_ROOT_PASSWORD" == CHANGE_ME* || "$MONGO_APP_PASSWORD" == CHANGE_ME* ]]; then
    echo "ERROR: placeholder Mongo credentials detected (CHANGE_ME*). Set real values in env file." >&2
    return 2
  fi

  admin_uri="mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${target_port}/admin?authSource=admin"
  echo "[step] ensure mongo app user exists and password matches env (with retry)"
  max_attempts=45
  for _attempt in $(seq 1 "$max_attempts"); do
    if PYTHONPATH=. "$PYTHON_BIN" scripts/mongo_bootstrap_users.py \
      --mongo-uri "$admin_uri" \
      --app-db "$COYOTE3_DB" \
      --app-user "$MONGO_APP_USER" \
      --app-password "$MONGO_APP_PASSWORD"; then
      return 0
    fi
    sleep 2
  done

  echo "ERROR: failed to bootstrap Mongo app user after ${max_attempts} attempts." >&2
  echo "Check Mongo root credentials and port (${target_port}) in env file." >&2
  return 2
}

run_preflight() {
  local args=(
    --env-file "$ENV_FILE"
    --compose-file "$COMPOSE_FILE"
    --seed-file "$SEED_FILE"
    --yaml-file "$YAML_FILE"
  )
  if [[ -n "$SEED_DATA_PACK" ]]; then
    args+=(--reference-seed-data "$SEED_DATA_PACK")
  fi
  bash scripts/center_preflight.sh "${args[@]}"
}

start_compose_stack() {
  echo "[step] starting compose stack"
  local compose_args=(--env-file "$ENV_FILE" -f "$COMPOSE_FILE")
  local profile=""
  for profile in "${COMPOSE_PROFILES[@]}"; do
    compose_args+=(--profile "$profile")
  done
  docker compose "${compose_args[@]}" up -d --build

  if [[ "$MONGO_URI" =~ @coyote3_mongo:27017/ ]]; then
    if ! docker compose "${compose_args[@]}" ps coyote3_mongo >/dev/null 2>&1; then
      echo "ERROR: expected coyote3_mongo to be part of the compose stack, but it was not created." >&2
      exit 2
    fi
  fi
}

cleanup() {
  if [[ "$TEARDOWN" -eq 1 ]]; then
    resolved_compose="$(realpath "$COMPOSE_FILE")"
    script_path="$(realpath "$0")"
    app_dir="$(dirname "$(dirname "$script_path")")"
    prod_compose="$(realpath "$app_dir/deploy/compose/docker-compose.yml")"
    if [[ "$resolved_compose" == "$prod_compose" && "${COYOTE3_ALLOW_PROD_VOLUME_PRUNE:-0}" != "1" ]]; then
      echo "ERROR: refusing teardown with volume removal for production compose." >&2
      echo "Set COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1 only when intentional." >&2
      exit 2
    fi
    echo "[step] teardown compose stack"
    local compose_args=(--env-file "$ENV_FILE" -f "$COMPOSE_FILE")
    local profile=""
    for profile in "${COMPOSE_PROFILES[@]}"; do
      compose_args+=(--profile "$profile")
    done
    docker compose "${compose_args[@]}" down -v || true
  fi
}

wait_for_api_health() {
  echo "[step] waiting for API health"
  local _i=0
  for _i in $(seq 1 90); do
    if curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null; then
      break
    fi
    sleep 2
  done
  curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null
}

bootstrap_local_admin() {
  echo "[step] bootstrap first local superuser"
  local output
  if output="$(
    PYTHONPATH=. "$PYTHON_BIN" scripts/bootstrap_local_admin.py \
      --mongo-uri "$MONGO_URI" \
      --db "$COYOTE3_DB" \
      --username "$ADMIN_USERNAME" \
      --email "$ADMIN_EMAIL" \
      --password "$ADMIN_PASSWORD" \
      --role-id "superuser" \
      --assay-group "hematology" \
      --assay "assay_1" 2>&1
  )"; then
    printf '%s\n' "$output"
    return 0
  fi

  if grep -Fq "A superuser already exists." <<<"$output"; then
    echo "[info] bootstrap superuser already exists; continuing with seed + ingest"
    return 0
  fi

  printf '%s\n' "$output" >&2
  return 1
}

seed_baseline_collections() {
  local seed_args=(
    --api-base-url "$API_BASE_URL"
    --username "$ADMIN_EMAIL"
    --password "$ADMIN_PASSWORD"
    --seed-file "$SEED_FILE"
  )
  if [[ -n "$SEED_DATA_PACK" ]]; then
    seed_args+=(--reference-seed-data "$SEED_DATA_PACK")
  fi
  if [[ "$WITH_OPTIONAL" -eq 1 ]]; then
    seed_args+=(--with-optional)
  fi
  if [[ "$SKIP_EXISTING" -eq 1 ]]; then
    seed_args+=(--skip-existing)
  fi
  if [[ "$STRICT_NO_RETRY" -eq 1 ]]; then
    seed_args+=(--strict-no-retry)
  fi

  echo "[step] seed baseline collections"
  bash scripts/bootstrap_center_collections.sh "${seed_args[@]}"
}

run_ingest_check() {
  echo "[step] ingest check"
  bash scripts/center_check.sh \
    --api-base-url "$API_BASE_URL" \
    --username "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" \
    --yaml-file "$YAML_FILE"
}

main() {
  parse_args "$@"
  if [[ -z "$SEED_DATA_PACK" && -d "tests/data/seed_data" ]]; then
    SEED_DATA_PACK="tests/data/seed_data"
    echo "[info] using default seed data pack: ${SEED_DATA_PACK}"
  fi
  validate_args
  clear_shell_overrides_from_env_file
  resolve_python_bin
  resolve_version
  load_env_runtime_values
  validate_profile_requirements
  rewrite_internal_mongo_uri_for_host

  run_preflight
  start_compose_stack
  bootstrap_mongo_app_user
  trap cleanup EXIT
  wait_for_api_health
  bootstrap_local_admin
  seed_baseline_collections
  run_ingest_check

  echo "[ok] first-time center bootstrap completed"
}

main "$@"
