# Mongo Docker Runtime for Dev and Portable Environments

## 1. Purpose
This guide defines the expected Mongo runtime pattern for local/dev and portable validation environments.

Primary goals:
- reproducible startup on any platform with Docker
- no host Mongo dependency
- persistent volume-backed data
- controlled restore from curated snapshots

## 2. Compose entry points
- Dev compose: `deploy/compose/docker-compose.dev.yml`
- Portable compose: `deploy/compose/docker-compose.dev.portable.yml`
- Prod-style compose: `deploy/compose/docker-compose.yml`
- Wrapper script: `scripts/compose-with-version.sh`

## 3. Mongo service model
Mongo runs as a dedicated container (`mongo:7.0`) with external volume policy.

Why external volume:
- protects data from accidental `docker compose down -v`
- keeps data across container rebuilds/restarts

Expected volume names:
- `coyote3-dev-mongo-data`
- `coyote3-portable-mongo-data`
- `coyote3-prod-mongo-data`

Bootstrap command:

```bash
./scripts/create_external_mongo_volumes.sh all
```

## 4. Dev database selection policy
For dev work, configure `.coyote3_dev_env`:

```env
COYOTE3_DB_NAME='coyote_dev_3'
FLASK_MONGO_HOST='coyote3_dev_mongo'
FLASK_MONGO_PORT='27017'
```

The active container port mapping remains host-facing `37017 -> 27017` for local tooling.

## 5. Fresh startup workflow
1. Ensure network/volume prerequisites.
2. Start compose profile with Mongo.
3. Restore approved snapshot.
4. Run business-key migration script.
5. Validate counts and login.

Example:

```bash
./scripts/compose-with-version.sh --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml --profile with-mongo up -d --build

/home/ram/.virtualenvs/coyote3/bin/python scripts/restore_mongo_micro_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --snapshot-dir .internal/mongo_sample_linked_snapshot \
  --drop

/home/ram/.virtualenvs/coyote3/bin/python scripts/backfill_business_keys.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote_dev_3 \
  --db coyote3
```

Why this extra step is mandatory:
- restored snapshots may contain older document shapes (`*_beta2`, alternate collection aliases, missing business key fields)
- strict backend mode now expects canonical key fields for identity reads/writes in migrated bounded contexts
- running backfill keeps dev/prod-like environments behaviorally identical

## 6. Snapshot sources
Current restore tooling supports curated snapshot directories under `.internal/`.

Common examples:
- `.internal/mongo_micro_snapshot`
- `.internal/mongo_sample_linked_snapshot`

Use linked snapshot for realistic cross-collection test data (users, samples, variants, metadata).

## 7. Keeping `coyote3` and `coyote_dev_3` aligned
When both DB names are used during migration/testing, keep data synchronized.

Recommended operator script pattern:
- source DB: `coyote3`
- target DB: `coyote_dev_3`
- copy all collections after dropping target collections

Validation query (example):

```python
from pymongo import MongoClient
c = MongoClient("mongodb://localhost:37017")
for dbname in ["coyote3", "coyote_dev_3"]:
    db = c[dbname]
    print(dbname, {
        "samples": db["samples"].count_documents({}),
        "users": db["users"].count_documents({}),
        "variants": db["variants"].count_documents({}),
    })
```

## 8. Pymongo 4.x index compatibility note
With `pymongo>=4`, Mongo startup is stricter about index-name conflicts (`code=85`) where equivalent index keys already exist under a different name.

Coyote3 runtime now tolerates these legacy-name conflicts during handler index setup while logging a warning. This prevents startup failure on restored legacy snapshots.

Operator expectation:
- service boots successfully
- warnings are visible
- data path remains intact

## 9. Backup and recovery controls
For patient-data safety controls, use:
- `docs/PATIENT_DATA_BACKUP_AND_RECOVERY.md`
- `scripts/mongo_backup_archive.sh`
- `scripts/mongo_restore_archive.sh`

Never run destructive Docker volume commands in environments containing clinical data unless under approved recovery/change procedure.

## 10. Quick health checklist
After startup/restore:
1. `docker ps` shows web/api/mongo/redis/tailwind all `Up`.
2. `GET /api/v1/health` returns `200`.
3. login succeeds for approved local user.
4. `/api/v1/home/samples` returns expected snapshot data.
5. dashboard/public routes render without repeated 401 loops.
