#!/usr/bin/env bash
set -euo pipefail

if [[ "${COYOTE3_FIRST_RUN:-0}" != "1" ]]; then
  echo "[skip] COYOTE3_FIRST_RUN!=1; compose first-run bootstrap disabled."
  exit 0
fi

ADMIN_EMAIL="${FIRST_RUN_ADMIN_EMAIL:-}"
ADMIN_PASSWORD="${FIRST_RUN_ADMIN_PASSWORD:-}"
API_BASE_URL="${FIRST_RUN_API_BASE_URL:-http://coyote3_api:8001}"
SEED_FILE="${FIRST_RUN_SEED_FILE:-tests/fixtures/db_dummy/all_collections_dummy}"
REFERENCE_SEED_DATA="${FIRST_RUN_REFERENCE_SEED_DATA:-}"
YAML_FILE="${FIRST_RUN_YAML_FILE:-tests/data/ingest_demo/generic_case_control.yaml}"
WITH_OPTIONAL="${FIRST_RUN_WITH_OPTIONAL:-0}"
SKIP_EXISTING="${FIRST_RUN_SKIP_EXISTING:-1}"
RUN_SMOKE="${FIRST_RUN_RUN_SMOKE:-1}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
MONGO_URI_VALUE="${FIRST_RUN_MONGO_URI:-${MONGO_URI:-}}"
COYOTE3_DB_VALUE="${FIRST_RUN_DB_NAME:-${COYOTE3_DB:-coyote3}}"

if [[ -z "$ADMIN_EMAIL" || -z "$ADMIN_PASSWORD" ]]; then
  echo "[error] FIRST_RUN_ADMIN_EMAIL and FIRST_RUN_ADMIN_PASSWORD are required when COYOTE3_FIRST_RUN=1."
  exit 2
fi

if [[ -z "$MONGO_URI_VALUE" ]]; then
  echo "[error] FIRST_RUN_MONGO_URI (or MONGO_URI) is required when COYOTE3_FIRST_RUN=1."
  exit 2
fi

if [[ ! -d "$SEED_FILE" ]]; then
  echo "[error] seed directory not found: $SEED_FILE"
  exit 2
fi

if [[ -n "$REFERENCE_SEED_DATA" && ! -d "$REFERENCE_SEED_DATA" ]]; then
  echo "[error] reference seed data directory not found: $REFERENCE_SEED_DATA"
  exit 2
fi

echo "[step] compose first-run: bootstrap local admin"
PYTHONPATH=. "$PYTHON_BIN" scripts/bootstrap_local_admin.py \
  --mongo-uri "$MONGO_URI_VALUE" \
  --db "$COYOTE3_DB_VALUE" \
  --email "$ADMIN_EMAIL" \
  --password "$ADMIN_PASSWORD" \
  --assay-group "${FIRST_RUN_ASSAY_GROUP:-hematology}" \
  --assay "${FIRST_RUN_ASSAY:-assay_1}"

echo "[step] compose first-run: seed baseline collections"
seed_args=(
  --api-base-url "$API_BASE_URL"
  --username "$ADMIN_EMAIL"
  --password "$ADMIN_PASSWORD"
  --seed-file "$SEED_FILE"
)
if [[ -n "$REFERENCE_SEED_DATA" ]]; then
  seed_args+=(--reference-seed-data "$REFERENCE_SEED_DATA")
fi
if [[ "$WITH_OPTIONAL" == "1" ]]; then
  seed_args+=(--with-optional)
fi
if [[ "$SKIP_EXISTING" == "1" ]]; then
  seed_args+=(--skip-existing)
fi
bash scripts/bootstrap_center_collections.sh "${seed_args[@]}"

if [[ "$RUN_SMOKE" == "1" ]]; then
  echo "[step] compose first-run: ingest demo sample"
  bash scripts/center_smoke.sh \
    --api-base-url "$API_BASE_URL" \
    --username "$ADMIN_EMAIL" \
    --password "$ADMIN_PASSWORD" \
    --yaml-file "$YAML_FILE"
fi

echo "[ok] compose first-run bootstrap completed"
