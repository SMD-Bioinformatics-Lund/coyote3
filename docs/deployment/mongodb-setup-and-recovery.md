# MongoDB deployment and recovery

Coyote3 selects app, identity, knowledgebase, and BAM databases through separate
URI/name pairs. MongoDB can be host-installed, managed externally, or enabled
through the optional Docker profiles. See [MongoDB service topology](../architecture/mongodb-topology.md)
for the connection contract, local/split examples, environment isolation, and
profile commands.

## Replica-set requirement

Related-document writes require a MongoDB replica set or sharded cluster.
A single-member replica set is supported for local development, but has no
failover protection. Every endpoint can use its own replica-set name. Connection
strings and advertised member addresses must be reachable from API and workers.
See [transaction boundaries](../architecture/transactions-and-ingest-recovery.md).

Each mongod uses one dbPath for all its logical databases. Never mount the same
data directory into two running mongod processes.

## Docker deployment model

For Compose 1.29.2 deployments, use the separate
[legacy deployment definitions and commands](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/api/deploy/legacy/README.md).
They do not change the modern Compose files or certify current images on an old runtime.

The base Compose stack starts no MongoDB. The optional
`deploy/compose/docker-compose.mongo.yml` overlay selects app MongoDB with
`--profile mongo` and knowledgebase MongoDB with `--profile mongo-kb`.
Both use the operator-created `COYOTE3_APP_NETWORK`.
For independently operated infrastructure, use an explicit Compose project name
and keep its lifecycle separate from application updates.

## First-time setup

Follow [first installation, step 6](first-installation.md#choose-and-prepare-mongodb)
before application bootstrap. It includes software installation links, the private
Docker server environment, network/storage/keyfile preparation, initialization,
and host-installed MongoDB replica-set conversion. It also separates runtime
knowledgebase readers from the maintenance credentials required to install reference data.

For an existing healthy replica set, retain its data directory, keyfile, member
addresses and account configuration. Do not repeat fresh initialization during
an application upgrade. Each physical server needs its own persistent dbPath;
keyfiles and database storage are not created by application directory preparation.

The optional Docker server entrypoint copies its read-only host keyfile into tmpfs,
sets permissions and drops to the configured `MONGO_UID`/`MONGO_GID`. Health checks
and initializers use the same IDs. Root-squashed storage must permit the required
startup ownership operations. Change owner IDs only during a planned database
stop/recreate operation, never while another process uses the same storage.

## Connectivity checks

Check each configured endpoint without assuming a common replica-set name:

```bash
mongosh "$COYOTE3_MONGO_URI" --eval 'db.hello().isWritablePrimary'
mongosh "$IDENTITY_MONGO_URI" --eval 'db.hello().isWritablePrimary'
mongosh "$KNOWLEDGEBASE_MONGO_URI" --eval 'db.hello().isWritablePrimary'
```

These shell variables must be loaded from the completed environment file.
Configure authentication and TLS according to center policy; do not expose
unauthenticated MongoDB to an external network.

## Knowledgebase database migration

Coyote3 stores external knowledgebase datasets in the database selected by
`KNOWLEDGEBASE_DB` on `KNOWLEDGEBASE_MONGO_URI`. Its namespace must not overlap an
app/identity/BAM namespace on the same deployment. HGNC and VEP reference data
also belong in the knowledgebase database. Clinical annotations, samples, findings,
comments and reports remain in the primary application database.

Upgrade an installation that still has knowledgebase collections in
`COYOTE3_DB` before starting the new API or workers. Starting first can create
empty destination collections and correctly block migration into them.

1. Stop application writers and take a logical backup.
2. Give the application read access and the migration operator the source-read,
   destination-write/index/rename privileges needed for the copy. The URI variables
   below must contain maintenance credentials, not the runtime reader account.
3. Run the read-only inspection:

```bash
PYTHONPATH=. .venv/bin/python scripts/knowledgebase/migrate_knowledgebase_database.py \
  --source-mongo-uri "$COYOTE3_MONGO_URI" \
  --target-mongo-uri "$KNOWLEDGEBASE_MONGO_URI" \
  --source-db "$COYOTE3_DB" \
  --target-db "$KNOWLEDGEBASE_DB" \
  --report knowledgebase-migration-dry-run.json
```

4. Copy into staging collections, preserve indexes, verify complete collection
   digests, and atomically publish each verified destination:

```bash
PYTHONPATH=. .venv/bin/python scripts/knowledgebase/migrate_knowledgebase_database.py \
  --source-mongo-uri "$COYOTE3_MONGO_URI" \
  --target-mongo-uri "$KNOWLEDGEBASE_MONGO_URI" \
  --source-db "$COYOTE3_DB" \
  --target-db "$KNOWLEDGEBASE_DB" \
  --apply \
  --report knowledgebase-migration-applied.json
```

The command removes `sample_ids` and `sample_names` from migrated
`oncokb_public` documents. Those fields are forbidden in the destination. It
does not modify any source collection during the normal apply operation.

5. Start Coyote3 with `KNOWLEDGEBASE_DB` configured, verify knowledgebase
   markers and finding-detail evidence, and retain the source collections for
   the center's rollback interval.
6. After the migration has been accepted, remove only the verified source
   knowledgebase collections with the explicit destructive confirmation:

```bash
PYTHONPATH=. .venv/bin/python scripts/knowledgebase/migrate_knowledgebase_database.py \
  --source-mongo-uri "$COYOTE3_MONGO_URI" \
  --target-mongo-uri "$KNOWLEDGEBASE_MONGO_URI" \
  --source-db "$COYOTE3_DB" \
  --target-db "$KNOWLEDGEBASE_DB" \
  --apply \
  --drop-source \
  --confirm-drop-source "$COYOTE3_DB" \
  --report knowledgebase-migration-cleanup.json
```

The migration is restartable. An existing destination is accepted only when
its transformed document count and complete SHA-256 digest match the source.
A differing destination or an existing staging collection stops the command
for operator review; neither is overwritten automatically.

## Identity database migration

Coyote3 stores `users`, `roles`, `permissions`, `api_sessions`, and
`audit_events` in the database selected by `IDENTITY_DB`. Audit events remain
with identity data because both require restricted access, durable backups,
and security-controlled administration. Application controls and clinical data
remain in `COYOTE3_DB`.

For an existing installation, stop API and worker processes and back up MongoDB
before migration. Grant the application and migration account read/write access
to `IDENTITY_DB`, then inspect the source without writing:

```bash
PYTHONPATH=. .venv/bin/python scripts/identity/migrate_identity_database.py \
  --source-mongo-uri "$COYOTE3_MONGO_URI" \
  --target-mongo-uri "$IDENTITY_MONGO_URI" \
  --source-db "$COYOTE3_DB" \
  --target-db "$IDENTITY_DB" \
  --report identity-migration-dry-run.json
```

Copy documents and indexes through verified staging collections:

```bash
PYTHONPATH=. .venv/bin/python scripts/identity/migrate_identity_database.py \
  --source-mongo-uri "$COYOTE3_MONGO_URI" \
  --target-mongo-uri "$IDENTITY_MONGO_URI" \
  --source-db "$COYOTE3_DB" \
  --target-db "$IDENTITY_DB" \
  --apply \
  --report identity-migration-applied.json
```

Start Coyote3 with `IDENTITY_DB` configured and verify local login, role and
permission administration, session persistence, audit export, and index status.
Keep the source collections for the approved rollback period. After acceptance,
remove only the verified source copies:

```bash
PYTHONPATH=. .venv/bin/python scripts/identity/migrate_identity_database.py \
  --source-mongo-uri "$COYOTE3_MONGO_URI" \
  --target-mongo-uri "$IDENTITY_MONGO_URI" \
  --source-db "$COYOTE3_DB" \
  --target-db "$IDENTITY_DB" \
  --apply \
  --drop-source \
  --confirm-drop-source "$COYOTE3_DB" \
  --report identity-migration-cleanup.json
```

The report contains collection counts and content digests, not identity
documents. A populated destination with different content blocks migration and
is never overwritten.

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

The MongoDB server has no `/backup` mount by default. If an internal process
handles backups, omit `COYOTE3_MONGO_BACKUP_HOST_ROOT` and the backup overlay.
The archive tool below mounts its own output directory and does not require a
backup mount on the server. Set `COYOTE3_MONGO_BACKUP_HOST_ROOT` to the desired
output directory before running this example, or pass a directory directly to
`--out-dir`.

For commands that need `/backup` inside the MongoDB server container, create the
host directory, grant the container user appropriate access, and set
`COYOTE3_MONGO_BACKUP_HOST_ROOT`. Include the optional overlay after the MongoDB
definition:

```bash
docker compose -p coyote3-dev-mongo --env-file .coyote3_dev_mongo_env \
  -f deploy/compose/docker-compose.mongo.yml \
  -f deploy/compose/docker-compose.mongo-backup.yml \
  --profile mongo up -d mongo
```

Use the same Compose project and environment file as the existing deployment.
The overlay requires an explicitly configured, existing directory; it does not
create the directory or schedule backups. Setting the variable alone does not
mount anything. Removing the overlay and reapplying Compose recreates the
container without `/backup`; it does not delete files in the host directory.
Plan for a brief interruption when changing mounts on a single-member replica set.

Use the archive script with a MongoDB user permitted to run backup operations.
For the optional Docker MongoDB deployment, pass the dedicated network. For a
host-installed or externally managed MongoDB, omit `--docker-network`; the
tools container must be able to resolve and reach the host in `MONGO_BACKUP_URI`.

```bash
bash scripts/database/mongo_backup_archive.sh \
  --mongo-uri "$MONGO_BACKUP_URI" \
  --out-dir "$COYOTE3_MONGO_BACKUP_HOST_ROOT" \
  --label nightly \
  --docker-network "$COYOTE3_APP_NETWORK"
```

Schedule `database/mongo_backup_archive.sh` through the centre's approved backup platform. This may be an enterprise scheduler, infrastructure automation, or an existing operations service; scheduling configuration is intentionally not part of the application repository.

Use a dedicated backup URI and persistent backup storage. The backup URI should
authenticate with a backup user or the restricted administrative account
approved by the centre; it is not the routine application URI. Retention and
off-host copy are explicit centre operations.

## Backup failure and recovery testing

If MongoDB goes offline during a dump, the command fails and the script removes its partial archive. The previous successful backup remains available. Monitor the scheduled job through the centre's normal operations tooling.

At least quarterly, restore one archive to an isolated recovery MongoDB instance and verify application login, sample retrieval, and report preview. Record the elapsed backup and restore times to confirm that the deployment meets the center's recovery objectives.
