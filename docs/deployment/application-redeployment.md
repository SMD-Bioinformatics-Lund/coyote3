# Restart or redeploy an existing installation

Use this procedure when the application release, center configuration and database
contracts are unchanged. It recovers stopped services or replaces application
containers using existing images. It does not initialize databases, change secrets,
install catalogs or migrate data.

If changing code, dependencies, configuration or the container UID/GID, use
[Upgrade an existing installation](application-upgrades.md). Rebuilding an image
can resolve different base images or dependencies, so a rebuild is a release
operation rather than an exact redeployment.

## 1. Select the existing installation

Run from the checkout of the recorded deployed release, in one Bash shell.
Use the existing private environment file and exact Compose project name:

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

git rev-parse HEAD
coyote_compose ps --all
coyote_compose images
```

Replace the first two example assignments with the installation's recorded
values. Confirm the commit and images match the deployed release record.
Stop if image tags were rebuilt or overwritten; restore the recorded images
before continuing. Do not select a new project name to work around startup errors.

## 2. Verify persistent dependencies

- Confirm the independently managed MongoDB service is available and its application
  and identity endpoints have a writable replica-set primary.
- Confirm the original data/log paths, center files and database names are selected.
- Verify the external network exists:

```bash
docker network inspect "$COYOTE3_APP_NETWORK" --format '{{.Name}} {{.Driver}}'
bash scripts/deployment/validate_env_secrets.sh --env-file "$COYOTE_ENV_FILE"
coyote_compose config --quiet
```

An unexpectedly missing network, data directory or Redis volume requires inspection.
Do not accept newly created empty storage as recovery of an existing installation.
Restore the recorded storage and deployment identity before continuing. These
checks do not authorize provisioning a new database or running bootstrap.

## 3. Choose one restart operation

For stopped services or recovery after a host restart, start existing images:

```bash
coyote_compose up -d --no-build --pull never --wait --wait-timeout 180
```

For deliberate replacement of the containers, arrange a maintenance window and
pause submissions. Allow active ingest/report work to finish before replacement:

```bash
coyote_compose stop proxy beat
coyote_compose exec -T worker celery -A api.celery_app:celery_app inspect active
coyote_compose exec -T worker celery -A api.celery_app:celery_app inspect reserved
coyote_compose exec -T worker celery -A api.celery_app:celery_app inspect scheduled
```

Confirm every worker responds and has no active task before proceeding. Check
reserved/scheduled work and pause external producers as appropriate; stopping the
browser proxy alone does not stop pipeline submissions. Keep Redis and its volume.
Then replace containers without fetching or rebuilding images:

```bash
coyote_compose stop -t 300 api worker monitor
coyote_compose up -d --no-build --pull never --force-recreate --wait --wait-timeout 180
```

Do not continue if tasks remain active or a worker cannot be inspected. A stop
timeout can terminate work; it is not evidence that tasks completed successfully.
Neither operation requires `down`, volume removal, RBAC synchronization or index changes.

## 4. Verify before reopening access

```bash
coyote_compose ps
coyote_compose logs --tail=100 api worker beat proxy
COYOTE_BROWSER_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME%/}"
curl --fail --show-error "$COYOTE_BROWSER_URL/api/v1/health"
curl --fail --show-error --output /dev/null "$COYOTE_BROWSER_URL/"
curl --fail --show-error --output /dev/null "$COYOTE_BROWSER_URL/docs-site/"
```

Sign in with an existing account, open an authorized sample, verify an existing
report and confirm worker processing resumes. Check that no unexpected ingest job
was lost or duplicated. Record the restart and verification result before resuming
submissions. Do not create replacement administrator accounts through bootstrap.

For the example direct HTTP listener, the URL is `http://localhost:6802/coyote3/`.
HTTPS requires a TLS ingress; changing `COYOTE3_NGINX_PUBLIC_SCHEME` does not create one.

## If verification fails

Keep clinical submissions paused and inspect the reported service error. Check
image identity, configuration, mounts, MongoDB readiness and Redis state. Do not
change database names, rotate secrets, delete volumes or repeatedly recreate
containers as a recovery strategy. Restore the recorded configuration/images if
they changed; a stored-data recovery requires the reviewed backup/restore procedure.
