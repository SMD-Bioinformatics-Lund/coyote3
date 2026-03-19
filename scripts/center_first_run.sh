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
    [--yaml-file <path>] \
    [--with-optional] \
    [--skip-existing] \
    [--teardown]
USAGE
}

ENV_FILE=""
COMPOSE_FILE=""
API_BASE_URL=""
ADMIN_EMAIL=""
ADMIN_PASSWORD=""
MONGO_URI_OVERRIDE=""
SEED_FILE="tests/fixtures/db_dummy/center_template_seed.json"
YAML_FILE="tests/data/ingest_demo/generic_case_control.yaml"
WITH_OPTIONAL=0
SKIP_EXISTING=0
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
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    --with-optional) WITH_OPTIONAL=1; shift ;;
    --skip-existing) SKIP_EXISTING=1; shift ;;
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
  PROD_MONGO_PORT="$(extract_env COYOTE3_MONGO_PORT)"
  TARGET_PORT="${STAGE_MONGO_PORT:-${DEV_MONGO_PORT:-${PROD_MONGO_PORT:-8008}}}"
  MONGO_URI="$(echo "$MONGO_URI" | sed -E "s#@[^/]+:27017/#@localhost:${TARGET_PORT}/#")"
fi

bash scripts/center_preflight.sh \
  --env-file "$ENV_FILE" \
  --compose-file "$COMPOSE_FILE" \
  --seed-file "$SEED_FILE" \
  --yaml-file "$YAML_FILE"

echo "[step] starting compose stack"
docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" up -d --build

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
"$PYTHON_BIN" scripts/bootstrap_local_admin.py \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB" \
  --email "$ADMIN_EMAIL" \
  --password "$ADMIN_PASSWORD" \
  --assay-group "GROUP_A" \
  --assay "ASSAY_A"

seed_args=(
  --api-base-url "$API_BASE_URL"
  --username "$ADMIN_EMAIL"
  --password "$ADMIN_PASSWORD"
  --seed-file "$SEED_FILE"
)
if [[ "$WITH_OPTIONAL" -eq 1 ]]; then
  seed_args+=(--with-optional)
fi
if [[ "$SKIP_EXISTING" -eq 1 ]]; then
  seed_args+=(--skip-existing)
fi

echo "[step] seed baseline collections"
bash scripts/bootstrap_center_collections.sh "${seed_args[@]}"

echo "[step] ingest smoke"
bash scripts/center_smoke.sh \
  --api-base-url "$API_BASE_URL" \
  --username "$ADMIN_EMAIL" \
  --password "$ADMIN_PASSWORD" \
  --yaml-file "$YAML_FILE"

echo "[ok] first-time center bootstrap completed"
