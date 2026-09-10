# Local disposable full-stack validation

This procedure creates a complete temporary Coyote3 deployment on a local
workstation. It is an operator-run local test that follows the center
deployment sequence:

1. create the MongoDB service;
2. initialize the empty application and identity databases explicitly;
3. start the application, worker, scheduler, cache, documentation, and reverse
   proxy;
4. ingest controlled data through the live watch-folder workflow;
5. review the sample and exercise its analysis and reporting workflow;
6. collect evidence; and
7. stop and remove the disposable environment.

The procedure uses the immutable application topology from
`deploy/compose/docker-compose.yml` without a development, test, or stage
overlay. MongoDB runs from `deploy/compose/docker-compose.mongo.yml` with the
`mongo` profile, using the same MongoDB 7.0.41 single-member replica-set configuration for a new
deployment. Isolation comes from local project names, ports, credentials, and
temporary host paths rather than different application code.

> **Warning: Synthetic data only**
>
>
> Use only the synthetic files under `demo_data/`. Do not copy clinical
> samples, patient identifiers, production credentials, or a production
> database archive into this environment.
>

## Validation boundary

The disposable environment verifies the application below the external TLS
termination boundary.

Always create a new `VALIDATION_ROOT` for a new rehearsal. MongoDB persists the
replica-set member address in its database files. A directory initialized by an
older version of this procedure with a different member address must not be
reused; complete the cleanup section and restart at step 1.

| Deployment concern | Disposable equivalent |
| --- | --- |
| MongoDB 7.0.41 replica set | Temporary MongoDB 7.0.41 single-member replica set |
| Persistent host paths | Isolated paths under a new `/tmp/coyote3-validation.*` directory |
| Explicit first deployment | `bootstrap_database.py` against an empty database |
| Immutable application services | Base Compose file and immutable image targets |
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
environment. Every Compose command in this procedure passes one of these names
with `-p`. This overrides the base Compose project name, producing container
names beginning with the run-specific `coyote3_testing_app_` and
`coyote3_testing_mongo_` project names; it does not create containers with production,
development, or staging project names.

## 1. Create the isolated workspace

Create a temporary root and keep the same terminal open for the complete
procedure:

```bash
export VALIDATION_ROOT="$(mktemp -d /tmp/coyote3-validation.XXXXXX)"
export VALIDATION_ENV_FILE="$VALIDATION_ROOT/coyote3.env"
export VALIDATION_RUN_ID="$(openssl rand -hex 6)"
export VALIDATION_APP_PROJECT="coyote3_testing_app_$VALIDATION_RUN_ID"
export VALIDATION_MONGO_PROJECT="coyote3_testing_mongo_$VALIDATION_RUN_ID"
export VALIDATION_APP_NETWORK="coyote3-validation-app-$VALIDATION_RUN_ID"
export VALIDATION_APP_SUBNET="172.29.120.0/28"
export VALIDATION_APP_GATEWAY="172.29.120.1"
export VALIDATION_APP_PORT="6816"
export VALIDATION_MONGO_PORT="27182"
export COYOTE3_VERSION="$(python3 api/version.py)"

mkdir -p \
  "$VALIDATION_ROOT/data/coyote3_test/copied_sample_files/yaml" \
  "$VALIDATION_ROOT/logs" \
  "$VALIDATION_ROOT/mongo-data" \
  "$VALIDATION_ROOT/mongo-backups"

sudo chown -R 10001:10001 \
  "$VALIDATION_ROOT/data" \
  "$VALIDATION_ROOT/logs"

openssl rand -base64 756 > "$VALIDATION_ROOT/mongo-keyfile"
chmod 0400 "$VALIDATION_ROOT/mongo-keyfile"
```

The API and worker run as UID `10001`. MongoDB uses the host user's UID/GID
configured below. Its shared entrypoint prepares data ownership and a protected
container copy of the operator-owned keyfile before dropping privileges.

## 2. Generate disposable credentials

Generate values that are unique to this run:

```bash
export VALIDATION_MONGO_ROOT_PASSWORD="$(openssl rand -hex 24)"
export VALIDATION_MONGO_APP_PASSWORD="$(openssl rand -hex 24)"
export VALIDATION_SECRET_KEY="$(openssl rand -hex 32)"
export VALIDATION_INTERNAL_TOKEN="$(openssl rand -hex 32)"
export VALIDATION_PASSWORD_SALT="$(openssl rand -hex 32)"
export VALIDATION_REDIS_PASSWORD="$(openssl rand -hex 32)"
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
umask 077
cat > "$VALIDATION_ENV_FILE" <<EOF
ENV_NAME=testing
COYOTE3_DB=coyote3_validation
IDENTITY_DB=coyote3_identity_validation
KNOWLEDGEBASE_DB=coyote3_knowledgebase_validation
BAM_DB=BAM_Service_validation
ORGANIZATION_NAME=Coyote3 disposable validation
LOCAL_TIME_ZONE=UTC

SECRET_KEY=$VALIDATION_SECRET_KEY
INTERNAL_API_TOKEN=$VALIDATION_INTERNAL_TOKEN
PASSWORD_TOKEN_SALT=$VALIDATION_PASSWORD_SALT
REDIS_PASSWORD=$VALIDATION_REDIS_PASSWORD

COYOTE3_PORT=$VALIDATION_APP_PORT
SCRIPT_NAME=/coyote3_validation
PUBLIC_BASE_URL=http://localhost:$VALIDATION_APP_PORT

MONGO_ROOT_USERNAME=coyote3_root
MONGO_ROOT_PASSWORD=$VALIDATION_MONGO_ROOT_PASSWORD
MONGO_APP_USER=coyote3_app
MONGO_APP_PASSWORD=$VALIDATION_MONGO_APP_PASSWORD
COYOTE3_MONGO_URI=mongodb://coyote3_app:$VALIDATION_MONGO_APP_PASSWORD@mongo-app:27017/coyote3_validation?authSource=admin&replicaSet=coyote3-validation-rs
IDENTITY_MONGO_URI=mongodb://coyote3_app:$VALIDATION_MONGO_APP_PASSWORD@mongo-app:27017/coyote3_identity_validation?authSource=admin&replicaSet=coyote3-validation-rs
KNOWLEDGEBASE_MONGO_URI=mongodb://coyote3_app:$VALIDATION_MONGO_APP_PASSWORD@mongo-app:27017/coyote3_knowledgebase_validation?authSource=admin&replicaSet=coyote3-validation-rs
BAM_MONGO_URI=mongodb://coyote3_app:$VALIDATION_MONGO_APP_PASSWORD@mongo-app:27017/BAM_Service_validation?authSource=admin&replicaSet=coyote3-validation-rs
COYOTE3_APP_NETWORK=$VALIDATION_APP_NETWORK
COYOTE3_MONGO_PORT=$VALIDATION_MONGO_PORT
COYOTE3_MONGO_BIND_ADDRESS=127.0.0.1
MONGO_REPLICA_SET_NAME=coyote3-validation-rs
MONGO_UID=$(id -u)
MONGO_GID=$(id -g)
MONGO_REPLICA_MEMBER_HOST=mongo-app:27017

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

Public OncoKB and ClinPGx lookups are disabled so these requests do not leave the
rehearsal environment. Local HGNC and VEP reference snapshots loaded by bootstrap
remain available; bootstrap does not populate an external knowledgebase database.

All four logical databases use explicit URI/name pairs on this disposable replica
set. The `mongo` profile creates the application MongoDB service and initializer;
`mongo-kb` is only needed for a separate knowledgebase instance and is not enabled
here. Without these profiles, no MongoDB container starts. The runtime user has
read-only knowledgebase access and read/write access to app, identity, and BAM.

The base stack mounts only the configured data root at `/data` and logs at
`/app/logs`; no storage override is needed for these bundle-relative synthetic
fixtures. There are no implicit `/access`, `/media`, `/fs1`, or host-path mirror
mounts. Do not add center clinical input mounts to the disposable deployment.

Validate the file before starting services:

```bash
bash scripts/validate_env_secrets.sh --env-file "$VALIDATION_ENV_FILE"
bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml config --quiet
docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo config --quiet
```

## 4. Start the disposable MongoDB replica set

Create the external application network explicitly; the MongoDB profile joins it. The `down`
command removes stale containers from the named disposable Compose project
before MongoDB is recreated. It does not remove the bind-mounted database
directory:

```bash
docker network create \
  --driver bridge \
  --subnet "$VALIDATION_APP_SUBNET" \
  --ip-range "$VALIDATION_APP_SUBNET" \
  --gateway "$VALIDATION_APP_GATEWAY" \
  "$VALIDATION_APP_NETWORK"

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  down --remove-orphans

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  up -d --force-recreate mongo
```

The `/28` validation network provides approximately 13 assignable addresses for
MongoDB, API, workers, and temporary tools. Choose a larger or different range
if it overlaps another network or more replicas are needed.

This starts MongoDB 7.0.41 with its isolated bind-mounted data directory. The
host port is bound to loopback for optional host-side administration. Coyote3
containers use the `mongo-app` network alias and do not pass through a
published host port.

Confirm that Compose attached MongoDB to the pre-created external network.
This check catches stale or detached Docker endpoints before replica-set
initialization:

```bash
export VALIDATION_MONGO_CONTAINER_ID="$(docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  ps -q mongo)"

test -n "$VALIDATION_MONGO_CONTAINER_ID"
docker inspect "$VALIDATION_MONGO_CONTAINER_ID" \
  --format '{{range $name, $_ := .NetworkSettings.Networks}}{{$name}}{{println}}{{end}}' \
  | grep -Fx "$VALIDATION_APP_NETWORK"
```

Wait for its health check through the Compose service name. This avoids
depending on a generated container name:

```bash
for attempt in $(seq 1 60); do
  if docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  exec -T mongo mongosh --quiet \
    --username coyote3_root \
    --password "$VALIDATION_MONGO_ROOT_PASSWORD" \
    --authenticationDatabase admin \
    --eval 'quit(db.adminCommand({ping: 1}).ok ? 0 : 1)' >/dev/null 2>&1; then
    break
  fi
  [ "$attempt" -lt 60 ] || { echo "MongoDB did not become ready" >&2; exit 1; }
  sleep 2
done
```

Initialize the single-member replica set as a foreground one-shot operation:

```bash
docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  run --rm --no-deps mongo_init
```

The command must finish with `[ok] replica set is writable`. The temporary
initializer container is removed automatically; only the `mongo` service
remains running.

Optionally verify the database from a separate, short-lived MongoDB tools
container. This confirms that another container can reach the MongoDB member
over the same external Docker network and does not require `mongosh` on the
host:

```bash
docker run --rm \
  --network "$VALIDATION_APP_NETWORK" \
  mongo:8.2 \
  mongosh --quiet \
    "mongodb://coyote3_root:$VALIDATION_MONGO_ROOT_PASSWORD@mongo-app:27017/admin?authSource=admin&replicaSet=coyote3-validation-rs" \
    --eval 'const hello=db.hello(); printjson({ping:db.adminCommand({ping:1}).ok, replicaSet:hello.setName, writablePrimary:hello.isWritablePrimary}); quit(hello.isWritablePrimary ? 0 : 1)'
```

The tools container is removed automatically after the command. It does not
run another database server and does not mount or modify the MongoDB data
directory beyond issuing authenticated status commands. A successful result
prints `ping: 1`, the configured replica-set name, and
`writablePrimary: true`.

The application and MongoDB services share the isolated validation network.
They reach the replica-set member at `mongo-app:27017`. The MongoDB host port stays bound to `127.0.0.1`, so
it is not exposed on external host interfaces.

## 5. Build the immutable application images

Use the version-aware wrapper so image tags always use `api/version.py`:

```bash
bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  build
```

This builds immutable frontend, API, and documentation artifacts from the same
Docker targets used for a release. The deployment remains a disposable testing
environment because
its configuration, credentials, ports, database, networks, and storage roots
are isolated from production. The test intentionally avoids the development
frontend server and source-code bind mounts so it validates the packaged
application that a center would deploy.

## 6. Bootstrap the empty database

Initialize the empty database before starting the API:

```bash
bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps -it api \
  python scripts/bootstrap_database.py \
    --mongo-uri "$(grep '^COYOTE3_MONGO_URI=' "$VALIDATION_ENV_FILE" | cut -d= -f2-)" \
    --identity-mongo-uri "$(grep '^IDENTITY_MONGO_URI=' "$VALIDATION_ENV_FILE" | cut -d= -f2-)" \
    --db coyote3_validation \
    --identity-db coyote3_identity_validation \
    --sys-admin-username "center.operator" \
    --sys-admin-email "operator@example.org" \
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

Start the complete immutable service stack:

```bash
bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  up -d
```

Inspect service state:

```bash
bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
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

Create one sample bundle through the running worker, which owns the mounted
watch directory. Copy every declared resource first and copy the manifest last
under the configured watch filename. Copying the manifest last prevents the
scheduled scanner from observing an incomplete bundle.

```bash
export VALIDATION_WORKER_CONTAINER_ID="$(docker compose \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  ps -q worker)"

test -n "$VALIDATION_WORKER_CONTAINER_ID"

VALIDATION_DNA_BUNDLE="/data/coyote3_test/copied_sample_files/yaml/demo_dna_sample"
docker exec "$VALIDATION_WORKER_CONTAINER_ID" \
  mkdir -p "$VALIDATION_DNA_BUNDLE"

for resource in \
  demo_data/ingest/generic_case_control.final.filtered.vcf \
  demo_data/ingest/generic_case_control.cnvs.merged.json \
  demo_data/ingest/generic_case_control.modeled.png \
  demo_data/ingest/generic_case_control.cov.json; do
  docker cp "$resource" \
    "$VALIDATION_WORKER_CONTAINER_ID:$VALIDATION_DNA_BUNDLE/$(basename "$resource")"
done

docker cp demo_data/ingest/generic_case_control.yaml \
  "$VALIDATION_WORKER_CONTAINER_ID:$VALIDATION_DNA_BUNDLE/coyote3.yaml"
```

The manifest contains bundle-relative file paths. The worker resolves those
paths from the manifest directory, validates every declared file, writes the
complete sample bundle, and renames the manifest only after the transaction
succeeds. Runtime ingest must not depend on repository files packaged into an
application image.

Wait for the completion marker:

```bash
for attempt in $(seq 1 90); do
  if docker exec "$VALIDATION_WORKER_CONTAINER_ID" find "$VALIDATION_DNA_BUNDLE" \
      -maxdepth 1 -name 'coyote3.yaml*.done' -print -quit | grep -q .; then
    echo "Watch-folder ingest completed"
    break
  fi
  if docker exec "$VALIDATION_WORKER_CONTAINER_ID" find "$VALIDATION_DNA_BUNDLE" \
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
If the ingest family is disabled during the scan, expect the job and manifest to
remain pending without a success acknowledgement. Re-enable it before checking
completion; neither a disabled task result nor an HTTP acceptance is ingest success.

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
PYTHON_BIN=.venv/bin/python bash scripts/center_check.sh \
    --api-base-url "$VALIDATION_PUBLIC_URL" \
    --username coyote3.admin \
    --password "$VALIDATION_ADMIN_PASSWORD" \
    --provider local \
    --yaml-file demo_data/ingest/generic_case_control.yaml
```

The disposable bootstrap creates `coyote3.admin` as a local account, so this
check uses the `local` authentication provider explicitly. Use
`--provider ldap` only when validating a configured LDAP account in a
deployment where LDAP connectivity is part of the test scope.

Skip this optional step when the same sample already exists and update is
disabled. The watch-folder result remains the required live-ingest evidence.
This command runs on the host with the repository's Python environment and fixture
files, through the public proxy; it does not require fixtures inside the API image.

## 11. Capture evidence before cleanup

Save service state and logs outside the containers:

```bash
mkdir -p "$VALIDATION_ROOT/evidence"

bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  ps > "$VALIDATION_ROOT/evidence/application-services.txt"

bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  logs --no-color > "$VALIDATION_ROOT/evidence/application.log"

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  logs --no-color > "$VALIDATION_ROOT/evidence/mongodb.log"
```

Review the logs for tracebacks, repeated restarts, failed tasks, MongoDB
selection errors, and unexpected `5xx` responses. Record the application
version, commit, image identifiers, start and finish times, sample name, and
reviewer with the release evidence.

## 12. Stop and remove the disposable environment

Stop the application before MongoDB:

```bash
bash scripts/compose-with-version.sh \
  -p "$VALIDATION_APP_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.yml \
  down --remove-orphans

docker compose \
  -p "$VALIDATION_MONGO_PROJECT" \
  --env-file "$VALIDATION_ENV_FILE" \
  -f deploy/compose/docker-compose.mongo.yml \
  --profile mongo \
  down --remove-orphans

docker network rm "$VALIDATION_APP_NETWORK"
```

Do not use `down -v`. Coyote3's version-aware wrapper rejects that option, and
production MongoDB data must never be coupled to application teardown.

After confirming that the disposable jobs are complete and evidence has been retained,
remove only this run's Redis volume. Unique project names prevent a later rehearsal
from inheriting old queues or credentials:

```bash
docker volume rm "${VALIDATION_APP_PROJECT}_redis-data"
docker ps -a --filter "label=com.docker.compose.project=$VALIDATION_APP_PROJECT"
docker ps -a --filter "label=com.docker.compose.project=$VALIDATION_MONGO_PROJECT"
```

Both container queries must be empty. Never substitute a clinical deployment's
project name or remove a shared Redis volume.

Confirm that the variables still identify the disposable location before
removing its bind-mounted files:

```bash
case "$VALIDATION_ROOT" in
  /tmp/coyote3-validation.*) ;;
  *) echo "Refusing to remove unexpected path: $VALIDATION_ROOT" >&2; exit 1 ;;
esac

sudo rm -rf -- "$VALIDATION_ROOT"
unset VALIDATION_ROOT VALIDATION_ENV_FILE
unset VALIDATION_APP_PROJECT
unset VALIDATION_RUN_ID VALIDATION_APP_NETWORK VALIDATION_APP_SUBNET VALIDATION_APP_GATEWAY
unset VALIDATION_MONGO_PROJECT
unset VALIDATION_MONGO_CONTAINER_ID VALIDATION_WORKER_CONTAINER_ID
unset VALIDATION_APP_PORT VALIDATION_MONGO_PORT VALIDATION_PUBLIC_URL
unset COYOTE3_VERSION
unset VALIDATION_MONGO_ROOT_PASSWORD VALIDATION_MONGO_APP_PASSWORD
unset VALIDATION_SECRET_KEY VALIDATION_INTERNAL_TOKEN
unset VALIDATION_PASSWORD_SALT VALIDATION_ADMIN_PASSWORD
unset VALIDATION_REDIS_PASSWORD
```

The empty project-scoped container queries complete container verification. Elevated
removal is needed for files owned by the container UIDs. Images remain in the local Docker
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

For a separate capacity exercise, use [self-hosted load testing](load_testing.md)
after this stack is healthy. The generator must reach this isolated stack's Nginx
prefix, with external fetches disabled or mocked. This functional rehearsal,
including its deliberate report save, is not a load-tested release; do not turn its
clinical write checks into load loops. The load guide owns generator commands and
excludes publication and finalization.

- [Initial deployment checklist](../operations/initial_deployment_checklist.md)
- [MongoDB deployment and recovery](../operations/mongodb_deployment_and_recovery.md)
- [Backup, restore, and snapshots](../operations/backup_restore_and_snapshots.md)
- [Browser and release validation](browser_and_release_validation.md)
- [Target-center acceptance](../operations/target_center_acceptance.md)
- [Sample ingest YAML](../api/sample_yaml.md)
