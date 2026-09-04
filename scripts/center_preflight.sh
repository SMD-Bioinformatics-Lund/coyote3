#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Validate a center deployment setup before starting application services.

Usage:
  scripts/center_preflight.sh --env-file <path> --compose-file <base> [--compose-file <overlay>] [--seed-file <path>] [--yaml-file <path>] [--reference-seed-data <path>]...

Example:
  scripts/center_preflight.sh \
    --env-file .coyote3_stage_env \
    --compose-file deploy/compose/docker-compose.yml \
    --compose-file deploy/compose/docker-compose.stage.yml
USAGE
}

ENV_FILE=""
COMPOSE_FILES=()
SEED_FILE=""
YAML_FILE=""
REFERENCE_SEED_DATA=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --env-file) ENV_FILE="$2"; shift 2 ;;
    --compose-file) COMPOSE_FILES+=("$2"); shift 2 ;;
    --seed-file) SEED_FILE="$2"; shift 2 ;;
    --yaml-file) YAML_FILE="$2"; shift 2 ;;
    --reference-seed-data) REFERENCE_SEED_DATA+=("$2"); shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2 ;;
  esac
done

if [[ -z "$ENV_FILE" || ${#COMPOSE_FILES[@]} -eq 0 ]]; then
  echo "ERROR: --env-file and --compose-file are required" >&2
  usage
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "ERROR: env file not found: $ENV_FILE" >&2
  exit 2
fi

COMPOSE_ARGS=()
for compose_file in "${COMPOSE_FILES[@]}"; do
  if [[ ! -f "$compose_file" ]]; then
    echo "ERROR: compose file not found: $compose_file" >&2
    exit 2
  fi
  COMPOSE_ARGS+=("-f" "$compose_file")
done

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is not installed" >&2
  exit 2
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "ERROR: docker compose plugin is not available" >&2
  exit 2
fi

COYOTE3_VERSION="$(python3 api/version.py)"
export COYOTE3_VERSION

echo "[check] validating secrets in env file"
bash scripts/validate_env_secrets.sh --env-file "$ENV_FILE"

echo "[check] validating compose render"
docker compose --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}" config -q

echo "[check] mandatory keys"
for key in MONGO_URI COYOTE3_DB IDENTITY_DB KNOWLEDGEBASE_DB BAM_DB SECRET_KEY INTERNAL_API_TOKEN PASSWORD_TOKEN_SALT CORS_ORIGINS COYOTE3_APP_NETWORK; do
  if ! grep -qE "^${key}=" "$ENV_FILE"; then
    echo "ERROR: missing key in env file: $key" >&2
    exit 1
  fi
done

echo "[check] mongo URI consistency"
PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "$PYTHON_BIN" ]]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python3)"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="$(command -v python)"
  else
    echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
    exit 2
  fi
fi

echo "[check] python version"
echo "Using Python: $PYTHON_BIN"
"$PYTHON_BIN" --version
echo "Env file: $ENV_FILE"
if ! "$PYTHON_BIN" --version >/dev/null 2>&1; then
  echo "ERROR: Python interpreter is not runnable: $PYTHON_BIN" >&2
  exit 2
fi

"$PYTHON_BIN" -c '
import sys
from urllib.parse import parse_qs, urlparse

env_file = sys.argv[1]
data = {}
with open(env_file, "r", encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        data[k.strip()] = v.strip().strip("'"'"'\"")

db = data.get("COYOTE3_DB", "")
if not db:
    raise SystemExit("ERROR: COYOTE3_DB must be set")
identity_db = data.get("IDENTITY_DB", "")
if not identity_db:
    raise SystemExit("ERROR: IDENTITY_DB must be set")
knowledgebase_db = data.get("KNOWLEDGEBASE_DB", "")
if not knowledgebase_db:
    raise SystemExit("ERROR: KNOWLEDGEBASE_DB must be set")
bam_db = data.get("BAM_DB", "")
if not bam_db:
    raise SystemExit("ERROR: BAM_DB must be set")
if knowledgebase_db in {db, bam_db}:
    raise SystemExit("ERROR: KNOWLEDGEBASE_DB must be different from COYOTE3_DB and BAM_DB")
if identity_db in {db, knowledgebase_db, bam_db}:
    raise SystemExit("ERROR: IDENTITY_DB must be different from all other configured databases")
uri = data.get("MONGO_URI", "")
if not uri:
    raise SystemExit("ERROR: MONGO_URI must be set")

parsed = urlparse(uri)
uri_db = parsed.path.lstrip("/")
if uri_db and uri_db != db:
    raise SystemExit(f"ERROR: MONGO_URI db '"'"'{uri_db}'"'"' does not match COYOTE3_DB '"'"'{db}'"'"'.")

qs = parse_qs(parsed.query)
auth_source = (qs.get("authSource") or [""])[0]
if auth_source and auth_source != db:
    raise SystemExit(f"ERROR: MONGO_URI authSource '"'"'{auth_source}'"'"' does not match COYOTE3_DB '"'"'{db}'"'"'.")

' "$ENV_FILE"

echo "[check] endpoint ports"
if grep -qE '^COYOTE3_PORT=' "$ENV_FILE"; then
  val="$(grep -E '^COYOTE3_PORT=' "$ENV_FILE" | tail -n1 | cut -d'=' -f2- | tr -d "'\"")"
  if [[ -n "$val" && ! "$val" =~ ^[0-9]+$ ]]; then
    echo "ERROR: COYOTE3_PORT must be numeric, got: ${val}" >&2
    exit 1
  fi
fi

echo "[check] runtime mount ownership and permissions"
"$PYTHON_BIN" -c '
import os
import stat
import sys

env_file = sys.argv[1]
data = {}
with open(env_file, "r", encoding="utf-8") as fh:
    for raw in fh:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        data[key.strip()] = value.strip().strip("\"\047")

uid = int(data.get("COYOTE3_UID", "10001"))
gid = int(data.get("COYOTE3_GID", "10001"))

def has_access(path, *, write):
    current = os.path.abspath(path)
    if not os.path.isdir(current):
        raise SystemExit(f"ERROR: configured host directory does not exist: {current}")
    target = os.stat(current)
    if target.st_uid == uid:
        required = stat.S_IXUSR | (stat.S_IWUSR if write else stat.S_IRUSR)
    elif target.st_gid == gid:
        required = stat.S_IXGRP | (stat.S_IWGRP if write else stat.S_IRGRP)
    else:
        required = stat.S_IXOTH | (stat.S_IWOTH if write else stat.S_IROTH)
    if (target.st_mode & required) != required:
        operation = "write and traverse" if write else "read and traverse"
        raise SystemExit(
            f"ERROR: container uid:gid {uid}:{gid} cannot {operation} {current}; "
            "set ownership or mode before deployment"
        )

    parent = current
    while parent != "/":
        parent = os.path.dirname(parent)
        parent_stat = os.stat(parent)
        if parent_stat.st_uid == uid:
            executable = bool(parent_stat.st_mode & stat.S_IXUSR)
        elif parent_stat.st_gid == gid:
            executable = bool(parent_stat.st_mode & stat.S_IXGRP)
        else:
            executable = bool(parent_stat.st_mode & stat.S_IXOTH)
        if not executable:
            raise SystemExit(
                f"ERROR: container uid:gid {uid}:{gid} cannot traverse parent directory {parent}"
            )

for key in ("COYOTE3_DATA_HOST_ROOT", "COYOTE3_LOGS_HOST_ROOT"):
    value = data.get(key, "")
    if not value:
        raise SystemExit(f"ERROR: missing host path in env file: {key}")
    has_access(value, write=True)
' "$ENV_FILE"

if [[ -n "$SEED_FILE" ]]; then
  if [[ ! -e "$SEED_FILE" ]]; then
    echo "ERROR: seed source not found: $SEED_FILE" >&2
    exit 2
  fi
  echo "[check] seed dependency and assay consistency"
  PYTHON_BIN="${PYTHON_BIN:-}"
  if [[ -z "$PYTHON_BIN" ]]; then
    if command -v python3 >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python3)"
    elif command -v python >/dev/null 2>&1; then
      PYTHON_BIN="$(command -v python)"
    else
      echo "ERROR: python/python3 not found in PATH. Set PYTHON_BIN." >&2
      exit 2
    fi
  fi
  cmd=("$PYTHON_BIN" scripts/validate_assay_consistency.py --seed-file "$SEED_FILE")
  for reference_dir in "${REFERENCE_SEED_DATA[@]}"; do
    if [[ ! -d "$reference_dir" ]]; then
      echo "ERROR: reference seed data source not found: $reference_dir" >&2
      exit 2
    fi
    cmd+=(--reference-seed-data "$reference_dir")
  done
  if [[ -n "$YAML_FILE" ]]; then
    if [[ ! -f "$YAML_FILE" ]]; then
      echo "ERROR: yaml file not found: $YAML_FILE" >&2
      exit 2
    fi
    cmd+=(--yaml "$YAML_FILE")
  fi
  "${cmd[@]}"
fi

echo "[ok] preflight passed"
