# Backup And Restore

**Procedure verified:** 6 August 2026.

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

## Clinical identity and filter-profile migration

The current contract migration normalizes ASP, ASPC, ISGL, sample, and user
scope documents to `asp_id`, `subpanel_id`, `environment`, `asp_ids`, and
`asp_groups`. It also converts flat sample/ASPC filters into intent profiles.
The script validates every replacement document before it writes anything.

!!! caution
    Take and verify an archive backup first. Run the migration with `--dry-run`
    against the exact target database, inspect its output, then run it without
    that flag during a maintenance window. The script removes retired persisted
    keys; restore the backup to roll back.

One-off migrations are local operational scripts in ignored
`migration_scripts/`. They are not shipped as supported runtime commands.

```bash
PYTHONPATH=. python migration_scripts/20260729_normalize_clinical_configuration.py \
  --uri "${MONGO_URI}" \
  --database "${COYOTE3_DB}" \
  --dry-run
```

The physical collection names are resolved from
`api/config/center/collections.toml` for the selected database.
