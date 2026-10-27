#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
  cat <<'USAGE'
Validate resolved deployment settings and center files without starting services.
Requires host Python 3.12+ with the application installed. The normal installer
instead validates application configuration inside its API image.

Usage: bash scripts/deployment/center_preflight.sh --env-file FILE
       --compose-file BASE [--compose-file OVERLAY] [--prepare-directories]
       [--seed-file FILE] [--yaml-file FILE] [--reference-seed-data DIRECTORY]...

Only --prepare-directories creates missing application storage. This command does
not connect to MongoDB/Redis, create networks, or install application data.
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ENV_FILE="" SEED_FILE="" YAML_FILE=""
COMPOSE_ARGS=() REFERENCE_SEED_DATA=() PREPARE_DIRECTORIES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prepare-directories) PREPARE_DIRECTORIES=(--prepare-directories); shift ;;
    --env-file|--compose-file|--seed-file|--yaml-file|--reference-seed-data)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --env-file) ENV_FILE="$(realpath "$2")" ;;
        --compose-file) COMPOSE_ARGS+=(-f "$(realpath "$2")") ;;
        --seed-file) SEED_FILE="$(realpath "$2")" ;;
        --yaml-file) YAML_FILE="$(realpath "$2")" ;;
        --reference-seed-data) REFERENCE_SEED_DATA+=("$(realpath "$2")") ;;
      esac
      shift 2 ;;
    --help|-h) usage; exit 0 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
[[ -f "$ENV_FILE" && ${#COMPOSE_ARGS[@]} -gt 0 ]] || { usage; exit 2; }
cd "$ROOT_DIR"
source scripts/deployment/python_runtime.sh
select_deployment_python "$ROOT_DIR"
export PYTHONPATH="$ROOT_DIR${PYTHONPATH:+:$PYTHONPATH}"
docker compose version >/dev/null
bash scripts/deployment/validate_env_secrets.sh --env-file "$ENV_FILE"
rendered="$(mktemp)"
trap 'rm -f "$rendered"' EXIT
bash scripts/deployment/compose-with-version.sh "${PREPARE_DIRECTORIES[@]}" \
  --env-file "$ENV_FILE" "${COMPOSE_ARGS[@]}" config --format json > "$rendered"

"$PYTHON_BIN" - "$rendered" <<'PY'
import json
import os
import sys
from pathlib import Path

config = json.loads(Path(sys.argv[1]).read_text())
api = config["services"]["api"]
settings = api["environment"]
os.environ.update({key: str(value) for key, value in settings.items() if value is not None})
mounts = {item["target"]: Path(item["source"]) for item in api.get("volumes", [])
          if item.get("type") == "bind"}
if "/app/center-config" not in mounts:
    raise SystemExit("API requires a center configuration bind mount")
os.environ["COYOTE3_CENTER_CONFIG_DIR"] = str(mounts["/app/center-config"])
from api.config.mongo import mongo_endpoints
from scripts.deployment.installation_checks import validate_configuration
from scripts.deployment.prepare_host_directories import check_directory_access

mongo_endpoints(settings)
validate_configuration()
args = api.get("build", {}).get("args", {})
identity = api.get("user") or f"{args.get('COYOTE3_UID', 10001)}:{args.get('COYOTE3_GID', 10001)}"
if len(str(identity).split(":")) != 2 or not all(part.isdigit() for part in str(identity).split(":")):
    raise SystemExit("API container identity must use numeric UID:GID")
uid, gid = map(int, str(identity).split(":"))
for target in ("/data", "/app/logs"):
    if target not in mounts:
        raise SystemExit(f"API requires {target} as a bind mount")
    if any(item.get("target") == target and item.get("read_only")
           for item in api.get("volumes", [])):
        raise SystemExit(f"API requires {target} to be writable, but its mount is read-only")
    check_directory_access(mounts[target], uid, gid, mount_root=mounts[target])
print("[ok] Resolved MongoDB selections, mounted center files and storage permissions")
PY

if [[ -n "$SEED_FILE" ]]; then
  [[ -e "$SEED_FILE" ]] || { echo "Seed source does not exist" >&2; exit 2; }
  seed_command=("$PYTHON_BIN" scripts/bootstrap/validate_assay_consistency.py --seed-file "$SEED_FILE")
  for reference in "${REFERENCE_SEED_DATA[@]}"; do
    [[ -d "$reference" ]] || { echo "Reference source must be a directory" >&2; exit 2; }
    seed_command+=(--reference-seed-data "$reference")
  done
  [[ -z "$YAML_FILE" ]] || seed_command+=(--yaml "$YAML_FILE")
  "${seed_command[@]}"
elif [[ -n "$YAML_FILE" ]]; then
  "$PYTHON_BIN" scripts/ingest/validate_ingest_spec.py --yaml "$YAML_FILE"
fi
echo "[ok] preflight passed (no database or service connectivity check)"
