# Legacy Docker deployment

These definitions target the Compose 1.29.2 configuration format and avoid
Docker Engine 18.09's unsupported `host-gateway` mapping. They are separate from
the modern definitions in `deploy/compose`; do not combine the two families.

Configuration rendering is tested with Compose 1.29.2 and modern Compose.
This is not certification of the application images on Docker 18.09. The host
CPU, kernel, runtime, and seccomp policy must support the current images.
Docker 18.09 and Compose v1 are obsolete; use this deployment only under the
center's explicit legacy-runtime policy. Do not disable authentication, seccomp,
or other isolation controls to make an image start.

## Definitions

| File | Purpose |
| --- | --- |
| `docker-compose.yml` | Compiled application, API, workers, Redis, docs, and proxy; no MongoDB. Use for any environment with its own env file and project name. |
| `docker-compose.mongo.yml` | Optional `mongo` and `mongo-kb` profiles, with authentication and separate replica sets. Can run as an independent project. |
| `docker-compose.mongo-backup.yml` | Optional server `/backup` mount; omit for externally managed backups. |
| `docker-compose.storage.example.yml` | Optional read-only input mounts shared by API, worker, and beat. |
| `docker-compose.host.yml` | Optional `host.docker.internal` mapping to an explicitly configured host IP. |

Initialization scripts, proxy configuration, Dockerfiles, image versions, and
application settings are reused from the current repository. Hot-reload, test
runner, and load-test overlays from `deploy/compose` are not part of this legacy
deployment. There is no implicit project name; always pass `-p` explicitly.

## Configuration

Use `deploy/env/example.env` as the starting point for a private env file.
Complete all secrets, public URL, database names, and storage paths as described
in the [configuration reference](../../docs/start_here/configuration.md).
Never commit a completed environment file.

| Setting | Legacy requirement |
| --- | --- |
| `COYOTE3_MONGO_URI` | Explicit URI; the old `MONGO_URI` alias is not consulted. |
| `COYOTE3_REPORTS_HOST_ROOT` | Required, nonempty host path. Set it to your data root followed by `/coyote3/reports` to preserve existing storage, or choose a separate report directory. Write the full path, not a nested variable expression. |
| `COYOTE3_DOCKER_HOST_IP` | Only required with `docker-compose.host.yml`. Numeric host IP reachable from the application network; no automatic gateway substitution. |
| `COYOTE3_VERSION` | Export from `api/version.py` before application Compose commands. |

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
UID/GID; MongoDB data and keyfile ownership must match the MongoDB image user.
Read-only pipeline inputs do not replace writable ingest staging.

## MongoDB first

Run these full commands from the repository root, in the same Bash session.
Source only a trusted environment file. The examples use independent app and
database project names so application updates do not stop MongoDB.

```bash
docker-compose version
docker run --rm mongo:8.2 mongod --version
docker run --rm mongo:8.2 mongosh --version
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

## Application startup

The base file serves compiled frontend assets even when `ENV_NAME=development`.
It retains development branding and environment configuration without hot reload.
Build explicitly, then bootstrap and provision indexes before starting writers.

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
