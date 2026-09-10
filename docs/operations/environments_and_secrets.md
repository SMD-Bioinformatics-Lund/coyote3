# Environments And Secrets

## Environment separation

Use isolated stacks and databases for each environment:

- **prod**: `deploy/compose/docker-compose.yml`
- **stage**: `deploy/compose/docker-compose.stage.yml`
- **dev**: `deploy/compose/docker-compose.dev.yml`

## Browser session cookie

Set `API_SESSION_COOKIE_NAME` in each deployment's env file, for example
`coyote3_dev_api_session` for dev and `coyote3_prod_api_session` for production.
Change this value when copying the example env to another environment. Modern
and legacy Compose both pass it to the API. The browser UI and interactive API
docs use the same HttpOnly session cookie; they do not need separate cookie names.
Workers, beat, Redis, MongoDB, and static documentation do not need browser
session cookies. Programmatic clients using cookie authentication must pass the
configured name to the API client helper's `cookie_name` argument.

Use distinct names for deployments on the same hostname, even when their ports
or URL prefixes differ: the session cookie currently uses path `/`. After changing
the name, recreate the API container and log in again. No frontend rebuild is
required for this setting.

## Default port matrix

Each stack exposes one HTTP entrypoint through nginx. Web UI, FastAPI, and docs
are routed behind that proxy; Redis stays internal.

| Environment | HTTP proxy | Optional Mongo |
| --- | --- | --- |
| prod | 5815 | 5820 |
| stage | 8804 | 8808 |
| dev | 6801 | 6804 |
| test | 6811 | 6814 |

These defaults are encoded in the compose files. The copied env file uses the
single `COYOTE3_PORT` key when a center needs to override the active stack port.

## Host Drive Mounts Per Center

Centers can have different host filesystem layouts. Configure only the host data
root with `COYOTE3_DATA_HOST_ROOT` in the copied `.coyote3_*_env` file. Compose
mounts that directory at the fixed container path `/data` and also at the same
absolute host path inside API and Celery containers. The latter preserves
pipeline-declared source paths in the database. The API and Celery containers
use repository-defined locations `/data/coyote3_<env>/reports`,
`/data/coyote3_<env>/ingest_staging`, and `/data/coyote3_<env>/copied_sample_files/yaml` for
application workspaces. Edit Compose only for permanent center infrastructure
mounts that are outside the data root.

Examples:

- Stage: `deploy/compose/docker-compose.stage.yml`
- Prod: `deploy/compose/docker-compose.yml`
- Dev: `deploy/compose/docker-compose.dev.yml`

For each volume mount, define both source path and access mode:

- Read-write (default): `"/center/data:/data"`
- Read-only: `"/center/reference:/reference:ro"`

Recommendation:

- Keep writable paths (`/data`, backups, runtime output) as `rw`.
- Use `:ro` for reference-only inputs that must not be modified by containers.
- Validate after edits with:
  `docker compose --env-file <env-file> -f <compose-file> config -q`

## Redis runtime policy

- All compose stacks pin Redis to `redis:7.4.3`.
- Redis is a shared cache dependency for API/UI and is required by default
  (`CACHE_REQUIRED=1`).
- A center can deliberately choose degraded mode (`CACHE_REQUIRED=0`); cache
  operations then become no-op on Redis outages and functionality continues with
  lower performance.

## Environment naming map

Runtime profile normalization:

- `production` -> `production`
- `development` / `dev` -> `development`
- `test` / `testing` -> `test`
- `validation` / `stage` / `staging` -> `validation`

Use `validation` in persisted profile fields for stage/staging environments.

## Database isolation

Recommended:

- separate Mongo instance per environment
- same DB name (`coyote3`) is acceptable with isolated instances
- app user credentials per environment

## Mongo credential roles

- `MONGO_ROOT_*`: bootstrap/admin operations
- `MONGO_APP_*`: application runtime access (least privilege)
- For the optional supplied Docker MongoDB stack, mongo-init creates
  `MONGO_APP_*` only on first startup of an empty Mongo data directory
- If volume already exists, create/rotate app user with `mongosh` using an admin-capable URI:

Example (existing volume/user rotation):

```bash
mongosh "<admin-mongo-uri>" --eval '
  db = db.getSiblingDB("'"${COYOTE3_DB:?COYOTE3_DB must be set}"'");
  var user = "'"${MONGO_APP_USER}"'";
  var pwd  = "'"${MONGO_APP_PASSWORD}"'";
  var roles = [
    {role: "readWrite", db: "'"${COYOTE3_DB:?COYOTE3_DB must be set}"'"},
    {role: "readWrite", db: "'"${IDENTITY_DB:?IDENTITY_DB must be set}"'"},
    {role: "readWrite", db: "'"${KNOWLEDGEBASE_DB:?KNOWLEDGEBASE_DB must be set}"'"},
    {role: "readWrite", db: "'"${BAM_DB:?BAM_DB must be set}"'"}
  ];
  var info = db.getUser(user);
  if (info) { db.updateUser(user, {pwd: pwd, roles: roles}); print("updated"); }
  else       { db.createUser({user: user, pwd: pwd, roles: roles}); print("created"); }
'
```

The supplied Docker MongoDB deployment is reachable through its dedicated
network and is bound to loopback only for host-side maintenance. In local mode,
the external MongoDB deployment owns its own exposure and maintenance policy.

## Load-test isolation

An `ENV_NAME` label or separate MongoDB database alone does not isolate a load run.
Use explicit application, identity, and BAM URI/name pairs pointing only to
disposable resources, with synthetic accounts and fixtures. Prefer a disposable
knowledgebase; a shared read-only knowledgebase requires its operator's approval
and a test plan accounting for contention with other deployments. Keep Redis,
its `ingest`/`default` queues and result backend, report artifacts, ingest staging,
watch directories, and logs separate from clinical environments. Logical Redis
databases within one shared server still compete for memory and processing.

Set `ONCOKB_PUBLIC_LOOKUPS_ENABLED=0` and `CLINPGX_PUBLIC_LOOKUPS_ENABLED=0` for
load runs. Disable or mock other external fetches and integrations as applicable;
do not direct generated traffic at third parties. Store generator credentials and
configuration JSON in private untracked files mounted read-only. The
[load-testing guide](../testing/load_testing.md) defines the optional runner setup;
application secrets, including `REDIS_PASSWORD`, remain deployment requirements.

## Secrets handling

- Keep real values out of git
- Use `deploy/env/example.env` only as a template
- Rotate secrets on team membership changes
- Validate before deployment with `scripts/validate_env_secrets.sh`

## SMTP relay strategy

Preferred center-safe baseline is external SMTP relay (no host Postfix coupling):

```env
SMTP_HOST='mxis.skane.se'
SMTP_PORT='25'
SMTP_USE_TLS='0'
SMTP_USE_SSL='0'
SMTP_USERNAME=''
SMTP_PASSWORD=''
SMTP_FROM_EMAIL='CHANGE_ME_FROM_EMAIL'
```

Behavior guarantees:

- User create/invite/reset flows do not hard-fail if mail cannot be delivered.
- API/UI return warning + manual setup URL metadata when email send fails.
- This keeps admin workflows functional even when SMTP is temporarily unavailable.
