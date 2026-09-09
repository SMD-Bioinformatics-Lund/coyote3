# Legacy Docker deployment

These definitions target the Compose 1.29.2 configuration format and avoid
Docker Engine 18.09's unsupported `host-gateway` mapping. They are separate from
the modern definitions in `deploy/compose`; do not combine the two families.

Configuration rendering is tested with Compose 1.29.2 and modern Compose.
This is not certification of the application images on Docker 18.09. The host
CPU, kernel, runtime, and seccomp policy must support the current images.
Docker 18.09 and Compose v1 are obsolete; use this deployment only under the
center's explicit legacy-runtime policy. The legacy MongoDB servers and replica
initializers use `seccomp=unconfined` because Docker 18.09's default seccomp policy
blocks thread creation in MongoDB 7.0.41 and `mongosh`. This disables syscall
filtering for those four services, including their health checks. Authentication
and the other isolation controls remain enabled. Remove this exception when the
runtime is upgraded and startup and health checks pass with the default profile.
Legacy Redis also uses `seccomp=unconfined` to allow its background threads on
Docker 18.09. This exception is scoped to that Redis service; host kernel settings
and other deployments are not changed.

Legacy beat uses `ipc: none`: its single-process scheduler does not need
`/dev/shm`. This avoids allocating that tmpfs mount on the legacy host while
retaining a private IPC namespace. Workers retain their shared-memory mount.

## Definitions

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Compiled production application, API, workers, Redis, docs, and proxy; no MongoDB. |
| `docker-compose.dev.yml` | Standalone development stack with Vite, API reload, source mounts, and `-dev` application image tags. Use instead of the base file. |
| `docker-compose.stage.yml` | Stage image tags; combine with the base file. |
| `docker-compose.test.yml` | Test image tags and test runner; combine with the base file. |
| `docker-compose.mongo.yml` | Optional `mongo` and `mongo-kb` profiles, with authentication and separate replica sets. Can run as an independent project. |
| `docker-compose.mongo-backup.yml` | Optional server `/backup` mount; omit for externally managed backups. |
| `docker-compose.storage.example.yml` | Optional read-only input mounts shared by API, worker, and beat. |
| `docker-compose.host.yml` | Optional `host.docker.internal` mapping to an explicitly configured host IP. |

MongoDB servers and replica initializers are pinned to `mongo:7.0.41`; the modern
deployment retains MongoDB 8.2. There is no MongoDB Dockerfile: these services
use the official image directly. Initialization scripts, proxy configuration,
application Dockerfiles, and application settings are reused from the current
repository. Development and test services follow the modern definitions. The
load-test overlay is not provided here. There is no implicit project name; always
pass `-p` explicitly.

The selected definition controls image tags, just as in modern Compose:
`<version>-dev`, `<version>-stage`, `<version>-test`, or `<version>` for production.
`ENV_NAME` controls application branding; changing it alone does not select a
development server or change image tags. Upstream images such as Node, MongoDB,
Redis, and Nginx retain their upstream version tags. Compose project names isolate
containers and named volumes; configure distinct networks, ports, and storage
paths in each environment file.

Development is a standalone definition because Compose 1.29.2 cannot remove an
inherited frontend build with `!reset`, or extend services with dependencies.
It uses native Compose settings and the shared application Dockerfiles.

## Configuration

Use `deploy/env/example.env` as the starting point for a private env file.
Complete all secrets, public URL, database names, and storage paths as described
in the [configuration reference](../../docs/start_here/configuration.md).
Never commit a completed environment file.

| Setting | Legacy requirement |
| --- | --- |
| `COYOTE3_MONGO_URI` | Explicit URI; the old `MONGO_URI` alias is not consulted. |
| `COYOTE3_DOCKER_HOST_IP` | Only required with `docker-compose.host.yml`. Numeric host IP reachable from the application network; no automatic gateway substitution. |
| `COYOTE3_VERSION` | Export from `api/version.py` before application Compose commands. |
| `COYOTE3_DATA_HOST_ROOT` | Shared application storage root, for example `/data/coyote3`. The application creates `coyote3_dev`, `coyote3_prod`, `coyote3_test`, or `coyote3_stage` according to `ENV_NAME`, with reports and ingest working directories inside. |

Pipeline input locations remain separate mounts in the storage overlay. Prepare
the application root with write access for `COYOTE3_UID:COYOTE3_GID`; startup
creates its environment subdirectories without changing ownership of existing files.
Existing installations must follow the [storage migration instructions](../../docs/start_here/configuration.md#migrating-existing-application-storage)
before deploying this layout. Updating the env file does not migrate files or
stored absolute paths. Log and MongoDB storage settings remain independent.

For Docker MongoDB, use `mongo-app:27017` in the application URI and set
`MONGO_REPLICA_MEMBER_HOST=mongo-app:27017`. For split knowledgebases, use
`mongo-kb:27017` and `KNOWLEDGEBASE_REPLICA_MEMBER_HOST=mongo-kb:27017`.
Each URI must use its own configured credentials and replica-set name.
No host mapping is needed for these container-to-container connections.

For a database or integration running on the host, either use its reachable IP
directly or add the optional host overlay. `127.0.0.1` inside a container is not
the host. The host service must listen on an address reachable from that network.

Prepare all bind source directories and keyfiles before startup. Legacy Compose
cannot enforce `bind.create_host_path: false` and may create missing directories.
Check source existence and permissions yourself, especially for file mounts.
Application data, logs, and reports must be writable by the configured application
UID/GID. Set `MONGO_UID` and `MONGO_GID` in the deployment env file to the
database owner's numeric IDs (obtain them with `id -u` and `id -g`).
Both Mongo services and their replica initializers use these IDs; root IDs are rejected.
Keep the host keyfile owned by the deploying operator with mode `600`. The legacy
Mongo entrypoint reads the file through a read-only bind mount as container root,
then copies it into `/run/coyote3-mongo` (tmpfs), owned by the configured IDs with mode
`400`. Before starting MongoDB, it updates ownership of existing files in
`/data/db` and `/data/configdb`, then drops to the configured UID/GID using
`gosu`. Stop the old Mongo container before recreating it after changing IDs;
never run another Mongo process against that data directory during migration. The host
keyfile is never modified by the container. Root-squashed network filesystems
must still permit container root to read the source; use a local keyfile if needed.
Read-only pipeline inputs do not replace writable ingest staging.

## MongoDB first

Run these full commands from the repository root, in the same Bash session.
Source only a trusted environment file. The examples use independent app and
database project names so application updates do not stop MongoDB.

```bash
docker-compose version
docker run --rm --security-opt seccomp=unconfined mongo:7.0.41 mongod --version
docker run --rm --security-opt seccomp=unconfined mongo:7.0.41 mongosh --version
set -a; source .coyote3_dev_env; set +a
export COYOTE3_VERSION="$(python3 api/version.py)"
docker network inspect "$COYOTE3_APP_NETWORK" >/dev/null 2>&1 || docker network create "$COYOTE3_APP_NETWORK"
bash scripts/validate_env_secrets.sh --env-file .coyote3_dev_env
docker-compose -p coyote3-dev-mongo --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.mongo.yml --profile mongo config --quiet
docker-compose -p coyote3-dev-mongo --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.mongo.yml --profile mongo up -d mongo
docker-compose -p coyote3-dev-mongo --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.mongo.yml --profile mongo run --rm mongo_init
docker-compose -p coyote3-dev-mongo --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.mongo.yml --profile mongo ps
```

Stop if any command fails. `mongo_init` uses bounded retries for authentication
and primary election and exits nonzero on failure. Compose health checks enforce
its MongoDB dependency. Do not use `up --wait`, which Compose 1.29.2 lacks.
The initializer must report `[ok] replica set is writable` before bootstrap.
Use the same pattern with `--profile mongo-kb`, `mongo-kb`, and `mongo_kb_init`
to initialize the independently configured knowledgebase instance.

Use empty data directories only for first installation. Never mount a directory
used by another running mongod. Do not also run a manually created MongoDB
container or a modern Compose project against the same storage. Existing
databases require their original credentials and keyfile; env changes do not
reset database accounts or move data.

Never start MongoDB 7.0 against data files written by MongoDB 8. Use a fresh
directory for a new installation. Existing MongoDB 8 data requires a separately
validated transfer, not an image-tag replacement. Keep the original data intact.
The shared archive scripts still launch MongoDB 8.2 tools containers; they are
not suitable for a host that cannot run that image. Use the center's external
backup process for this deployment until its tooling has been validated.

## Application startup

Legacy API and documentation builds select `python:3.12-slim-bullseye` through
the `PYTHON_BASE_IMAGE` build argument to avoid Bookworm syscall incompatibilities
on Docker 18.09. Workers and beat use the same API image. The modern API build
defaults to Python 3.14.7 on Bookworm. Application dependencies remain pinned in
`requirements.txt`, and the project supports Python 3.12 and newer.
Bullseye LTS ended on August 31, 2026. The API build disables metadata expiry
checking only for its Bullseye security snapshot dated September 1, 2026; APT signature and
package hash verification remain enabled. This base no longer receives Debian
LTS security updates.

The base file serves compiled frontend assets even when `ENV_NAME=development`.
Use `docker-compose.dev.yml` for live development, as shown below.
Build explicitly, then bootstrap and provision indexes before starting writers.
The API, frontend, and documentation builds use `build.network: host` so Dockerfile
`RUN` commands use the host network for dependency downloads on the legacy host.
Application containers still use the configured application network at runtime.

For development, build the documentation site with `python3 -m mkdocs build`
in the project's documentation environment before starting; the dev service mounts
`site/`, matching modern development. Export `COYOTE3_VERSION` from `api/version.py`
as above. Use the same definition and env file for every command:

```bash
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.dev.yml config --quiet
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.dev.yml build api docs
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.dev.yml pull frontend
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.dev.yml up -d
```

Frontend source changes update through Vite; API source changes trigger Uvicorn
reload. Restart worker and beat after changing task code. Rebuild API images after
Python dependency changes, and recreate services after changing environment
settings. Compose v1 has no `--watch`; the source mounts provide live development.
The dev frontend runs the official Node image and installs dependencies into its
project-scoped `frontend_node_modules` volume, so it has no frontend build step.
Its runtime network must reach the npm registry.

Stage and test use the base plus the matching overlay:

```bash
docker-compose -p coyote3-stage --env-file .coyote3_stage_env -f deploy/legacy/docker-compose.yml -f deploy/legacy/docker-compose.stage.yml up -d --build
docker-compose -p coyote3-test --env-file .coyote3_test_env -f deploy/legacy/docker-compose.yml -f deploy/legacy/docker-compose.test.yml --profile tests run --rm test_runner
```

Add `--profile with-ui` for the test frontend, docs, and proxy. The following
compiled-stack bootstrap examples are only for a fresh installation; substitute
the selected environment definition on every command when using dev, stage, or test.

```bash
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml config --quiet
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml build
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml run --rm --no-deps api python scripts/bootstrap_database.py --db "$COYOTE3_DB" --identity-db "$IDENTITY_DB" --username admin.coyote3 --email '<emergency administrator email>' --sys-admin-username coyote3_sysadmin --sys-admin-email '<system administrator email>'
```

Replace the email placeholders. Bootstrap prompts for temporary passwords and
must run only for an empty installation, never against restored application data.
Supply a separately authorized knowledgebase maintenance URI for index creation,
not a permanent elevation of the normal application account:

```bash
read -rsp 'Knowledgebase maintenance URI: ' KB_MAINTENANCE_URI; echo
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml run --rm --no-deps -e KNOWLEDGEBASE_MONGO_URI="$KB_MAINTENANCE_URI" api python scripts/manage_mongo_indexes.py apply
unset KB_MAINTENANCE_URI
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml up -d
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml ps
docker-compose -p coyote3-dev --env-file .coyote3_dev_env -f deploy/legacy/docker-compose.yml logs --tail=100 api worker beat proxy
```

Dependency health checks still apply, but `up -d` is not a complete application
acceptance test. Verify API health, login, and the required workflows before use.
The existing `center_preflight.sh` requires modern Compose; do not use it as a
legacy readiness check. The secret validator and `config --quiet` commands above
do not replace storage, connectivity, or application acceptance checks.

Append selected legacy overlays after the corresponding base file on every
command for that project. For example, add
`-f deploy/legacy/docker-compose.host.yml` for host access, or a private copy of
the legacy storage example for extra inputs. Explicitly create backup/input
directories before adding those overlays. Never run `down -v` against persistent
deployments. Backups remain the center's responsibility.

## Verification

The unit tests compare the application definition with the modern service
contract and render all legacy overlays without connecting to a Docker daemon:

```bash
COYOTE3_LEGACY_COMPOSE_BIN=/path/to/docker-compose-1.29.2 .venv/bin/pytest -q --no-cov tests/unit/test_legacy_compose.py
```

Run this whenever either Compose family changes. The legacy rendering tests skip
when the executable is unavailable. Image execution and full-stack acceptance
must additionally be performed on the actual legacy host; passing YAML validation
does not establish runtime compatibility.
