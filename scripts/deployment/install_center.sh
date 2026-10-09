#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
  cat <<'USAGE'
Build, validate, bootstrap fresh databases, ensure indexes, and start Coyote3.
MongoDB and its users must already be provisioned. Existing installations skip application bootstrap.

Usage: bash scripts/deployment/install_center.sh --env-file FILE --project NAME
       --compose-file FILE [--compose-file OVERLAY] [--skip-build]
       [--sys-admin-username NAME --sys-admin-email EMAIL]
       [--username EMERGENCY_USER --email EMAIL] [--with-demo-center]
       [--knowledgebase-maintenance-uri-file FILE]
       [--steps network,directories,build,validate,bootstrap,indexes,start,health]
       [--with-knowledgebase-seeds] [--with-knowledgebase-indexes]

Missing initial account details and passwords are prompted only for fresh targets.
Knowledgebase data and indexes are opt-in, using the configured URI unless overridden.
Steps run in the listed canonical order; validation and startup safety gates remain mandatory.
No database is dropped, restored, reset or migrated. Index conflicts stop installation.
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
env_file="" project="" maintenance_file=""
admin_username="" admin_email="" emergency_username="" emergency_email=""
skip_build=0
steps="network,directories,build,validate,bootstrap,indexes,start,health"
kb_seeds=0 kb_indexes=0
compose_files=() demo_args=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --skip-build) skip_build=1; shift ;;
    --with-knowledgebase-seeds) kb_seeds=1; shift ;;
    --with-knowledgebase-indexes) kb_indexes=1; shift ;;
    --with-demo-center) demo_args=(--with-demo-center); shift ;;
    --env-file|--project|--compose-file|--sys-admin-username|--sys-admin-email|--username|--email|--knowledgebase-maintenance-uri-file|--steps)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --env-file) env_file="$(realpath "$2")" ;;
        --project) project="$2" ;;
        --steps) steps="$2" ;;
        --compose-file) compose_files+=(-f "$(realpath "$2")") ;;
        --sys-admin-username) admin_username="$2" ;;
        --sys-admin-email) admin_email="$2" ;;
        --username) emergency_username="$2" ;;
        --email) emergency_email="$2" ;;
        --knowledgebase-maintenance-uri-file) maintenance_file="$(realpath "$2")" ;;
      esac
      shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
[[ "$steps" =~ ^(network|directories|build|validate|bootstrap|indexes|start|health)(,(network|directories|build|validate|bootstrap|indexes|start|health))*$ ]] || {
  echo "Invalid --steps selection" >&2; exit 2;
}
selected() { [[ ",$steps," == *",$1,"* ]]; }
if [[ -n "$maintenance_file" && "$kb_seeds" == 0 && "$kb_indexes" == 0 ]]; then
  echo "Maintenance URI override requires a knowledgebase operation" >&2; exit 2
fi
[[ -f "$env_file" && -n "$project" && ${#compose_files[@]} -gt 0 ]] || { usage; exit 2; }
cd "$ROOT_DIR"
if selected health; then command -v curl >/dev/null; fi
docker compose version >/dev/null
bash scripts/deployment/validate_env_secrets.sh --env-file "$env_file"
compose_args=(-p "$project" --env-file "$env_file" "${compose_files[@]}")
compose() { bash scripts/deployment/compose-with-version.sh "${compose_args[@]}" "$@"; }
scratch_dir="$(mktemp -d)"
trap 'rm -rf "$scratch_dir"; unset COYOTE_INSTALL_KB_URI' EXIT

# Resolve only nonsecret orchestration values from Compose, never source/eval an env file.
compose config --format json > "$scratch_dir/compose.json"
python3 - "$scratch_dir/compose.json" > "$scratch_dir/settings" <<'PY'
import json
import sys
with open(sys.argv[1]) as stream:
    config = json.load(stream)
env = config["services"]["api"]["environment"]
prefix = (env.get("SCRIPT_NAME") or "").rstrip("/")
ports = [port for port in config["services"]["proxy"].get("ports", [])
         if int(port["target"]) == 8088 and port.get("protocol", "tcp") == "tcp"]
if not ports or not ports[0].get("published"):
    raise SystemExit("Proxy HTTP port 8088 must have a published host port for installation checks")
port = ports[0]
host = port.get("host_ip") or "127.0.0.1"
if host in {"0.0.0.0", "::"}:
    host = "::1" if host == "::" else "127.0.0.1"
if ":" in host:
    host = f"[{host}]"
local_url = f"http://{host}:{int(port['published'])}{prefix}"
values = [config["networks"]["app"]["name"], env["COYOTE3_DB"], env["IDENTITY_DB"],
          env["PUBLIC_BASE_URL"].rstrip("/") + prefix, local_url]
if any(not value or "\n" in value or "\r" in value for value in values):
    raise SystemExit("Invalid installation settings")
if not values[3].startswith(("http://", "https://")):
    raise SystemExit("PUBLIC_BASE_URL must use http or https")
print("\n".join(values))
PY
rm "$scratch_dir/compose.json"
mapfile -t settings < "$scratch_dir/settings"
printf '[target] project=%s application_db=%s identity_db=%s\n' "$project" "${settings[1]}" "${settings[2]}"
if selected network && ! docker network inspect "${settings[0]}" >/dev/null 2>&1; then
  docker network create "${settings[0]}"
fi
if selected directories; then compose --prepare-directories config --quiet; fi
if selected build && [[ "$skip_build" == 0 ]]; then compose build; fi
state="unchecked"
if selected validate || selected bootstrap || selected indexes || selected start; then
compose run --rm --no-deps -T api python3 -m scripts.deployment.installation_checks configuration
if ! compose run --rm --no-deps -T api python3 -m scripts.deployment.installation_checks state > "$scratch_dir/state"; then
  cat "$scratch_dir/state" >&2
  exit 1
fi
state="$(tail -n 1 "$scratch_dir/state")"
[[ "$state" == fresh || "$state" == existing ]] || { echo "Unrecognized target state; stopping" >&2; exit 1; }
fi

maintenance_env_args=()
if [[ -n "$maintenance_file" ]]; then
  COYOTE_INSTALL_KB_URI="$(cat "$maintenance_file")"
  [[ -n "$COYOTE_INSTALL_KB_URI" ]] || { echo "Maintenance URI file is empty" >&2; exit 2; }
  export COYOTE_INSTALL_KB_URI
  compose run --rm --no-deps -T -e COYOTE_INSTALL_KB_URI api python3 -m scripts.deployment.installation_checks maintenance
  maintenance_env_args=(-e KNOWLEDGEBASE_MONGO_URI)
elif [[ "$kb_seeds" == 1 || "$kb_indexes" == 1 ]]; then
  echo "[use] Configured knowledgebase connection for installation."
fi
maintenance_compose() {
  if [[ -n "$maintenance_file" ]]; then
    KNOWLEDGEBASE_MONGO_URI="$COYOTE_INSTALL_KB_URI" compose "$@"
  else
    compose "$@"
  fi
}
if selected bootstrap && [[ "$state" == fresh ]]; then
  [[ -n "$admin_username" ]] || read -rp "Named administrator username: " admin_username
  [[ -n "$admin_email" ]] || read -rp "Named administrator email: " admin_email
  [[ -n "$emergency_username" ]] || read -rp "Emergency superuser username: " emergency_username
  [[ -n "$emergency_email" ]] || read -rp "Emergency superuser email: " emergency_email
  compose run --rm --no-deps -it api \
    python3 scripts/bootstrap/bootstrap_database.py --require-empty-target \
    --db "${settings[1]}" --identity-db "${settings[2]}" \
    --sys-admin-username "$admin_username" --sys-admin-email "$admin_email" \
    --username "$emergency_username" --email "$emergency_email" "${demo_args[@]}"
  state="existing"
elif selected bootstrap; then
  echo "[skip] Existing installation: accounts, roles and application policies are preserved."
fi
if selected indexes; then
compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks indexes
compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py apply --summary
compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks indexes-ready
fi
if [[ "$kb_seeds" == 1 ]]; then
  [[ -n "$admin_username" ]] || read -rp "Existing administrator username for reference provenance: " admin_username
  maintenance_compose run --rm --no-deps -T "${maintenance_env_args[@]}" api \
    python3 scripts/bootstrap/install_reference_data.py --actor "$admin_username"
fi
if [[ "$kb_indexes" == 1 ]]; then
  maintenance_compose run --rm --no-deps -T "${maintenance_env_args[@]}" api \
    python3 -m scripts.deployment.installation_checks indexes --scope knowledgebase
  maintenance_compose run --rm --no-deps -T "${maintenance_env_args[@]}" api \
    python3 scripts/database/manage_mongo_indexes.py apply --scope knowledgebase --summary
  maintenance_compose run --rm --no-deps -T "${maintenance_env_args[@]}" api \
    python3 -m scripts.deployment.installation_checks indexes-ready --scope knowledgebase
fi
unset COYOTE_INSTALL_KB_URI
if selected start; then
[[ "$state" == existing ]] || { echo "Application baseline is missing; run bootstrap first" >&2; exit 1; }
if ! selected indexes; then
  compose run --rm --no-deps -T api python3 -m scripts.deployment.installation_checks indexes-ready
fi
compose up -d --no-build --wait --wait-timeout 180
compose ps
fi
if selected health; then
printf '[check] Local proxy: %s/\n' "${settings[4]}"
curl --fail --show-error --retry 6 --retry-connrefused --retry-delay 2 --max-time 15 \
  "${settings[4]}/api/v1/health"
curl --fail --show-error --output /dev/null --max-time 15 "${settings[4]}/"
printf '\n[ok] Local application (published proxy port): %s/\n' "${settings[4]}"
printf '[info] Public application (PUBLIC_BASE_URL): %s/\n' "${settings[3]}"
fi
echo "[ok] Selected installation operations completed."
