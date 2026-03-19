# Backup Restore And Snapshots

## Create Mongo archive backup

```bash
bash scripts/mongo_backup_archive.sh \
  --mongo-uri "${MONGO_URI}" \
  --db "${COYOTE3_DB}" \
  --out "/data/coyote3/backups/mongo"
```

## Restore Mongo archive

```bash
bash scripts/mongo_restore_archive.sh \
  --mongo-uri "${MONGO_URI}" \
  --db "${COYOTE3_DB}" \
  --archive "/data/coyote3/backups/mongo/backup.archive.gz"
```

## Build compact dev snapshot from source DB

```bash
python scripts/create_mongo_snapshot.py \
  --mongo-uri "${SNAPSHOT_SOURCE_MONGO_URI}" \
  --db "${SNAPSHOT_SOURCE_DB}" \
  --sample-count 60
```

## Restore snapshot into dev or stage

```bash
bash scripts/snapshot_restore_dev.sh \
  --source-uri "${SNAPSHOT_SOURCE_MONGO_URI}" \
  --source-db "${SNAPSHOT_SOURCE_DB}" \
  --target-uri "${SNAPSHOT_DEV_TARGET_MONGO_URI}" \
  --target-db "${SNAPSHOT_DEV_TARGET_DB:-coyote3}"

bash scripts/snapshot_restore_stage.sh \
  --source-uri "${SNAPSHOT_SOURCE_MONGO_URI}" \
  --source-db "${SNAPSHOT_SOURCE_DB}" \
  --target-uri "${SNAPSHOT_STAGE_TARGET_MONGO_URI}" \
  --target-db "${SNAPSHOT_STAGE_TARGET_DB:-coyote3}"
```

## Identity normalization migration (after restore)

```bash
python scripts/migrate_db_identity.py \
  --mongo-uri "${TARGET_MONGO_URI}" \
  --db "${TARGET_DB:-coyote3}"
```
