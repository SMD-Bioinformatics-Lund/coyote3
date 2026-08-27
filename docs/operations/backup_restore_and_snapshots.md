# Backup and recovery

Coyote3 uses two complementary protection mechanisms for MongoDB data:

1. A complete logical archive is the routine, portable recovery mechanism.
2. Infrastructure snapshots are an optional additional disaster-recovery mechanism for large deployments.

The supported logical archive process is documented together with database setup in the [MongoDB deployment guide](mongodb_deployment_and_recovery.md). This page focuses on how the recovery mechanisms differ and how to operate them safely.

## Logical archives

`scripts/mongo_backup_archive.sh` runs `mongodump` in a short-lived `mongo:8.2` tools container. The container has no MongoDB data volume and does not run a database server. It mounts only the backup destination, creates one compressed archive, verifies it, writes metadata with a SHA-256 checksum, and exits. Docker removes the tools container after the command finishes. For Docker-managed MongoDB, pass `--docker-network`; omit it for an externally reachable MongoDB host.

For the supported one-member replica set, the script uses `--oplog`. This records writes that occur during the dump so that `mongorestore --oplogReplay` can restore a consistent point-in-time state. A backup command that uses `--oplog` must archive the complete MongoDB deployment; it must not select an individual database or collection.

The archive file is written as a hidden `.partial` file first. It is renamed to its final timestamped name only after `gzip -t` and checksum generation succeed. A failed task therefore leaves no apparently complete archive. Earlier archives are never overwritten or removed by the script.

The backup script runs the MongoDB tools in a temporary container. This is a
short-lived process container created only to run `mongodump`; it has no
database data directory and cannot become a database server. Docker removes it
when the command exits. The actual MongoDB primary remains in the independent
database stack throughout the backup.

!!! important
    Copy completed archives and their `.meta` files to storage independent of the MongoDB host. Local archives alone do not protect against host or storage loss.

## Restore

Restore only into a dedicated recovery target unless an incident procedure explicitly authorizes replacing the production server. The restore script requires `--confirm RESTORE_PATIENT_DATA`, validates gzip integrity, verifies the metadata checksum when available, and restores the complete archive with oplog replay.

```bash
bash scripts/mongo_restore_archive.sh \
  --mongo-uri "$MONGO_RECOVERY_URI" \
  --archive /srv/coyote3/mongo/backups/coyote3_mongodb_20260813T023000Z_nightly.archive.gz \
  --drop \
  --confirm RESTORE_PATIENT_DATA \
  --docker-network coyote3-mongo-net
```

Run application-level checks against the recovery target before declaring recovery complete.

## Storage snapshots

A storage snapshot is an image of a block device, volume, virtual machine disk, or managed database storage system. It is not the same as a `mongodump` archive and is not portable across storage platforms.

Snapshots are useful for multi-terabyte databases because they can finish quickly and avoid reading every document through `mongodump`. They must be coordinated with the storage platform and MongoDB state:

- With a future replica set containing secondaries, take snapshots from a secondary so normal application writes continue on the primary.
- With only one member, a crash-consistent snapshot may need recovery work. A fully consistent snapshot requires a controlled maintenance procedure such as `fsyncLock`, a snapshot, and `fsyncUnlock`; writes are paused for that interval.
- Snapshot retention, encryption, off-host replication, and restore testing are infrastructure responsibilities. They cannot be made portable or safe by a generic repository script.

For the initial one-member deployment, nightly logical archives plus off-host retention are the clean default. Add storage snapshots when archive duration or restore-time objectives require them.
