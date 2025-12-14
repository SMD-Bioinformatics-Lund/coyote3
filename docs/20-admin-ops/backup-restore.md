# Backup & Restore

Data layer is MongoDB. Suggested operations:

## Backup
- `mongodump --db <COYOTE3_DB_NAME> --out /backups/$(date +%F)`
- Include `BAM_Service` if used.

## Restore
- `mongorestore --db <COYOTE3_DB_NAME> /backups/DATE/COYOTE3_DB_NAME`

## Versioned configs
- ASP/ASPC/ISGL documents include **version** and **version_history** fields (see Admin UI). Keep dumps for rollback.
