# MongoDB deployment and recovery

MongoDB is deployed independently from the Coyote3 API, UI, documentation,
workers, and proxy. The application uses only `MONGO_URI`; stopping,
rebuilding, or updating the application stack does not stop, configure, or
remove the database stack.

The URI may target a host-installed MongoDB, a managed database platform, or
the optional MongoDB Compose definition in this repository. The database
administrator owns availability, backups, upgrades, replica-set membership,
networking, and application-user provisioning. In Docker-based local
development, use `host.docker.internal` in `MONGO_URI` to reach a MongoDB
server installed on the host.

## Docker deployment model

The repository provides `deploy/compose/docker-compose.mongo.yml` for a self-hosted MongoDB 8.2 instance. It creates a dedicated Docker network and starts a single-member replica set.

The first member is a normal MongoDB primary, not a high-availability cluster. It provides replica-set semantics needed for consistent oplog backups and gives a controlled path to add secondaries later.

!!! warning
    A one-member replica set has no failover protection. If its server is unavailable, Coyote3 cannot read or write clinical data. Use tested backups and add two separate-host secondary members when availability requirements justify the operational cost.

## First-time setup

1. Copy `deploy/env/example.env` to the environment file for the target deployment.
2. Set all `CHANGE_ME` values and choose persistent host directories for MongoDB data and backups.
3. Create the replica-set keyfile once. It is a secret used only by MongoDB members, not an application setting.

```bash
sudo install -d -m 0700 /srv/coyote3/mongo/data /srv/coyote3/mongo/backups
sudo sh -c 'openssl rand -base64 756 > /srv/coyote3/mongo/keyfile'
sudo chmod 0400 /srv/coyote3/mongo/keyfile
sudo chown 999:999 /srv/coyote3/mongo/keyfile
```

The official MongoDB image runs its database process as UID `999`. Confirm the runtime UID if a custom image is used.

4. Keep these values aligned in the environment file:

| Key | Meaning | Self-hosted value |
| --- | --- | --- |
| `COYOTE3_MONGO_NETWORK` | Dedicated Docker network for the independent MongoDB stack only. | `coyote3-mongo-net` |
| `MONGO_REPLICA_SET_NAME` | Immutable name of the replica set. | `coyote3-rs` |
| `MONGO_REPLICA_MEMBER_HOST` | Member address published in replica-set metadata. | A stable hostname and port reachable from both MongoDB and application containers, such as `mongo.example.internal:27017`. |
| `MONGO_URI` | Application connection string. | Uses the same reachable host, database name, `authSource`, and `replicaSet`. |
| `COYOTE3_MONGO_BIND_ADDRESS` | Host interface used for the optional Docker MongoDB port. | `127.0.0.1` when only the host needs access; an operator-approved host interface when application containers connect through the host. |
| `COYOTE3_MONGO_DATA_HOST_ROOT` | Persistent host directory for `/data/db`. | Center-controlled absolute path. |
| `COYOTE3_MONGO_BACKUP_HOST_ROOT` | Persistent host directory for archive output. | Center-controlled absolute path. |
| `COYOTE3_MONGO_KEYFILE_HOST_PATH` | Persistent replica-set secret file. | Center-controlled absolute path. |

5. Start the MongoDB stack as an independent infrastructure deployment. Create
the network named by `COYOTE3_MONGO_NETWORK` beforehand if it does not already
exist; this Compose file deliberately uses an externally supplied network and
does not create one. The application stack does not join that network.

```bash
set -a
. ./.coyote3_env
set +a
docker network create "$COYOTE3_MONGO_NETWORK"
docker compose --env-file .coyote3_env \
  -f deploy/compose/docker-compose.mongo.yml \
  up -d
```

6. Set `MONGO_URI` to a URI reachable from the application containers, then
start the application stack. For a database on the same Docker host, use an
operator-approved published MongoDB port and `host.docker.internal`; for a
production deployment, prefer a stable center DNS name. Do not use the
internal `coyote3_mongo` service alias in `MONGO_URI`, because application
services do not join the MongoDB network.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

7. Confirm that initialization completed and the member is primary.

```bash
set -a
. ./.coyote3_env
set +a
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.mongo.yml logs mongo_init
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.mongo.yml exec mongo \
  mongosh --username "$MONGO_ROOT_USERNAME" --password "$MONGO_ROOT_PASSWORD" \
  --authenticationDatabase admin --quiet --eval 'rs.status().members.map(m => ({host: m.name, state: m.stateStr}))'
```

## Data durability

MongoDB data and archives are host bind mounts. `docker compose down` stops and removes containers but does not remove either host directory. The project wrapper also rejects `down -v` and `down --volumes`.

Do not manually delete, recreate, or move `COYOTE3_MONGO_DATA_HOST_ROOT` while MongoDB is running. A database volume can later be used by a non-Docker MongoDB installation only when the MongoDB version, storage engine, filesystem permissions, and startup procedure are compatible. This is a recovery operation, not a routine migration method. Use a logical archive to move data between hosts or deployments.

## Adding replica members later

Yes. A one-member replica set can be expanded later without recreating the original member or changing the application's data model. Each new member must:

1. Run the same supported MongoDB version and replica-set name.
2. Use a securely copied instance of the existing keyfile.
3. Have its own persistent data path and a DNS hostname reachable by every MongoDB member and application client.
4. Be added from the current primary using `rs.add({ host: "mongo-secondary-1.example.internal:27017" })`.

Add two voting secondaries on separate servers for a standard three-member production replica set. Each data-bearing secondary performs an initial sync and keeps a full copy of the database, so data storage is intentionally replicated on disk.

Use stable DNS names or Docker service aliases, not generated container names,
IP addresses, or localhost addresses, in replica-set member configuration. The
chosen address becomes persisted MongoDB metadata and must remain resolvable
after restarts and upgrades.

## Logical backups

Use the archive script with a MongoDB user permitted to run backup operations.
For the optional Docker MongoDB deployment, pass the dedicated network. For a
host-installed or externally managed MongoDB, omit `--docker-network`; the
tools container must be able to resolve and reach the host in `MONGO_BACKUP_URI`.

```bash
bash scripts/mongo_backup_archive.sh \
  --mongo-uri "$MONGO_BACKUP_URI" \
  --out-dir "$COYOTE3_MONGO_BACKUP_HOST_ROOT" \
  --label nightly \
  --docker-network "$COYOTE3_MONGO_NETWORK"
```

Schedule `mongo_backup_archive.sh` through the centre's approved backup platform. This may be an enterprise scheduler, infrastructure automation, or an existing operations service; scheduling configuration is intentionally not part of the application repository.

Use a dedicated backup URI and persistent backup storage. The backup URI should
authenticate with a backup user or the restricted administrative account
approved by the centre; it is not the routine application URI. Retention and
off-host copy are explicit centre operations.

## Backup failure and recovery testing

If MongoDB goes offline during a dump, the command fails and the script removes its partial archive. The previous successful backup remains available. Monitor the scheduled job through the centre's normal operations tooling.

At least quarterly, restore one archive to an isolated recovery MongoDB instance and verify application login, sample retrieval, and report preview. Record the elapsed backup and restore times to confirm that the deployment meets the center's recovery objectives.
