# Upgrade an existing installation

Use this procedure for a later application release or a reviewed change to the
configuration of an existing installation. It preserves installed accounts,
clinical configuration, samples and reference databases. **Do not run database
bootstrap or the legacy v2/v3 migration merely to update the application.**

Complete each numbered step before proceeding. A command failure, incompatible
configuration, incomplete backup or missing migration procedure stops deployment.
There is no universal migration command: releases that change stored contracts
must supply their own reviewed migration and recovery instructions.

## 1. Select the installation and maintenance record

Run from the current deployed checkout, in one Bash shell. Select the existing
installation's environment file and Compose project name:

The [environment file](../configuration/environment-file.md) is the private
`NAME=value` configuration selected by `--env-file`. Its
[key reference](configuration-reference.md#environment-variable-reference) lists
required values and exact defaults. `COYOTE_ENV_FILE` and `COYOTE_PROJECT` below
are shell helper variables selecting the file and existing deployment name.

```bash
COYOTE_ENV_FILE="/srv/coyote3/config/production.env"
COYOTE_PROJECT="coyote3-prod"
set -a
. "$COYOTE_ENV_FILE"
set +a

coyote_compose() {
  bash scripts/deployment/compose-with-version.sh \
    -p "$COYOTE_PROJECT" --env-file "$COYOTE_ENV_FILE" \
    -f deploy/compose/docker-compose.yml "$@"
}

read -r -p "New private absolute directory for this deployment record: " COYOTE_RELEASE_RECORD
case "$COYOTE_RELEASE_RECORD" in /*) ;; *) echo "Use an absolute path"; return 1 2>/dev/null || exit 1 ;; esac
(umask 077; mkdir "$COYOTE_RELEASE_RECORD")
```

Replace the example environment-file and project assignments with
the installation's existing values. The record directory must be new, outside the checkout,
and on storage with room for configuration, images and backups. Do not continue
if directory creation fails. Keep its contents private; it will contain secrets.

Read the target release notes before changing the checkout. Identify required
configuration keys, schema changes, RBAC/index maintenance, compatibility and
rollback restrictions. Agree on the maintenance window and recovery plan.
For center files that still declare families, manifest keys, analysis bindings or
base query settings, follow the [application-owned definitions upgrade](center-configuration.md#application-owned-definitions)
before validating the new configuration release.
For configuration-only changes, retain the current reviewed commit throughout.

## 2. Preserve the current release and configuration

Record the current code and running images before any build changes their tags:

```bash
git status --short
git rev-parse HEAD > "$COYOTE_RELEASE_RECORD/previous-commit.txt"
coyote_compose ps --all > "$COYOTE_RELEASE_RECORD/previous-services.txt"
coyote_compose images > "$COYOTE_RELEASE_RECORD/previous-images.txt"
cp -p "$COYOTE_ENV_FILE" "$COYOTE_RELEASE_RECORD/previous.env"
cp -a "$COYOTE3_CENTER_CONFIG_HOST_DIR" "$COYOTE_RELEASE_RECORD/previous-center"

docker ps -aq --filter "label=com.docker.compose.project=$COYOTE_PROJECT" \
  > "$COYOTE_RELEASE_RECORD/container-ids.txt"
while read -r container_id; do
  docker inspect --format '{{.Config.Image}} {{.Image}}' "$container_id"
done < "$COYOTE_RELEASE_RECORD/container-ids.txt" \
  | sort -u > "$COYOTE_RELEASE_RECORD/image-map.txt"
mapfile -t COYOTE_IMAGE_IDS < <(awk '{print $2}' "$COYOTE_RELEASE_RECORD/image-map.txt" | sort -u)
```

Confirm the map contains every service image and has no conflicting IDs for the
same image tag. Do not continue with an empty or incomplete map. Save those exact
images, including proxy and Redis, before building replacements:

```bash
docker image save --output "$COYOTE_RELEASE_RECORD/previous-images.tar" "${COYOTE_IMAGE_IDS[@]}"
sha256sum "$COYOTE_RELEASE_RECORD/previous-images.tar" > "$COYOTE_RELEASE_RECORD/previous-images.tar.sha256"
```

Also preserve private Compose overrides, TLS ingress configuration and any other
center deployment assets in the protected record. Resolve uncommitted tracked
changes before switching releases; do not reset, clean or discard local work.
Retain the original database endpoints/names, secrets, network, project name and
persistent roots unless the approved change explicitly replaces them.

## 3. Select, validate and build the target release

For an application update, fetch and select the exact reviewed tag:

```bash
read -r -p "Reviewed target release tag: " COYOTE_TARGET_RELEASE
git fetch --tags
git checkout --detach "$COYOTE_TARGET_RELEASE"
git rev-parse HEAD
```

Confirm the resolved commit matches the approved release. For a configuration-only
change, skip the checkout. Review only the required environment/center changes;
never recopy example files over the center's configuration. Prepare changed center
files as a separate reviewed directory and select it in the private environment.
Keep the previous directory available for rollback.

Changes to database endpoints, data roots, project/network identity or the Redis
password require a separate infrastructure transition plan. This procedure assumes
those persistent resources remain the same; changing them can select empty state
or interrupt existing clients. Do not treat such changes as a routine image update.

Reload the environment after edits and validate/build before interrupting service:

```bash
set -a
. "$COYOTE_ENV_FILE"
set +a
bash scripts/deployment/validate_env_secrets.sh --env-file "$COYOTE_ENV_FILE"
coyote_compose config --quiet
coyote_compose pull --ignore-buildable
coyote_compose build
```

Validate the mounted center configuration in a one-off container without starting
API or workers or writing to MongoDB:

```bash
coyote_compose run --rm --no-deps -T api python3 -c '
from api.config.loaders.filter_flags import load_filter_flag_metadata
from api.config.loaders.contact import load_contact_config
from api.config.paths import CONTACT_CONFIG_PATH
load_filter_flag_metadata()
load_contact_config(CONTACT_CONFIG_PATH, organization_name="Validation", public_base_url="", script_name="")
print("Center configuration valid")
'
```

Building includes frontend and documentation settings as well as the API. It does
not replace currently running containers. If validation/build fails, the current
application continues to use its existing images. Resolve the error before the
maintenance window; do not proceed with a partly built release.

## 4. Pause writes and drain active work

Notify users and pause external pipeline producers and manual submissions.
Stop public application access and scheduled dispatch, then inspect workers:

```bash
coyote_compose stop proxy beat
coyote_compose exec -T worker celery -A api.celery_app:celery_app inspect active
coyote_compose exec -T worker celery -A api.celery_app:celery_app inspect reserved
coyote_compose exec -T worker celery -A api.celery_app:celery_app inspect scheduled
```

Require responses from all workers. Allow active tasks to complete; resolve reserved
or scheduled tasks according to the release's queue compatibility plan. Do not
purge Redis to obtain an empty queue. Check that direct API clients and other
writers have stopped, then stop remaining application writers:

```bash
coyote_compose stop -t 300 api worker monitor
```

Redis and MongoDB remain available. A stop timeout may kill work: investigate any
unfinished job before continuing. Schema migrations must not run concurrently with
old writers. Keep all producers paused until verification is complete.

## 5. Back up the quiesced installation

Create verified backups for **every distinct MongoDB deployment** used by the four
logical database endpoints. One archive covers them only when they share a server
and the backup account can read all required databases. Use a dedicated backup
account and an endpoint reachable from the backup container:

```bash
read -rsp "MongoDB backup URI: " MONGO_BACKUP_URI
printf '\n'
bash scripts/database/mongo_backup_archive.sh \
  --mongo-uri "$MONGO_BACKUP_URI" \
  --out-dir "$COYOTE_RELEASE_RECORD/mongo" \
  --label pre-upgrade --docker-network "$COYOTE3_APP_NETWORK"
unset MONGO_BACKUP_URI
```

Repeat for independent identity, knowledgebase or BAM deployments as needed. The
archive tool verifies gzip integrity and records a checksum and metadata; this
does not replace a MongoDB restore test.
Confirm every invocation succeeded and copy the protected backups off-host.
For stored-data changes, require an isolated restore test and the approved recovery
procedure before applying the change. Preserve the independently managed Redis
volume and its recoverable backup according to the center's backup policy.

With application writers stopped, archive reports and ingest files as well:

```bash
tar -cpf "$COYOTE_RELEASE_RECORD/application-data.tar" -C "$COYOTE3_DATA_HOST_ROOT" .
sha256sum "$COYOTE_RELEASE_RECORD/application-data.tar" > "$COYOTE_RELEASE_RECORD/application-data.tar.sha256"
```

Verify this completed without unreadable-file errors. Retain logs and audit evidence.
A database backup alone does not preserve generated report files or external input
mounts. Back up any additional center-managed assets required for recovery.

## 6. Apply only required release maintenance

Use the exact migration instructions supplied with the reviewed release. Review
its dry-run/plan, scope, counts and recovery requirements before applying changes.
If those instructions are missing for a changed stored contract, keep the old
installation in service or restore it without applying the new release.

When the release adds system permissions or roles, review and apply its bundled
catalog through the identity maintenance tool:

```bash
coyote_compose run --rm --no-deps -T api python3 scripts/identity/sync_rbac_catalog.py --dry-run
coyote_compose run --rm --no-deps -T api python3 scripts/identity/sync_rbac_catalog.py
```

The first command is a plan; run the second only after approving that plan. This
uses the configured identity endpoint and preserves center roles and grants.
Do not execute it solely because an older guide listed it.

For declared index changes, inspect the plan first:

```bash
coyote_compose run --rm --no-deps -T api python3 scripts/database/manage_mongo_indexes.py plan
```

After review, create compatible missing indexes:

```bash
coyote_compose run --rm --no-deps -T api python3 scripts/database/manage_mongo_indexes.py apply
```

`apply` does not drop indexes. Conflicts or obsolete indexes require their own
reviewed operation. Retain plans/results and migration evidence in the deployment
record. If maintenance fails, keep writers stopped and follow its recovery plan;
do not start old or new services against a partially migrated database.

### Database-managed query policies and annotation wording

When upgrading from runtime TOML query policies, install the application seed rules
before starting the new API. The new runtime reads published database rules only. Complete
the protected-field cleanup in the [center configuration guide](center-configuration.md#application-owned-definitions),
RBAC synchronization and index plan above. Assay groups must already be registered.

```bash
coyote_compose run --rm --no-deps -T api python3 scripts/bootstrap/install_query_rules.py --actor ADMIN_USERNAME
coyote_compose run --rm --no-deps -T api python3 scripts/bootstrap/install_query_rules.py --actor ADMIN_USERNAME --apply
```

Review the first command's plan before applying it. Existing scopes, including retired
ones, are preserved. The installer uses application-owned criteria and does not import
old center files. Compare archived center policies with the planned and existing
rules, then recreate any required differences through reviewed publications in the
editor before reopening clinical access. Validate effective policies for representative
sample scopes after startup.

For automatic Tier III annotations, move previous tumor-type descriptors into
`terminology.automatic_annotation_tumor_type` on reviewed reporting-rule successors.
Do not edit published documents or their hashes directly. Automatic text remains
unavailable until suitable wording is published; ordinary classification is unaffected.

## 7. Replace services and verify

Use the built images without rebuilding or fetching another version:

```bash
coyote_compose up -d --no-build --pull never --force-recreate --wait --wait-timeout 180
coyote_compose ps
coyote_compose logs --tail=100 api worker beat proxy
COYOTE_BROWSER_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME%/}"
curl --fail --show-error "$COYOTE_BROWSER_URL/api/v1/health"
curl --fail --show-error --output /dev/null "$COYOTE_BROWSER_URL/"
curl --fail --show-error --output /dev/null "$COYOTE_BROWSER_URL/docs-site/"
```

Keep clinical submissions paused while verifying existing-account login, permissions,
an authorized existing sample and report, worker processing and the release's approved
validation workflow. Check audit events, report generation and export behavior.
Health checks alone do not establish clinical acceptance. Beat/worker startup may
resume pending work; complete queue compatibility checks before this step.

Record target commit, image IDs, center configuration revision, migrations, backup
identifiers, operator, time and acceptance results. Resume users and pipeline
producers only after acceptance. If verification fails, follow step 8.

## 8. Recover a failed deployment

Stop new clinical activity and application writers, preserving failure logs and
audit evidence. First determine whether the previous application is compatible
with the current database, queued work and generated files.

**Application-only rollback is allowed only when that compatibility is established.**
Restore the previous environment file, center configuration and private overrides
from the protected record, then source the restored environment. This includes
removing newly exported shell overrides that are absent from the previous file;
using a fresh Bash shell avoids retaining target-release values.

From the restored shell, set the same `COYOTE_ENV_FILE`, `COYOTE_PROJECT` and
`COYOTE_RELEASE_RECORD` and define `coyote_compose` as in step 1. Then:

```bash
git checkout --detach "$(cat "$COYOTE_RELEASE_RECORD/previous-commit.txt")"
sha256sum --check "$COYOTE_RELEASE_RECORD/previous-images.tar.sha256"
docker image load --input "$COYOTE_RELEASE_RECORD/previous-images.tar"
while read -r image_tag image_id; do
  docker image tag "$image_id" "$image_tag"
done < "$COYOTE_RELEASE_RECORD/image-map.txt"
coyote_compose config --quiet
coyote_compose up -d --no-build --pull never --force-recreate --wait --wait-timeout 180
```

Use the saved exact images; rebuilding an old tag can resolve different dependencies.
Repeat the service, login, worker, existing-report and public-route checks before
reopening access. Record the rollback result.

If stored data changed incompatibly, **do not start the previous application first**.
Keep writers stopped and execute the release-approved reverse migration or coordinated
database/files/queue restoration. Preserve post-backup clinical work and audit
records before any restore; restoring an old archive can discard newer work.
There is no automatic database restore in this procedure. The center's
[backup and recovery runbook](../operations/backup-and-recovery.md) supplies the
restoration commands and required verification.
