# Backup And Restore

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

## Identity normalization migration (after restore)

One-off restore migrations are local operational scripts and belong in the
ignored `migration_scripts/` directory. Keep those scripts out of git unless
they become supported maintenance commands with tests.

```bash
python migration_scripts/<restore-migration-script>.py \
  --mongo-uri "${TARGET_MONGO_URI}" \
  --db "${TARGET_DB:-coyote3}"
```
