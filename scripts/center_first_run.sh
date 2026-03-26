#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Run first-time center bootstrap end-to-end:
preflight -> compose up -> admin bootstrap -> baseline seed -> ingest smoke.

Usage:
  scripts/center_first_run.sh \
    --env-file <path> \
    --compose-file <path> \
    --api-base-url <url> \
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
API_BASE_URL=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
MONGO_URI_OVERRIDE=""
SEED_FILE="tests/fixtures/db_dummy/all_collections_dummy"
SEED_DATA_PACK=""
YAML_FILE="tests/data/ingest_demo/generic_case_control.yaml"
WITH_OPTIONAL=0
SKIP_EXISTING=0
STRICT_NO_RETRY=0
TEARDOWN=0
PYTHON_BIN="${PYTHON_BIN:-}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILE="$2"; shift 2 ;;
    --api-base-url) API_BASE_URL="$2"; shift 2 ;;
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

if [[ -z "$ENV_FILE" || -z "$COMPOSE_FILE" || -z "$API_BASE_URL" || -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
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

if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  elif command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  else
    echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
    exit 2
  fi
fi

extract_env() {
  local key="$1"
  (grep -E "^${key}=" "$ENV_FILE" || true) | tail -n1 | cut -d'=' -f2- | tr -d "'\""
}

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

# If URI points to compose-internal Mongo host, rewrite to localhost:published_port
# so host-side bootstrap scripts can connect.
if [[ "$MONGO_URI" =~ @coyote3_.*_mongo:27017/ ]]; then
  STAGE_MONGO_PORT="$(extract_env COYOTE3_STAGE_MONGO_PORT)"
  DEV_MONGO_PORT="$(extract_env COYOTE3_DEV_MONGO_PORT)"
  TEST_MONGO_PORT="$(extract_env COYOTE3_TEST_MONGO_PORT)"
  PROD_MONGO_PORT="$(extract_env COYOTE3_MONGO_PORT)"
  TARGET_PORT="${STAGE_MONGO_PORT:-${DEV_MONGO_PORT:-${TEST_MONGO_PORT:-${PROD_MONGO_PORT:-8008}}}}"
  MONGO_URI="$(echo "$MONGO_URI" | sed -E "s#@[^/]+:27017/#@localhost:${TARGET_PORT}/#")"
fi

bootstrap_mongo_app_user() {
  local stage_port dev_port test_port prod_port target_port admin_uri
  stage_port="$(extract_env COYOTE3_STAGE_MONGO_PORT)"
  dev_port="$(extract_env COYOTE3_DEV_MONGO_PORT)"
  test_port="$(extract_env COYOTE3_TEST_MONGO_PORT)"
  prod_port="$(extract_env COYOTE3_MONGO_PORT)"
  target_port="${stage_port:-${dev_port:-${test_port:-${prod_port:-8008}}}}"

  if [[ -z "$MONGO_ROOT_USERNAME" || -z "$MONGO_ROOT_PASSWORD" || -z "$MONGO_APP_USER" || -z "$MONGO_APP_PASSWORD" ]]; then
    echo "[warn] skipping mongo app-user bootstrap; missing root/app mongo credentials in env file."
    return 0
  fi

  admin_uri="mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${target_port}/admin?authSource=admin"
  echo "[step] ensure mongo app user exists and password matches env"
  if ! PYTHONPATH=. "$PYTHON_BIN" scripts/mongo_bootstrap_users.py \
    --mongo-uri "$admin_uri" \
    --app-db "$COYOTE3_DB" \
    --app-user "$MONGO_APP_USER" \
    --app-password "$MONGO_APP_PASSWORD"; then
    echo "[warn] mongo app-user bootstrap failed; API may fail if app credentials do not match existing volume."
  fi
}

if [[ -n "$SEED_DATA_PACK" ]]; then
  bash scripts/center_preflight.sh \
    --env-file "$ENV_FILE" \
    --compose-file "$COMPOSE_FILE" \
    --seed-file "$SEED_FILE" \
    --reference-seed-data "$SEED_DATA_PACK" \
    --yaml-file "$YAML_FILE"
else
  bash scripts/center_preflight.sh \
    --env-file "$ENV_FILE" \
    --compose-file "$COMPOSE_FILE" \
    --seed-file "$SEED_FILE" \
    --yaml-file "$YAML_FILE"
fi
echo "[step] starting compose stack"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

bootstrap_mongo_app_user

cleanup() {
  if [[ "$TEARDOWN" -eq 1 ]]; then
    echo "[step] teardown compose stack"
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" down -v || true
  fi
}
trap cleanup EXIT

echo "[step] waiting for API health"
for _ in $(seq 1 90); do
  if curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS "${API_BASE_URL%/}/api/v1/health" >/dev/null

echo "[step] bootstrap first local admin"
PYTHONPATH=. "$PYTHON_BIN" scripts/bootstrap_local_admin.py \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB" \
  --email "$ADMIN_EMAIL" \
  --password "$ADMIN_PASSWORD" \
  --assay-group "hematology" \
  --assay "assay_1"

seed_args=(
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

SMOKE_ARGS=(
  --api-base-url "$API_BASE_URL"
  --username "$ADMIN_EMAIL"
  --password "$ADMIN_PASSWORD"
  --yaml-file "$YAML_FILE"
)

echo "[step] ingest smoke"
bash scripts/center_smoke.sh "${SMOKE_ARGS[@]}"

echo "[ok] first-time center bootstrap completed"
