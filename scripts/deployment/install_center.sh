#!/usr/bin/env bash
set -euo pipefail
umask 077

usage() {
  cat <<'USAGE'
Build, validate, bootstrap fresh databases, ensure indexes, and start Coyote3.
MongoDB, its users and the external bridge network must already be provisioned.
Existing installations skip application bootstrap. Host networking is never created or repaired.

Usage: bash scripts/deployment/install_center.sh --env-file FILE --project NAME
       --compose-file FILE [--compose-file OVERLAY] [--skip-build]
       [--sys-admin-username NAME --sys-admin-email EMAIL]
       [--username EMERGENCY_USER --email EMAIL]
       [--skip-users] [--skip-application] [--skip-knowledgebase] [--skip-demo]
       [--knowledgebase-maintenance-uri-file FILE]
       [--identity-maintenance-uri-file FILE]
       [--steps network,directories,build,validate,bootstrap,indexes,start,health]
       [--setup-center] [--with-knowledgebase-indexes]

Missing initial account details and passwords are prompted only for fresh targets.
Fresh installation includes accounts, application catalogs, bundled knowledgebases and both demos.
Existing deployments preserve all data; later additions/repairs use deployment/manage_data.py.
--setup-center selects all stages; cannot combine with --steps.
Knowledgebase indexes remain a separate opt-in. Maintenance credentials may seed a fresh knowledgebase.
Steps run in the listed canonical order; validation and startup safety gates remain mandatory.
Image builds package the application inside Docker; no host SDK preparation is required.
The optional release Compose overlay verifies a supplied tested wheel and release record.
No database is dropped, restored, reset or migrated. Index conflicts stop installation.
The identity maintenance option explicitly upgrades runtime roles before validation,
using credentials supplied only to a one-off container; it does not change passwords.
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
env_file="" project="" maintenance_file="" identity_maintenance_file=""
admin_username="" admin_email="" emergency_username="" emergency_email=""
skip_build=0
setup_center=0 steps_explicit=0
steps="network,directories,build,validate,bootstrap,indexes,start,health"
kb_seeds=1 kb_indexes=0
compose_files=()
with_demo=1 skip_users=0 skip_application=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --help|-h) usage; exit 0 ;;
    --skip-build) skip_build=1; shift ;;
    --setup-center) setup_center=1; shift ;;
    --with-knowledgebase-indexes) kb_indexes=1; shift ;;
    --skip-users) skip_users=1; shift ;;
    --skip-application) skip_application=1; shift ;;
    --skip-knowledgebase) kb_seeds=0; shift ;;
    --skip-demo) with_demo=0; shift ;;
    --env-file|--project|--compose-file|--sys-admin-username|--sys-admin-email|--username|--email|--knowledgebase-maintenance-uri-file|--identity-maintenance-uri-file|--steps)
      [[ $# -ge 2 && -n "$2" && "$2" != --* ]] || { echo "Missing value for $1" >&2; exit 2; }
      case "$1" in
        --env-file) env_file="$(realpath "$2")" ;;
        --project) project="$2" ;;
        --steps) steps="$2"; steps_explicit=1 ;;
        --compose-file) compose_files+=(-f "$(realpath "$2")") ;;
        --sys-admin-username) admin_username="$2" ;;
        --sys-admin-email) admin_email="$2" ;;
        --username) emergency_username="$2" ;;
        --email) emergency_email="$2" ;;
        --knowledgebase-maintenance-uri-file) maintenance_file="$(realpath "$2")" ;;
        --identity-maintenance-uri-file) identity_maintenance_file="$(realpath "$2")" ;;
      esac
      shift 2 ;;
    *) echo "Unknown argument: $1" >&2; usage; exit 2 ;;
  esac
done
if [[ "$setup_center" == 1 ]]; then
  [[ "$steps_explicit" == 0 ]] || {
    echo "--setup-center cannot be combined with --steps; select individual operations instead" >&2
    exit 2
  }
fi
if [[ "$skip_users" == 1 && ( "$skip_application" == 0 || "$kb_seeds" == 1 || "$with_demo" == 1 ) ]]; then
  echo "--skip-users requires --skip-application --skip-knowledgebase --skip-demo" >&2; exit 2
fi
if [[ "$skip_application" == 1 && "$with_demo" == 1 ]]; then
  echo "--skip-application requires --skip-demo" >&2; exit 2
fi
[[ "$steps" =~ ^(network|directories|build|validate|bootstrap|indexes|start|health)(,(network|directories|build|validate|bootstrap|indexes|start|health))*$ ]] || {
  echo "Invalid --steps selection" >&2; exit 2;
}
selected() { [[ ",$steps," == *",$1,"* ]]; }
if [[ -n "$identity_maintenance_file" ]] && ! selected validate && ! selected bootstrap \
  && ! selected indexes && ! selected start; then
  echo "Identity role upgrade requires validation, bootstrap, indexes or startup" >&2; exit 2
fi
if [[ -n "$maintenance_file" && "$kb_seeds" == 0 && "$kb_indexes" == 0 ]]; then
  echo "Maintenance URI override requires knowledgebase installation or indexes" >&2; exit 2
fi
[[ -f "$env_file" && -n "$project" && ${#compose_files[@]} -gt 0 ]] || { usage; exit 2; }
cd "$ROOT_DIR"
export GIT_COMMIT="${GIT_COMMIT:-$(git rev-parse HEAD)}"
if selected health; then command -v curl >/dev/null; fi
docker compose version >/dev/null
bash scripts/deployment/validate_env_secrets.sh --env-file "$env_file"
compose_args=(-p "$project" --env-file "$env_file" "${compose_files[@]}")
compose() { bash scripts/deployment/compose-with-version.sh "${compose_args[@]}" "$@"; }
scratch_dir="$(mktemp -d)"
trap 'rm -rf "$scratch_dir"; unset COYOTE_INSTALL_KB_URI COYOTE_INSTALL_IDENTITY_URI' EXIT

# Resolve only nonsecret orchestration values from Compose, never source/eval an env file.
compose config --format json > "$scratch_dir/compose.json"
if selected build && [[ "$skip_build" == 0 ]]; then
  python3 scripts/release/verify_sdk_artifact.py \
    --compose-config "$scratch_dir/compose.json" --release "$ROOT_DIR/release.toml"
fi
python3 - "$scratch_dir/compose.json" > "$scratch_dir/settings" <<'PY'
import json
import sys
from urllib.parse import parse_qs, urlsplit
with open(sys.argv[1]) as stream:
    config = json.load(stream)
if config["networks"]["app"].get("external") is not True:
    raise SystemExit("Application network must be external and provisioned before installation")
env = config["services"]["api"]["environment"]
identity_uri = env.get("IDENTITY_MONGO_URI") or env.get("COYOTE3_MONGO_URI") or ""
identity = urlsplit(identity_uri)
if not (identity.username or parse_qs(identity.query).get("authMechanism")):
    raise SystemExit(
        "Identity MongoDB connection is anonymous. Set IDENTITY_MONGO_URI (or its "
        "COYOTE3_MONGO_URI fallback) to an authenticated runtime connection before "
        "building. MongoDB authorization and the restricted identity role must also "
        "be provisioned. See docs/operations/audit-and-logging.md. "
        "The identity maintenance option upgrades existing user roles; it does not "
        "enable MongoDB authentication or create runtime credentials."
    )
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
if selected network || selected validate || selected bootstrap || selected indexes || selected start \
  || [[ "$kb_indexes" == 1 || -n "$maintenance_file" ]]; then
  if ! network_driver="$(docker network inspect "${settings[0]}" --format '{{.Driver}}')"; then
    echo "Cannot inspect application network '${settings[0]}'; provision the external bridge first." >&2
    echo "See docs/deployment/first-installation.md. No host networking changes were attempted." >&2
    exit 1
  fi
  if [[ "$network_driver" != bridge ]]; then
    echo "Application network '${settings[0]}' must use the bridge driver; found '$network_driver'." >&2
    echo "No host networking changes were attempted." >&2
    exit 1
  fi
fi
if selected directories; then compose --prepare-directories config --quiet; fi
if selected build && [[ "$skip_build" == 0 ]]; then compose build; fi
if selected start; then
  # A Redis-local health check cannot establish connectivity across the Docker bridge.
  compose up -d --no-deps --no-build --wait --wait-timeout 60 redis
  compose run --rm --no-deps -T api python3 -m scripts.deployment.installation_checks redis
fi
state="unchecked"
if selected validate || selected bootstrap || selected indexes || selected start; then
if [[ -n "$identity_maintenance_file" ]]; then
  COYOTE_INSTALL_IDENTITY_URI="$(cat "$identity_maintenance_file")"
  [[ -n "$COYOTE_INSTALL_IDENTITY_URI" ]] || { echo "Identity maintenance URI file is empty" >&2; exit 2; }
  export COYOTE_INSTALL_IDENTITY_URI
  compose run --rm --no-deps -T -e COYOTE_INSTALL_IDENTITY_URI api \
    python3 -m scripts.database.manage_mongo_roles --maintenance-uri-env COYOTE_INSTALL_IDENTITY_URI --apply
  unset COYOTE_INSTALL_IDENTITY_URI
fi
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
  bootstrap_args=()
  [[ -z "$admin_username" ]] || bootstrap_args+=(--sys-admin-username "$admin_username")
  [[ -z "$admin_email" ]] || bootstrap_args+=(--sys-admin-email "$admin_email")
  [[ -z "$emergency_username" ]] || bootstrap_args+=(--username "$emergency_username")
  [[ -z "$emergency_email" ]] || bootstrap_args+=(--email "$emergency_email")
  [[ "$skip_users" == 0 ]] || bootstrap_args+=(--skip-users)
  [[ "$skip_application" == 0 ]] || bootstrap_args+=(--skip-application)
  [[ "$kb_seeds" == 1 ]] || bootstrap_args+=(--skip-knowledgebase)
  [[ "$with_demo" == 1 ]] || bootstrap_args+=(--skip-demo)
  maintenance_compose run --rm --no-deps -it "${maintenance_env_args[@]}" api \
    python3 scripts/bootstrap/bootstrap_database.py --require-empty-target \
    --db "${settings[1]}" --identity-db "${settings[2]}" \
    "${bootstrap_args[@]}"
  [[ "$skip_users" == 1 ]] || state="existing"
elif selected bootstrap; then
  echo "[skip] Existing deployment: all data preserved; use manage_data.py for additions or repairs."
fi
if selected indexes; then
compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks indexes
compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py apply --summary
compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks indexes-ready
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
[[ "$state" == existing || "$skip_users" == 1 ]] || { echo "Initial accounts are missing; run bootstrap first" >&2; exit 1; }
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
