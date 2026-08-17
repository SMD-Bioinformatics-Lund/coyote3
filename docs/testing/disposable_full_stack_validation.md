# Local disposable full-stack validation

This procedure creates a complete temporary Coyote3 deployment on a local
workstation. It is an operator-run local test that follows the production
deployment sequence:

1. create the MongoDB service;
2. initialize the empty application database explicitly;
3. start the application, worker, scheduler, cache, documentation, and reverse
   proxy;
4. ingest controlled data through the live watch-folder workflow;
5. review the sample and exercise its analysis and reporting workflow;
6. collect evidence; and
7. stop and remove the disposable environment.

The procedure uses the production application topology from
`deploy/compose/docker-compose.yml` without a development, test, or stage
overlay. MongoDB runs from `deploy/compose/docker-compose.mongo.yml`, using the
same MongoDB 8.2 single-member replica-set configuration documented for a new
deployment. Isolation comes from local project names, ports, credentials, and
temporary host paths rather than different application code.

!!! warning "Synthetic data only"

    Use only the synthetic files under `demo_data/`. Do not copy clinical
    samples, patient identifiers, production credentials, or a production
    database archive into this environment.

## Validation boundary

The disposable environment verifies the application below the external TLS
termination boundary.

| Production concern | Disposable equivalent |
| --- | --- |
| MongoDB 8.2 replica set | Temporary MongoDB 8.2 single-member replica set |
| Persistent host paths | Isolated paths under a new `/tmp/coyote3-validation.*` directory |
| Explicit first deployment | `bootstrap_database.py` against an empty database |
| Production application services | Production base Compose file and production image targets |
| Reverse-proxy prefix | A unique `SCRIPT_NAME` served through the bundled proxy |
| Background ingest | Celery worker and scheduled watch-folder scan |
| Center data | Repository-owned synthetic DNA bundle |
| Operational evidence | Health, logs, audit events, worker state, and browser checks |

External Apache or another center-owned TLS proxy must still be validated in
the target-center acceptance exercise. This procedure does not claim to test
that external component.

## Prerequisites

Run the commands from the repository root. The host must provide:

- Docker Engine with the Compose v2 plugin;
- `openssl`;
- `curl`;
- Python 3; and
- enough free disk space for the images and temporary MongoDB files.

Confirm the tools before creating the environment:

```bash
docker version
docker compose version
openssl version
curl --version
python3 --version
```

Use ports that are not assigned to another local service. The explicit Compose
project names keep the test containers separate from an installed Coyote3
environment.

## 1. Create the isolated workspace

Create a temporary root and keep the same terminal open for the complete
procedure:

```bash
export VALIDATION_ROOT="$(mktemp -d /tmp/coyote3-validation.XXXXXX)"
export VALIDATION_ENV_FILE="$VALIDATION_ROOT/coyote3.env"
export VALIDATION_OVERRIDE_FILE="$VALIDATION_ROOT/storage.override.yml"
export VALIDATION_APP_PROJECT="coyote3_validation_app"
export VALIDATION_MONGO_PROJECT="coyote3_validation_mongo"
export VALIDATION_MONGO_NETWORK="coyote3-validation-mongo-net"
export VALIDATION_APP_PORT="6816"
export VALIDATION_MONGO_PORT="27182"

mkdir -p \
  "$VALIDATION_ROOT/data/coyote3/copied_sample_files/yaml" \
  "$VALIDATION_ROOT/access" \
  "$VALIDATION_ROOT/media" \
  "$VALIDATION_ROOT/fs1" \
  "$VALIDATION_ROOT/logs" \
  "$VALIDATION_ROOT/mongo-data" \
  "$VALIDATION_ROOT/mongo-backups"

sudo chown -R 10001:10001 \
  "$VALIDATION_ROOT/data" \
  "$VALIDATION_ROOT/logs"

openssl rand -base64 756 > "$VALIDATION_ROOT/mongo-keyfile"
chmod 0400 "$VALIDATION_ROOT/mongo-keyfile"
sudo chown 999:999 "$VALIDATION_ROOT/mongo-keyfile"
```

The API and worker run as UID `10001`. MongoDB reads the replica-set keyfile as
UID `999`. The ownership assignments are therefore part of the validation,
not optional cleanup.

## 2. Generate disposable credentials

Generate values that are unique to this run:

```bash
export VALIDATION_MONGO_ROOT_PASSWORD="$(openssl rand -hex 24)"
export VALIDATION_MONGO_APP_PASSWORD="$(openssl rand -hex 24)"
export VALIDATION_SECRET_KEY="$(openssl rand -hex 32)"
export VALIDATION_INTERNAL_TOKEN="$(openssl rand -hex 32)"
export VALIDATION_PASSWORD_SALT="$(openssl rand -hex 32)"
export VALIDATION_ADMIN_PASSWORD="$(openssl rand -base64 24 | tr -d '\n')"
```

Print the temporary administrator password only when it is needed for the
browser check:

```bash
printf 'Disposable administrator password: %s\n' "$VALIDATION_ADMIN_PASSWORD"
```

These values are removed with the temporary directory and must not be copied
to a tracked environment file.

## 3. Write the environment file

Create the environment file used by MongoDB and the application stack:

```bash
cat > "$VALIDATION_ENV_FILE" <<EOF
ENV_NAME=testing
COYOTE3_DB=coyote3_validation
BAM_DB=BAM_Service_validation
ORGANIZATION_NAME=Coyote3 disposable validation
LOCAL_TIME_ZONE=UTC

SECRET_KEY=$VALIDATION_SECRET_KEY
INTERNAL_API_TOKEN=$VALIDATION_INTERNAL_TOKEN
PASSWORD_TOKEN_SALT=$VALIDATION_PASSWORD_SALT

COYOTE3_PORT=$VALIDATION_APP_PORT
SCRIPT_NAME=/coyote3_validation
PUBLIC_BASE_URL=http://localhost:$VALIDATION_APP_PORT
CORS_ORIGINS=http://localhost:$VALIDATION_APP_PORT

MONGO_ROOT_USERNAME=coyote3_root
MONGO_ROOT_PASSWORD=$VALIDATION_MONGO_ROOT_PASSWORD
MONGO_APP_USER=coyote3_app
MONGO_APP_PASSWORD=$VALIDATION_MONGO_APP_PASSWORD
MONGO_URI=mongodb://coyote3_app:$VALIDATION_MONGO_APP_PASSWORD@host.docker.internal:$VALIDATION_MONGO_PORT/coyote3_validation?authSource=coyote3_validation&replicaSet=coyote3-validation-rs
COYOTE3_MONGO_NETWORK=$VALIDATION_MONGO_NETWORK
COYOTE3_MONGO_PORT=$VALIDATION_MONGO_PORT
COYOTE3_MONGO_BIND_ADDRESS=127.0.0.1
MONGO_REPLICA_SET_NAME=coyote3-validation-rs
MONGO_REPLICA_MEMBER_HOST=host.docker.internal:$VALIDATION_MONGO_PORT

COYOTE3_DATA_HOST_ROOT=$VALIDATION_ROOT/data
COYOTE3_LOGS_HOST_ROOT=$VALIDATION_ROOT/logs
COYOTE3_MONGO_DATA_HOST_ROOT=$VALIDATION_ROOT/mongo-data
COYOTE3_MONGO_BACKUP_HOST_ROOT=$VALIDATION_ROOT/mongo-backups
COYOTE3_MONGO_KEYFILE_HOST_PATH=$VALIDATION_ROOT/mongo-keyfile

AUTHENTICATION_PROVIDERS=local
CACHE_REQUIRED=1
API_WORKERS=1
CELERY_WORKER_CONCURRENCY=1
API_SESSION_COOKIE_NAME=coyote3_validation_api_session

COYOTE3_INGEST_WATCH_ENABLED=1
COYOTE3_INGEST_WATCH_FILENAME=coyote3.yaml
COYOTE3_INGEST_WATCH_INTERVAL_SECONDS=10
COYOTE3_INGEST_WATCH_UPDATE_EXISTING=0
COYOTE3_INGEST_WATCH_INCREMENT=0

ONCOKB_PUBLIC_LOOKUPS_ENABLED=0
CLINPGX_PUBLIC_LOOKUPS_ENABLED=0
EOF
```

Public knowledgebase calls are disabled so the rehearsal is deterministic and
does not depend on internet access. This does not disable the local
knowledgebase collections loaded by database bootstrap.

Create a local storage override so the production `/access`, `/media`, and
`/fs1` container mounts cannot expose corresponding host directories. Compose
merges these entries by container target and retains all other production
service settings:

```bash
cat > "$VALIDATION_OVERRIDE_FILE" <<EOF
services:
  api:
    volumes: &validation_app_volumes
      - $VALIDATION_ROOT/logs:/app/logs
      - $VALIDATION_ROOT/access:/access
      - $VALIDATION_ROOT/media:/media
      - $VALIDATION_ROOT/data:/data
      - $VALIDATION_ROOT/data:$VALIDATION_ROOT/data
      - $VALIDATION_ROOT/fs1:/fs1
  worker:
    volumes: *validation_app_volumes
  beat:
    volumes: *validation_app_volumes
EOF
```

Validate the file before starting services:

```bash
scripts/validate_env_secrets.sh --env-file "$VALIDATION_ENV_FILE"
```

## 4. Start the disposable MongoDB replica set

Create the external network explicitly, then start MongoDB:

```bash
docker network create "$VALIDATION_MONGO_NETWORK"

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  up -d mongo mongo_init
```

This is the disposable MongoDB container command used by this procedure. The
`mongo` service starts the MongoDB 8.2 server with its isolated bind-mounted
data directory. The one-shot `mongo_init` service initializes the
single-member replica set and then exits. It is normal for `mongo_init` to
show `Exited (0)` after initialization; the `mongo` service must remain
running and healthy.

Wait for its health check through the Compose service name. This avoids
depending on a generated container name:

```bash
until docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  exec -T mongo mongosh --quiet \
    --username coyote3_root \
    --password "$VALIDATION_MONGO_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --eval 'quit(db.adminCommand({ping: 1}).ok ? 0 : 1)' >/dev/null 2>&1; do
  sleep 2
done
```

Optionally verify the database from a separate, short-lived MongoDB tools
container. This confirms that another container can reach the replica set over
the same external Docker network and does not require `mongosh` on the host:

```bash
docker run --rm \
  --network "$VALIDATION_MONGO_NETWORK" \
  --add-host host.docker.internal:host-gateway \
  mongo:8.2 \
  mongosh --quiet \
    "mongodb://coyote3_root:$VALIDATION_MONGO_ROOT_PASSWORD@coyote3_mongo:27017/admin?authSource=admin&replicaSet=coyote3-validation-rs" \
    --eval 'quit(db.adminCommand({ping: 1}).ok ? 0 : 1)'
```

The tools container is removed automatically after the command. It does not
run another database server and does not mount or modify the MongoDB data
directory beyond issuing the authenticated `ping` command.

## 5. Build the production application images

Use the version-aware wrapper so image tags always use `api/version.py`:

```bash
scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  build
```

This builds the production frontend, API, and documentation images. It does
not use the development frontend server or source-code bind mounts.

## 6. Bootstrap the empty database

Initialize the empty database before starting the API:

```bash
scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  run --rm --no-deps api \
  python scripts/bootstrap_database.py \
    --mongo-uri "$(grep '^MONGO_URI=' "$VALIDATION_ENV_FILE" | cut -d= -f2-)" \
    --db coyote3_validation \
    --username coyote3.admin \
    --email admin@validation.invalid \
    --password "$VALIDATION_ADMIN_PASSWORD" \
    --role-id superuser \
    --with-demo-center
```

Bootstrap loads:

- system-managed permissions and roles;
- the first local superuser;
- the bundled HGNC and VEP reference snapshots; and
- synthetic ASP, ASPC, and ISGL records required by the DNA fixture.

Bootstrap is intentionally explicit and refuses to initialize an already
governed database. A second successful bootstrap is not expected.

## 7. Start the complete application stack

Start the same service families used by production:

```bash
scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  up -d
```

Inspect service state:

```bash
scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  ps
```

Wait for the proxied API rather than calling the API container directly:

```bash
export VALIDATION_PUBLIC_URL="http://localhost:$VALIDATION_APP_PORT/coyote3_validation"

for attempt in $(seq 1 60); do
  curl -fsS "$VALIDATION_PUBLIC_URL/api/v1/health" >/dev/null && break
  [ "$attempt" -lt 60 ] || { echo "API did not become healthy" >&2; exit 1; }
  sleep 2
done
```

Verify the public application surfaces:

```bash
curl -fsS "$VALIDATION_PUBLIC_URL/public/catalog" >/dev/null
curl -fsS "$VALIDATION_PUBLIC_URL/docs-site/" >/dev/null
curl -fsS "$VALIDATION_PUBLIC_URL/api/v1/docs" >/dev/null
```

## 8. Submit a live watch-folder ingest

Copy the synthetic DNA manifest into the mounted watch directory using the
configured watch filename:

```bash
cp demo_data/ingest/generic_case_control.yaml \
  "$VALIDATION_ROOT/data/coyote3/copied_sample_files/yaml/coyote3.yaml"
```

The manifest references files packaged in the API image. The worker discovers
the manifest through the mounted watch directory, validates every declared
file, writes the complete sample bundle, and renames the manifest only after
the transaction succeeds.

Wait for the completion marker:

```bash
for attempt in $(seq 1 90); do
  if find "$VALIDATION_ROOT/data/coyote3/copied_sample_files/yaml" \
      -maxdepth 1 -name 'coyote3.yaml*.done' -print -quit | grep -q .; then
    echo "Watch-folder ingest completed"
    break
  fi
  if find "$VALIDATION_ROOT/data/coyote3/copied_sample_files/yaml" \
      -maxdepth 1 -name 'coyote3.yaml*.failed' -print -quit | grep -q .; then
    echo "Watch-folder ingest failed" >&2
    exit 1
  fi
  [ "$attempt" -lt 90 ] || { echo "Ingest did not finish in time" >&2; exit 1; }
  sleep 2
done
```

The completed sample must appear once, have `ingest_status=ready`, and contain
the declared SNV, CNV, CNV-profile, and coverage resources. A `.failed` marker
is a failed validation result; do not rename it to `.done`.

## 9. Validate the clinical workflow

Open the application in a browser:

```text
http://localhost:6816/coyote3_validation/
```

Sign in as `coyote3.admin` with the generated password. Complete any required
first-login password change, then record the following results.

### Sample and analysis checks

1. Open **Samples** and locate `demo_dna_sample`.
2. Confirm the sample is ready and uses `assay_1_base_production`.
3. Confirm the overview shows the case, control, declared files, database
   versions, analysis status, and ASPC metadata.
4. Open **Somatic SNVs** and verify that sorting, paging, searching, filters,
   and the finding detail page work without returning to the overview tab.
5. Open **CNVs** and verify the table and CNV-profile pane.
6. Open **Coverage** and verify that the quality data renders.
7. Apply and reset an SNV filter. Confirm that the table and gene-panel summary
   use the saved sample filter state.
8. Add a controlled sample comment, preview the report, and confirm the latest
   sample comment is used as its summary.
9. Do not finalize or clinically sign the synthetic report.

### Operational checks

1. Open **Application Controls** and confirm the worker is online.
2. Confirm the processed-task count increased after ingest.
3. Open **Audit** and locate the watch-ingest success event by sample name.
4. Confirm the event contains the manifest path, task identifier, and resource
   counts without exposing credentials.
5. Open **Notifications** and confirm no raw gateway or stack-trace content was
   presented to the user.

### Optional RNA extension

`demo_data/ingest/generic_rna_sample.yaml` is a synthetic WTS contract fixture.
Use it only after importing or creating a matching active `assay_rna_1` ASP and
production ASPC through the supported administration workflow. Validate the
Fusion, Expression, Classification, and QC tabs selected by that ASPC. A
missing ASP/ASPC is a configuration failure and must not be bypassed with a
fallback.

## 10. Run API-level verification

The center check exercises authentication, manifest validation, file
collection, and the upload intake endpoint. Run it against a fresh disposable
database or use a second unique sample manifest; it must not overwrite the
watch-ingested sample:

```bash
scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  exec -T api \
  scripts/center_check.sh \
    --api-base-url http://127.0.0.1:8001 \
    --username coyote3.admin \
    --password "$VALIDATION_ADMIN_PASSWORD" \
    --yaml-file demo_data/ingest/generic_case_control.yaml
```

Skip this optional step when the same sample already exists and update is
disabled. The watch-folder result remains the required live-ingest evidence.

## 11. Capture evidence before cleanup

Save service state and logs outside the containers:

```bash
mkdir -p "$VALIDATION_ROOT/evidence"

scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  ps > "$VALIDATION_ROOT/evidence/application-services.txt"

scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  logs --no-color > "$VALIDATION_ROOT/evidence/application.log"

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  logs --no-color > "$VALIDATION_ROOT/evidence/mongodb.log"
```

Review the logs for tracebacks, repeated restarts, failed tasks, MongoDB
selection errors, and unexpected `5xx` responses. Record the application
version, commit, image identifiers, start and finish times, sample name, and
reviewer with the release evidence.

## 12. Stop and remove the disposable environment

Stop the application before MongoDB:

```bash
scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  -f "$VALIDATION_OVERRIDE_FILE" \
  down --remove-orphans

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  down --remove-orphans

docker network rm "$VALIDATION_MONGO_NETWORK"
```

Do not use `down -v`. Coyote3's version-aware wrapper rejects that option, and
production MongoDB data must never be coupled to application teardown.

Confirm that the variables still identify the disposable location before
removing its bind-mounted files:

```bash
case "$VALIDATION_ROOT" in
  /tmp/coyote3-validation.*) ;;
  *) echo "Refusing to remove unexpected path: $VALIDATION_ROOT" >&2; exit 1 ;;
esac

rm -rf -- "$VALIDATION_ROOT"
unset VALIDATION_ROOT VALIDATION_ENV_FILE VALIDATION_OVERRIDE_FILE
unset VALIDATION_APP_PROJECT
unset VALIDATION_MONGO_PROJECT VALIDATION_MONGO_NETWORK
unset VALIDATION_APP_PORT VALIDATION_MONGO_PORT VALIDATION_PUBLIC_URL
unset VALIDATION_MONGO_ROOT_PASSWORD VALIDATION_MONGO_APP_PASSWORD
unset VALIDATION_SECRET_KEY VALIDATION_INTERNAL_TOKEN
unset VALIDATION_PASSWORD_SALT VALIDATION_ADMIN_PASSWORD
```

Finally, confirm that no validation containers remain:

```bash
docker ps -a --filter name=coyote3_validation
```

An empty result completes the teardown. Images remain in the local Docker
cache and may be removed separately according to the host's image-retention
policy.

## Pass criteria

The rehearsal passes only when all of the following are true:

- MongoDB reaches healthy replica-set state;
- explicit bootstrap completes against an empty database;
- every application service starts without a restart loop;
- health, public catalog, documentation, and OpenAPI are reachable through
  `SCRIPT_NAME` and the bundled proxy;
- the watch-folder manifest becomes `.done`, not `.failed`;
- the sample reaches `ready` only after all declared resources are written;
- SNV, CNV, coverage, comments, report preview, audit, and worker-state checks
  complete successfully;
- logs contain no unexplained traceback or repeated `5xx` response; and
- all disposable containers, the external network, credentials, and
  bind-mounted database files are removed.

Failure in any item blocks promotion until the cause is understood and the
complete rehearsal passes on a fresh disposable database.

## Related procedures

- [Initial deployment checklist](../operations/initial_deployment_checklist.md)
- [MongoDB deployment and recovery](../operations/mongodb_deployment_and_recovery.md)
- [Backup, restore, and snapshots](../operations/backup_restore_and_snapshots.md)
- [Browser and release validation](browser_and_release_validation.md)
- [Target-center acceptance](../operations/target_center_acceptance.md)
- [Sample ingest YAML](../api/sample_yaml.md)
