# Production deployment

This guide describes a first production installation and later Coyote3 release
deployments. MongoDB is operated independently from the application stack. An
application deployment starts the proxy, frontend, API, worker, scheduler,
Redis, and documentation services; it does not create, seed, stop, or replace
MongoDB.

> **Warning**
>
> Use reviewed center configuration and synthetic acceptance data until the
> installation has passed the center's release checks. Never use the bundled
> demonstration ASP, ASPC, or ISGL records for clinical work.
>

## Deployment model

| Layer | Production responsibility | Lifecycle |
| --- | --- | --- |
| MongoDB | Stores clinical, configuration, audit, and reference collections. | Provisioned and backed up independently. |
| Coyote3 application | Proxy, frontend, API, worker, Beat, Redis, and documentation. | Rebuilt and replaced for each application release. |
| Center configuration | Environment file, contact details, clinical vocabulary, ASP, ASPC, and ISGL records. | Reviewed and changed through controlled center procedures. |
| Host data | Ingest inputs, report assets, logs, MongoDB data, and backups. | Stored outside disposable application containers. |

The production application definition is
`deploy/compose/docker-compose.yml`. Use
`scripts/compose-with-version.sh` instead of calling Docker Compose directly.
The wrapper reads the application version from `api/version.py`, validates the
environment before startup, and rejects `down -v`.

## Requirements

Prepare the following before installing Coyote3:

- a Linux host with Docker Engine and the Docker Compose plugin;
- a DNS name and TLS-terminating reverse proxy;
- MongoDB 8.2 or a later supported compatible release;
- durable storage for application data, logs, MongoDB data, and backups;
- a private production environment file;
- reviewed center ASP, ASPC, and ISGL definitions;
- an off-host backup destination and a restore-test environment.

See [Environment and secrets](../operations/environments_and_secrets.md) for
every supported environment variable and
[Minimum production baseline](../operations/minimum_production_baseline.md) for
the host and security requirements.

## First installation

Complete these steps once for a new, empty Coyote3 database.

### 1. Select the release

Deploy an exact reviewed release tag rather than a moving branch.

```bash
git fetch --tags
git checkout <RELEASE_TAG>
git status --short
```

The working tree should be clean before the deployment begins.

### 2. Create the production environment file

Copy the example and keep the resulting file outside Git.

```bash
cp deploy/env/example.env .coyote3_env
chmod 600 .coyote3_env
```

At minimum, set the deployment identity, database targets, public URL, host
storage roots, and secrets:

```dotenv
ENV_NAME=production
SCRIPT_NAME=/coyote3
PUBLIC_BASE_URL=https://coyote3.example.org
COYOTE3_PORT=5815
ORGANIZATION_NAME=Example molecular diagnostics center
LOCAL_TIME_ZONE=Europe/Stockholm

MONGO_URI=mongodb://<APP_USER>:<PASSWORD>@<MONGO_HOST>:27017/<DATABASE>?authSource=<AUTH_DATABASE>&replicaSet=<REPLICA_SET>
COYOTE3_DB=<COYOTE3_DATABASE>
KNOWLEDGEBASE_DB=<KNOWLEDGEBASE_DATABASE>
BAM_DB=<BAM_SERVICE_DATABASE>

COYOTE3_DATA_HOST_ROOT=/srv/coyote3/data
COYOTE3_LOGS_HOST_ROOT=/srv/coyote3/logs

SECRET_KEY=<GENERATED_RANDOM_SECRET>
INTERNAL_API_TOKEN=<GENERATED_RANDOM_TOKEN>
PASSWORD_TOKEN_SALT=<GENERATED_RANDOM_SALT>
CORS_ORIGINS=https://coyote3.example.org
```

Generate independent secrets with the center's approved secret-management
tool. Do not reuse an administrator password as an application secret.

Validate that no placeholder remains:

```bash
scripts/validate_env_secrets.sh --env-file .coyote3_env
```

Load the selected values into the operator shell before using them in later
commands:

```bash
set -a
. ./.coyote3_env
set +a
```

### 3. Create durable host directories

Create the paths selected in the environment file. The API container runs as
UID and GID `10001`.

```bash
sudo install -d -o 10001 -g 10001 -m 0750 "$COYOTE3_DATA_HOST_ROOT"
sudo install -d -o 10001 -g 10001 -m 0750 "$COYOTE3_LOGS_HOST_ROOT"
docker network create \
  --driver bridge \
  --subnet 172.29.110.0/28 \
  --ip-range 172.29.110.0/28 \
  --gateway 172.29.110.1 \
  "$COYOTE3_APP_NETWORK"
```

The application Compose stack treats this as an external network and will not
create it. Use a distinct name for each deployment, such as
`coyote3-prod-app-net`, `coyote3-stage-app-net`, or `coyote3-dev-app-net`.
The example `/28` pool reserves 16 addresses and provides approximately 13
assignable container addresses for the current seven services and limited
replicas. Select a different RFC 1918 subnet when this range overlaps center
infrastructure. Use a larger pool when the deployment will run many API or
worker replicas.

Create and mount any center data roots used by pipeline manifests. A path
stored in a sample manifest must resolve to the same data inside the worker
container. See [Sample YAML manifest](../api/sample_yaml.md) for the host-path
and symbolic-link rules.

### 4. Provision MongoDB independently

Use an existing managed MongoDB service or deploy the supplied independent
MongoDB stack. The application environment always selects MongoDB through
`MONGO_URI`.

For the supplied single-member replica set:

```bash
sudo install -d -o 999 -g 999 -m 0700 "$COYOTE3_MONGO_DATA_HOST_ROOT"
sudo install -d -o 999 -g 999 -m 0700 "$COYOTE3_MONGO_BACKUP_HOST_ROOT"
sudo install -d -o 999 -g 999 -m 0700 "$(dirname "$COYOTE3_MONGO_KEYFILE_HOST_PATH")"

openssl rand -base64 756 | sudo tee "$COYOTE3_MONGO_KEYFILE_HOST_PATH" >/dev/null
sudo chown 999:999 "$COYOTE3_MONGO_KEYFILE_HOST_PATH"
sudo chmod 0400 "$COYOTE3_MONGO_KEYFILE_HOST_PATH"

docker network create \
  --driver bridge \
  --subnet "$COYOTE3_MONGO_NETWORK_SUBNET" \
  --ip-range "$COYOTE3_MONGO_NETWORK_SUBNET" \
  --gateway "$COYOTE3_MONGO_NETWORK_GATEWAY" \
  "$COYOTE3_MONGO_NETWORK"
docker compose \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.mongo.yml \
  up -d
```

The `/29` MongoDB pool reserves eight addresses and provides approximately five
assignable container addresses. It accommodates the MongoDB member, the
one-shot replica-set initializer, and temporary backup or restore containers.
Use a larger dedicated pool before adding multiple replica-set members.

Set the MongoDB root credentials, host paths, network, replica-set name, and
application `MONGO_URI` in `.coyote3_env` before running this command. The
database container remains online when the Coyote3 application is rebuilt or
stopped.

Confirm the replica set and connectivity before continuing:

```bash
docker compose \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.mongo.yml \
  ps

mongosh "$MONGO_URI" --eval 'db.runCommand({ping: 1})'
```

For managed or center-operated MongoDB, perform the equivalent connectivity,
replica-set, authentication, and backup checks. The complete procedure is in
[MongoDB deployment and recovery](../operations/mongodb_deployment_and_recovery.md).

### 5. Validate and build the application

Validate the rendered production model, then build immutable application
images.

```bash
bash scripts/center_preflight.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  config --quiet

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  build
```

This step builds the frontend once. Production containers serve the compiled
assets and do not run the Vite development watcher.

### 6. Bootstrap the empty database

Load the application-owned permission and role catalogs, bundled HGNC and VEP
reference snapshots, and the first local superuser. Run this command only for
an empty first installation.

```bash
read -rsp "First administrator password: " FIRST_ADMIN_PASSWORD
echo

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps api \
  python scripts/bootstrap_database.py \
    --mongo-uri "$MONGO_URI" \
    --db "$COYOTE3_DB" \
    --username "admin.coyote3" \
    --email "admin@example.org" \
    --password "$FIRST_ADMIN_PASSWORD"

unset FIRST_ADMIN_PASSWORD
```

Do not add `--with-demo-center` to a clinical deployment. Bootstrap rejects a
partially initialized governance database and leaves an existing superuser
unchanged.

### 7. Start the production services

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d
```

Review the service state and startup logs:

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  ps

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  logs --tail=200 api worker beat proxy
```

Repeated container restarts are not a recovery strategy. Resolve failed
health checks or configuration errors before restarting a service.

### 8. Verify the public entry points

Build the externally visible application URL from `PUBLIC_BASE_URL` and
`SCRIPT_NAME`:

```bash
APP_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME}"

curl -fsS "$APP_URL/api/v1/health"
curl -fsSI "$APP_URL/"
curl -fsSI "$APP_URL/public/catalog"
curl -fsSI "$APP_URL/docs-site/"
curl -fsSI "$APP_URL/api/v1/docs"
```

Confirm that requests use TLS, both the prefix with and without a trailing
slash work, and no internal container port is exposed to users. Sign in with
the first administrator and immediately create named operator accounts.

### 9. Import the center clinical configuration

Import reviewed ASP, ASPC, and ISGL JSON documents through the administration
interface. Importing fills the managed form; an authorized operator must still
review and save the document.

Before sample ingest, verify that each production assay has:

1. one active ASP with the correct assay group, family, platform, and gene
   scope;
2. one active ASPC for the required subpanel or an explicitly accepted base
   configuration;
3. the enabled analysis types, intent-specific filters, and report sections;
4. every required analysis-specific ISGL.

### 10. Reconcile MongoDB indexes

Index management is explicit and idempotent. Inspect the plan before applying
missing compatible indexes:

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps api \
  python scripts/manage_mongo_indexes.py plan

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps api \
  python scripts/manage_mongo_indexes.py apply
```

`apply` creates missing compatible indexes and never drops an index. Retire an
obsolete index only through a reviewed maintenance operation. See
[Maintenance and quality](../operations/maintenance_and_quality.md).

### 11. Complete production acceptance

Use center-approved synthetic or de-identified validation samples to verify:

- local and configured LDAP authentication;
- role and permission boundaries;
- one representative DNA workflow and one representative RNA workflow;
- watch-folder ingest, worker state, and ingest audit events;
- SNV, CNV, fusion, coverage, expression, and classification views when
  enabled by the sample ASPC;
- curation, comments, report preview, report save, and export;
- the public catalog and prefixed documentation routes;
- application and MongoDB restart behavior.

Follow [Target-center acceptance](../operations/target_center_acceptance.md)
and store the signed evidence outside the repository.

### 12. Establish and test backups

Create a MongoDB archive and its checksum metadata:

```bash
read -rsp "MongoDB backup URI: " MONGO_BACKUP_URI
echo
export MONGO_BACKUP_URI
```

Use a dedicated MongoDB account with the center-approved backup permissions;
do not place this URI in Git. For the supplied Docker replica set, run:

```bash
scripts/mongo_backup_archive.sh \
  --mongo-uri "$MONGO_BACKUP_URI" \
  --out-dir "$COYOTE3_MONGO_BACKUP_HOST_ROOT" \
  --label first-production-release \
  --docker-network "$COYOTE3_MONGO_NETWORK"
```

Copy the archive off-host and test restoration into an isolated database. A
backup that has not passed a restore test is not accepted recovery evidence.
See [Backup and recovery](../operations/backup_restore_and_snapshots.md).

```bash
unset MONGO_BACKUP_URI
```

## Subsequent deployment

Use this procedure for a later v4 release or a production configuration
change. Do not bootstrap a populated database.

### 1. Review the release

Read the release notes and identify changes to environment variables,
configuration contracts, indexes, RBAC catalogs, or data schemas. Record the
currently deployed Git tag and image identifiers before changing anything.

```bash
git describe --tags --always
docker compose --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  images
```

### 2. Create and verify a pre-deployment backup

Create a fresh MongoDB archive, transfer it off-host, and verify its checksum.
For a release that changes stored data, restore that archive in an isolated
environment before approving production deployment.

Load the dedicated backup URI into the operator shell as described in the
first-installation backup step before running the archive command.

```bash
scripts/mongo_backup_archive.sh \
  --mongo-uri "$MONGO_BACKUP_URI" \
  --out-dir "$COYOTE3_MONGO_BACKUP_HOST_ROOT" \
  --label pre-deployment \
  --docker-network "$COYOTE3_MONGO_NETWORK"
```

### 3. Check out and validate the new release

```bash
git fetch --tags
git checkout <NEW_RELEASE_TAG>

scripts/validate_env_secrets.sh --env-file .coyote3_env
bash scripts/center_preflight.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  config --quiet
```

Add or change environment values only when the release documentation requires
it. Retain the production database URI, database names, secrets, public URL,
and durable host roots unless an approved infrastructure change replaces them.

### 4. Build before replacing running services

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  build
```

Building first reduces the application replacement window and confirms that
all release images can be produced before running containers are changed.

### 5. Run release-required maintenance

Run only the commands named by the release notes.

To add newly bundled system permissions or roles while preserving center roles
and grants:

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps api \
  python scripts/sync_rbac_catalog.py \
    --mongo-uri "$MONGO_URI" \
    --db "$COYOTE3_DB" \
    --bam-db "$BAM_DB"
```

Inspect and apply newly declared indexes when required:

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps api \
  python scripts/manage_mongo_indexes.py plan

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps api \
  python scripts/manage_mongo_indexes.py apply
```

Do not rerun `bootstrap_database.py`. Do not execute an old migration merely
because it exists in a previous release. Stored-data changes require a
release-specific, reviewed procedure.

### 6. Replace the application services

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d
```

MongoDB remains online because it is not part of this Compose model. Never use
`docker compose down -v`; the Coyote3 wrapper rejects that operation.

### 7. Verify the release

Repeat the service, URL, authentication, worker, representative DNA/RNA,
report, export, and public-route checks used during first installation. Review
API and worker logs for errors and confirm that no service is entering a
restart loop.

Record the deployed tag, image digests, backup archive, index plan, RBAC sync
result, verification evidence, operator, and deployment time.

### 8. Roll back when verification fails

Stop further clinical activity, check out the previous release tag, rebuild
the previous images, and start the previous application model:

```bash
git checkout <PREVIOUS_RELEASE_TAG>

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  build

scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d
```

Do not restore MongoDB simply because the application was rolled back. Restore
the verified pre-deployment archive only when the failed release changed
stored data and the approved rollback procedure requires database restoration.
Preserve the failed-release logs and audit evidence for investigation.

## Routine restart without a release change

A host restart or application-only restart does not require bootstrap, RBAC
synchronization, or index creation. Start the independent MongoDB service
first, confirm it is healthy, and then run:

```bash
scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d
```

Complete the health, authentication, worker, and public-route checks before
returning the service to clinical use.
