# Installation and data maintenance

First installation and later data maintenance are separate operations. The deployment
installer builds and starts application services. MongoDB and Redis have independent
lifecycle commands. The data maintenance command uses a running API
and does not build, start or recreate services.

## Entry point and profiles

Run `bash install.sh --help` from the checkout. `deploy`, `plan`, `app`, `mongo`, `redis`, `compose`,
`check`, `center`, `data`, `demo`, `watch` and `dependencies` share this entry point; implementation modules
live in `deploy/installer/`. Python 3.12 or later is required. The launcher prefers
`PYTHON_BIN`, then the checkout virtual environment, then a supported system Python.
Docker installation needs no server packages on the host. It needs Git and pip; the installer
stages its pinned wheel before building images. See [editable development](../sdk/uv-development.md).

| Selection | Default Compose files | Image tag |
| --- | --- | --- |
| `--environment prod` or `production` | Base | Application version |
| `--environment dev` or `development` | Base + dev | Version + `-dev` |
| `--environment stage` or `staging` | Base + stage | Version + `-stage` |
| `--environment test` or `testing` | Base + test | Version + `-test` |
| `demo` | Dedicated isolated demo stack | Demo build targets |

Both `--environment` and `ENV_NAME` accept short or full deployment names. An
explicit selection must agree with `ENV_NAME` after normalization. Without
`--environment`, the command derives it from the environment file, allowing an
explicit process-environment override. Use `--legacy` for the maintained older-host
Compose definitions. `--overlay FILE` appends an overlay; repeated
`--compose-file FILE` options replace the default file selection entirely.
Keep the same environment file, project name and ordered overlays for every operation.

For fast development, run native processes with
`install.sh watch --env-file FILE -- COMMAND`; it requires `ENV_NAME=dev` or
`development`. Docker development mounts backend sources but does not watch or
automatically restart backend processes. Restart affected services explicitly after
Python edits; rebuild and recreate them for dependency or image changes. Vite hot
updates remain enabled for frontend/CSS edits in both local and Docker development.
See [editable development](../sdk/uv-development.md) for commands.

These deployment names are independent of the sample's clinical profile.
Samples use `production`, `development`, `testing` or `validation`; the installer
does not translate `staging` into sample `validation`. See the
[environment naming map](environments-and-secrets.md#environment-naming-map).

Preview a regular deployment using local files only:

```bash
bash install.sh plan --environment stage --env-file .stage.env --project coyote4-stage
bash install.sh deploy --environment stage --env-file .stage.env --project coyote4-stage
bash install.sh compose --env-file .stage.env --project coyote4-stage ps
```

`plan` does not execute subprocesses, contact services or prepare storage. It
checks local selections and secret placeholders; it cannot establish that a
network, database or image is ready. `deploy` logs timestamped stages, streams
build output and stops at the first failure. It does not automatically roll back
completed database operations. `NO_COLOR=1` disables terminal colors.

Use [demo installation](demo-installation.md) for Docker or native demonstrations.
Demo settings cannot be substituted into an ordinary production profile.

## Independent infrastructure and application

Start MongoDB, then Redis, then deploy the application. Each can run natively or
in Docker, independently of the other selections. Application installation only
checks its configured connections; it never starts or stops either server.

Keep server configuration separate from application credentials. The examples are
`deploy/env/example.mongo-server.env`, `deploy/env/example.redis-server.env` and
`deploy/env/example.env`. Copy them to private files and review the settings before use.
For Docker, provision the selected external network and MongoDB storage/keyfile first,
following [MongoDB setup](mongodb-first-setup.md).

For example, Docker databases with a native staging application:

```bash
./install.sh mongo start --mode docker --environment stage --env-file .mongo-stage.env
./install.sh redis start --mode docker --environment stage --env-file .redis-stage.env
./install.sh deploy --mode native --environment stage --env-file .app-stage.env
```

Change the application's mode to `docker` to use containers. For a provisioned native
database service, use its systemd unit instead:

```bash
./install.sh mongo start --mode native --env-file .mongo-stage.env --unit mongod.service
./install.sh redis start --mode native --env-file .redis-stage.env --unit redis-server.service
```

Native infrastructure commands control existing services. They do not install MongoDB
or Redis, create database users, initialize a native replica set or change system files.
The caller needs permission to control the selected unit; the installer does not invoke
`sudo`. Add `--user` for an existing user service. Alternatively set `COYOTE4_MONGO_UNIT`
or `COYOTE4_REDIS_UNIT` in the corresponding server file. `mongo --knowledgebase` selects
the separately provisioned knowledgebase instance and `KNOWLEDGEBASE_MONGO_UNIT`.

Both server commands provide `plan`, `start`, `stop`, `restart`, `status` and `logs`.
Their Docker projects are separate from the application. MongoDB startup waits for
server health and runs the existing replica-set initializer. Neither command removes data.

The application file must supply all four MongoDB endpoint/database selections and
`CACHE_REDIS_URL`, `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND`. The application no longer
constructs these URLs from `REDIS_PASSWORD`; that setting belongs to the Redis server.

| Client runtime | Server location | Hostname in the client URL |
| --- | --- | --- |
| Native | Native or Docker with a published local port | `127.0.0.1` and the listening/published port |
| Docker | Docker on the shared application network | Service alias, such as `mongo-app` or `redis` |
| Docker | Native host service | `host.docker.internal` and a host interface reachable from Docker |

Container `127.0.0.1` refers to that container. A native server bound only to loopback
may not accept connections through Docker's host bridge. MongoDB replica-set member
addresses must also be reachable by the client, or a single-member connection must
explicitly select `directConnection=true`. Database names alone do not isolate users;
retain the reviewed database grants and credentials.

For existing Docker installations, retain the Redis data volume: set
`COYOTE4_REDIS_VOLUME` to its existing name in the new Redis server file. Stop the old
Redis container before starting the independent server against that volume. Do not run
two Redis processes against the same files, remove volumes or use `--remove-orphans`
as an upgrade shortcut. Merely changing project names does not move existing data.

## Native application on WSL or Linux

Native deployment requires Python 3.12+, uv, Git, Node.js 22+, npm, curl, Nginx 1.19.5+ and an
available systemd user manager. Install the runtime libraries used by the backend,
including the report-rendering system dependencies, before deployment. The installer
checks executable availability; it does not install OS packages or enable systemd.
MongoDB and Redis must already accept the configured application connections.

Edit the application file's existing connection keys for the selected client location.
For native clients using locally published ports, use the MongoDB selections in
`deploy/env/example.mongo-local.env` and Redis URLs such as the following, with actual
percent-encoded credentials. The MongoDB example's `directConnection=true` is intended
for a single-member local replica set, not multi-node failover.

```dotenv
CACHE_REDIS_URL=redis://:ENCODED_PASSWORD@127.0.0.1:6379/0
CELERY_BROKER_URL=redis://:ENCODED_PASSWORD@127.0.0.1:6379/1
CELERY_RESULT_BACKEND=redis://:ENCODED_PASSWORD@127.0.0.1:6379/2
```

Keep `COYOTE4_PORT` consistent with the intended local browser port. Set the center
directory to the reviewed host directory, using `COYOTE4_CENTER_CONFIG_DIR`; native
deployment does not mount container paths. `${PWD}` references in native environment
files resolve from the checkout root without shell execution.

```bash
./install.sh plan --mode native --environment stage --env-file .app-stage.env
./install.sh deploy --mode native --environment stage --env-file .app-stage.env
./install.sh app status --mode native --env-file .app-stage.env
./install.sh app logs --mode native --env-file .app-stage.env
./install.sh app stop --mode native --env-file .app-stage.env
./install.sh app start --mode native --env-file .app-stage.env
```

The default state directory is `.runtime/coyote4-ENV/`, ignored by Git. Use
`--directory PATH` and `--project NAME` consistently for a different installation.
It contains a private virtual environment, generated web configuration, compiled
frontend/documentation, scheduler state and runtime settings. Data and logs default
there too; explicit `COYOTE4_DATA_ROOT`, `COYOTE4_RUNTIME_ROOT` and `LOG_ROOT` select other
absolute paths. Native runtime directories must belong to the operator with mode 700;
existing permissions are never silently changed. Credentials are stored with mode 600.
An existing runtime `.env` is rejected so it cannot override the explicitly selected file.

The installer synchronizes locked packages without changing the checkout's `.venv`,
reuses the normal bootstrap/index checks, then starts owned systemd user services.
It does not install the optional Demo package. Stop the native application before
redeploying its dependencies. Each running native installation needs distinct ports;
each concurrently developed checkout should have its own state and project name.

For staging, production and test deployments, the build refreshes the local server,
core and Atlas wheels even when their version numbers have not changed. Third-party
dependencies remain locked. `app start` and `app restart` reuse the installed packages;
they do not build source changes. To update a native staging installation:

```bash
./install.sh app stop --mode native --env-file .app-stage.env
./install.sh deploy --mode native --environment stage --env-file .app-stage.env
```

Do not use `--skip-build` when applying Python or frontend source changes.

The proxy binds loopback on `COYOTE4_PORT` (default 6801). Internal loopback ports are
8001 for API, 3000 for frontend, 8080 for documentation and 5514/UDP for monitoring.
Override them with `COYOTE4_NATIVE_API_PORT`, `COYOTE4_NATIVE_FRONTEND_PORT`,
`COYOTE4_NATIVE_DOCS_PORT` and `COYOTE4_MONITOR_PORT`. Staging/production serve
built frontend and documentation through one Nginx process. Development uses Vite
for frontend/CSS hot updates and the existing polling watcher for backend changes.
Documentation changes require a rebuild. Staging and production do not reload source.

Native services are transient: WSL shutdown stops them, and `app start` starts them
again after WSL is available. The installer does not enable boot persistence or
alter unrelated system services. This separates dependencies, state and lifecycle;
it is not an OS security sandbox. Native production still needs the installation's
approved TLS proxy, OS permissions, resource limits and operational acceptance.

### Status, logs and restarts

Run from the repository root with the same environment file, project and directory
used for installation:

```bash
./install.sh app status --mode native --env-file .app-stage.env
./install.sh app logs --mode native --env-file .app-stage.env
./install.sh app restart --mode native --env-file .app-stage.env
```

`app logs` shows recent journal entries. Follow all staging services live with:

```bash
journalctl --user -f -u 'coyote4-stage-*.service'
```

For one service, use its full unit name:

```bash
journalctl --user -u coyote4-stage-api.service -n 100 -f
```

The other service suffixes are `worker`, `maintenance-worker`, `beat`, `monitor`
and `proxy`; development also has `frontend`. Replace `coyote4-stage` with the
installation's project name when different. Press Ctrl+C to stop following logs;
this does not stop a service.

Application log files use `LOG_ROOT`, defaulting to `.runtime/coyote4-stage/logs/`.
Nginx errors are in the selected state directory:

```bash
tail -n 100 -f .runtime/coyote4-stage/nginx-error.log
```

Nginx startup diagnostics use stderr, captured by the proxy service's journal.
Configuration validation uses the same startup log selection. Native deployment
does not require write access to `/var/log/nginx` or root privileges for Nginx.

Use `app stop` before rebuilding a running native installation and `app start`
after a WSL restart. `app restart` reloads the selected environment and restarts
application processes; it does not rebuild installed Python packages or frontend
assets. Deploy again to apply staging code changes. MongoDB and Redis keep their
independent lifecycles.

## Background application services

| Service | Purpose | Effect of stopping it |
| --- | --- | --- |
| Ingestion worker | Relay ingestion jobs on the `ingest` queue | Submitted sample processing waits |
| Maintenance worker | Report artifact completion, audit retries, notifications and retention tasks | Those jobs remain pending |
| Beat scheduler | Dispatch recurring jobs, including durable ingestion dispatch | Recurring work is no longer queued |
| Monitor | Persist service errors and retry operational alert emails independently of Redis/Celery | Central error alerts stop; current web logging expects its receiver |

Keep ingestion and maintenance separate so long sample imports cannot occupy all
maintenance capacity. Run one Beat scheduler for each deployment schedule. These
services share backend packages and the same Docker image; native deployment runs
them as processes. Monitor supports operations rather than sample analysis, but
disabling it also requires a deliberate replacement for the configured web logging.

## First installation

MongoDB and Redis endpoints and, for Docker, the application network must be configured
before installation. Follow [first installation](first-installation.md) for provisioning.

```bash
bash install.sh deploy \
  --env-file "$COYOTE_ENV_FILE" \
  --project "$COYOTE_PROJECT" \
  --compose-file deploy/compose/docker-compose.yml
```

All eight stages run by default: network, directories, build, validate, bootstrap,
indexes, start and health. Native mode needs no Docker network. `--skip-build` uses
existing images or the prepared native environment and web builds.
`--steps` selects individual stages in their canonical order.

Fresh bootstrap creates two distinct local accounts and their RBAC catalog, then
installs application catalogs and the installed Atlas provider's HGNC/VEP
references in their configured databases. It installs no synthetic samples or
demo assay configuration; use the separate [demo deployment](demo-installation.md).
The fixed logins are `coyote4.sysadmin` and `coyote4.superuser`. Independent temporary
passwords are generated and printed once after account creation. Both accounts must
change their password on first API or browser use. Existing accounts are preserved.
The `--system-admin-*` options apply to the `sys_admin` account for account, access
and system operations. The `--superuser-*` options apply to the privileged recovery
account. The clinical administrator role, `admin`, is assigned separately through
authenticated user administration.
MongoDB connections without authentication produce a warning and do not block installation.

Production Redis TLS is optional. When selected, prepare the
[certificates](../operations/redis-tls.md) and repeat
`--compose-file deploy/compose/docker-compose.redis-tls.yml` after the base file on
every application installer invocation. The independent Redis server uses
`docker-compose.redis-tls-server.yml`. Include the applicable overlays in subsequent
upgrade and recovery commands.

| Module | Default contents | Disable flag |
| --- | --- | --- |
| Identity | Emergency superuser, named system administrator, permissions and roles | `--skip-users` |
| Application | Five biological groups, six group-scoped SNV policies and immutable baseline revisions | `--skip-application` |
| Knowledgebase | Bundled HGNC genes, VEP metadata and associated binary diagrams | `--skip-knowledgebase` |

`--skip-users` requires application and knowledgebase installation to be skipped
too: unauthenticated data installation is authorized only
by successful initial account creation in that same invocation. On a deployment with
existing accounts, use authenticated maintenance to add disabled modules later.

Automated creations use `created_by: "system"`. Existing populated reference
collections are preserved. No application data is seeded by ordinary API startup.

Existing deployments skip the entire bootstrap operation, even when a selected
module is missing. A partially recognized application/identity target is rejected.
An initial data failure after account creation does not reopen unauthenticated
seeding. Rerun deployment to finish indexes and startup while preserving existing
data, then complete missing modules with the maintenance command.

### Stages and operational flags

| Stage or option | Behavior |
| --- | --- |
| `network` | Inspect the pre-provisioned external application network and require the bridge driver. Never create or repair networking. |
| `directories` | Prepare configured host directories and permissions. |
| `build` | Build the selected deployment images unless `--skip-build` is set. |
| `validate` | Validate mounted center configuration, endpoint access and target state. |
| `bootstrap` | Install the default modules only on a fresh target; preserve existing deployments. |
| `indexes` | Plan, apply and verify application, identity and BAM indexes. Conflicts stop execution. |
| `start` | Verify initial accounts and required indexes, start services and wait for health. |
| `health` | Check API/browser routes through the rendered local proxy address. |
| `--system-admin-username USERNAME` | Initial system-administrator login, fixed to `coyote4.sysadmin`. Omit to use this default. |
| `--system-admin-email EMAIL` | Contact address for the initial system administrator (`sys_admin`). |
| `--superuser-username USERNAME` | Initial emergency superuser login, fixed to `coyote4.superuser`. Omit to use this default. |
| `--superuser-email EMAIL` | Contact address for the initial emergency superuser (`superuser`). |
| `--with-knowledgebase-indexes` | Separately plan, apply and verify knowledgebase indexes. |
| `--knowledgebase-maintenance-uri-file FILE` | Optional restricted URI file for fresh knowledgebase installation and selected knowledgebase indexes. It must target the configured endpoint/database; runtime credentials remain unchanged. |
| `--identity-maintenance-uri-file FILE` | Explicitly upgrade the restricted identity runtime role using a maintenance connection before validation. It does not enable MongoDB authorization or create runtime passwords. |

Selecting startup also checks Redis cache, broker and result-backend connections
before bootstrap or indexes. Secrets remain in the private environment file.
Do not enable shell tracing when handling credentials.

Every stage that runs application containers requires the existing external bridge,
even when `network` is omitted from `--steps`. A failed network inspection stops
before image builds or container operations. Provision missing infrastructure using
[first installation](first-installation.md#6-create-the-application-network).
The installer does not change firewall rules, forwarding settings or Docker daemon
configuration, and does not restart the Docker daemon.

For a configuration-only host preflight, use `bash install.sh check --resolved` with the same
environment file and ordered Compose files. It needs a supported host interpreter
with the application installed. It validates the resolved mounts, center files
(including optional report presentation) and directory mode bits. It does not
check network connectivity, MongoDB credentials, installation state, Redis or
indexes. Only `--prepare-directories` creates storage. The installer's `validate`
stage runs its application checks in the API image instead and needs no host SDK.

The local health-check URL uses the proxy's rendered published port and
`SCRIPT_NAME`. The separately displayed public URL uses `PUBLIC_BASE_URL`.
See [connection troubleshooting](../operations/troubleshooting.md#api-startup-fails-while-connecting-to-redis)
when containers cannot reach Redis.

### Direct initial bootstrap

The same freshness check applies when invoking Python directly through Compose:

```bash
coyote_compose run --rm --no-deps -it api sh -c '
  exec python3 scripts/bootstrap/bootstrap_database.py \
    --db "$COYOTE4_DB" --identity-db "$IDENTITY_DB"
'
```

The Python command supports the same three module skip flags. It has no `--force`
option and never uses an existing account name as unauthenticated authorization.
Configured connections need write access to the selected destination databases.
Knowledgebase installation can use the deployment installer's maintenance URI
without granting routine API connections write privileges.

## Authenticated data maintenance

Use an existing `admin`, `sys_admin` or `superuser` account with the running API.
Module selection is mandatory; `--force` never implicitly selects every module.
Authentication defaults to `--provider local`, matching initial bootstrap accounts.
Select `--provider ldap` for an LDAP account; an email-shaped login does not select
the provider automatically.
Host invocations require the application dependencies installed
in the selected interpreter; follow [developer environment setup](../getting-started/developer-environment.md).
Alternatively run the command in the built API image, as shown below; no host
virtual environment is needed for that path.

```bash
bash install.sh data \
  --api-url https://coyote.example.org/coyote4 \
  --modules application knowledgebase
```

Without `--force`, populated catalog collections are skipped. To repair selected
bundled modules:

```bash
bash install.sh data \
  --api-url https://coyote.example.org/coyote4 \
  --modules application knowledgebase --force
```

Inside Compose, use `coyote_compose run --rm --no-deps -it api python3
-m deploy.installer data --api-url http://api:8001 --modules knowledgebase --force`.
The API's configured connection needs write privileges on each selected database.

The command requests a username and hidden password, signs in using
`POST /api/v1/auth/sessions`, and completes a required first-login password change
using `POST /api/v1/auth/password/change`. It signs in again with the new password
because password changes invalidate previous sessions. It then calls
`POST /api/v1/admin/installation/data` and revokes its session afterward.
Passwords are never command arguments or stored in credential files.

The write request is `{"modules":["application","knowledgebase"],"force":true}`.
The application service checks the authenticated administrator role and rejects
temporary-password sessions. Client actors, seed paths and arbitrary documents are
not accepted. Newly created seed records use the system creator; updates and API
audit events record the authenticated administrator.

| Module | Forced maintenance boundary |
| --- | --- |
| `identity` | Restore missing bundled permissions/roles and union missing grants into system roles. Preserve local grants, activation state, every user, membership and password. Account creation/reset uses the normal account administration workflow. |
| `application` | Repair bundled group labels/descriptions and add missing identities. Preserve group availability, center-owned scopes and custom records. Changed bundled query content is published as a new version with retained hash-linked history; retired-only scopes stay retired. |
| `knowledgebase` | Repair system-created bundled reference IDs and content-addressed diagrams. A bundled publication or surviving system provenance identifies recoverable initial batches; active external releases are preserved. Preserve unknown/unattributed records and unrelated gene/release IDs. |

Demo installation is a separate package operation. It is available only in a
guarded demo deployment and does not appear as a maintenance module on ordinary
deployments. See [demo installation](demo-installation.md) for its CLI and
permission-protected administration page.

## Knowledgebase operations

Fresh bootstrap includes bundled references unless `--skip-knowledgebase` is selected.
Later additions and repairs require API maintenance with `--modules knowledgebase`;
the API's configured database connection needs write access during that operation.
Knowledgebase index maintenance remains a separately selected operation.

External releases use their source-specific
[knowledgebase import procedures](../reference/knowledgebases/README.md).
The maintenance command does not drop databases or bulk-reset collections.
For separately prepared HGNC/BioMart files, use the
[gene installation reference](../operations/hgnc-gene-installation.md).

## Standalone index maintenance

`manage_mongo_indexes.py` supports `status`, `plan`, `apply` and explicit `retire`.
Each accepts `--scope application|knowledgebase|all`; the default is `application`.
`application` includes the application, identity and BAM repositories and security
indexes. `knowledgebase` selects reference repositories only. Use `all` only when
maintenance of both groups is intended.

```bash
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py plan --scope application
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py apply --scope application --summary
coyote_compose run --rm --no-deps -T api \
  python3 -m deploy.installer.checks indexes-ready --scope application
```

Replace `application` with `knowledgebase` for separately scheduled reference index
maintenance. `--summary` prints counts and returns a nonzero status if any required
index remains missing or conflicting. Without it, the index command prints JSON.
`indexes` is a read-only precheck that permits missing indexes; `indexes-ready`
requires all selected indexes to be present. Neither check creates indexes.
No command automatically drops a conflicting index. Use the
[index maintenance runbook](../operations/maintenance-and-verification.md) for reviewed retirement.
