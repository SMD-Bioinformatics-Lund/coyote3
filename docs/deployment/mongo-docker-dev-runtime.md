# Mongo Docker Runtime for Dev and Portable Environments

## 1. Purpose
This guide defines the expected Mongo runtime pattern for local/dev and portable validation environments.

Primary goals:
- reproducible startup on any platform with Docker
- no host Mongo dependency
- persistent volume-backed data
- controlled restore from curated snapshots
- authenticated database access via dedicated Mongo users

## 2. Compose entry points
- Dev compose: `deploy/compose/docker-compose.dev.yml`
- Stage compose: `deploy/compose/docker-compose.stage.yml`
- Prod compose: `deploy/compose/docker-compose.yml`
- Wrapper script: `scripts/compose-with-version.sh`

## 3. Mongo service model
Mongo runs as a dedicated container (`mongo:7.0`) with a stable named-volume policy.

Why stable named volumes:
- keeps data across container rebuilds and restarts
- avoids accidental drift to Compose-prefixed replacement volume names
- keeps local restore and troubleshooting commands predictable

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
COYOTE3_DB='coyote3_dev'
MONGO_APP_USER='coyote3_app'
MONGO_APP_PASSWORD='CHANGE_ME_DEV_APP_PASSWORD'
MONGO_URI='mongodb://coyote3_app:CHANGE_ME_DEV_APP_PASSWORD@coyote3_dev_mongo:27017/coyote3_dev'
```

`MONGO_URI` is required.

The active container port mapping remains host-facing `37017 -> 27017` for local tooling.
All host ports are environment-driven. Common keys:
- `COYOTE3_WEB_PORT`, `COYOTE3_API_PORT`, `COYOTE3_REDIS_PORT`, `COYOTE3_MONGO_PORT`
- `COYOTE3_DEV_WEB_PORT`, `COYOTE3_DEV_API_PORT`, `COYOTE3_DEV_REDIS_PORT`, `COYOTE3_DEV_MONGO_PORT`

## 5. Fresh startup workflow
1. Ensure network/volume prerequisites.
2. Start compose profile with Mongo.
3. Run required DB identity migration script.
4. Validate counts and login.

Example:

```bash
./scripts/compose-with-version.sh --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml --profile with-mongo up -d --build

/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev
```

Current behavior:
- runs directly against the dev Docker Mongo endpoint at `mongodb://localhost:37017`
- normalizes users/roles/permissions/schemas identities and business keys
- migrates non-ObjectId `_id` documents to ObjectId `_id` with unique business-key indexes
- populates canonical variant identity fields (`simple_id` + `simple_id_hash`)
- keeps variant lookups hash-index friendly without removing readable `simple_id`

## 6. Snapshot scripts
Use the canonical snapshot tooling:

Create a curated mixed-assay snapshot:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-count 60 \
  --output-dir snapshots
```

Create a snapshot from explicit sample selectors:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-list-file /tmp/sample_selectors.txt
```

One-command snapshot+restore into dev:

```bash
scripts/snapshot_restore_dev.sh \
  --source-uri mongodb://localhost:5818 \
  --source-db coyote3 \
  --target-uri mongodb://localhost:37017 \
  --target-db coyote3_dev \
  --fresh-snapshot \
  --sample-count 60
```

One-command snapshot+restore into stage:

```bash
scripts/snapshot_restore_stage.sh \
  --source-uri "mongodb://<prod-app-user>:<prod-app-pass>@<prod-mongo-host>:27017/coyote3" \
  --source-db coyote3 \
  --sample-count 60
```

Create/rotate app users for existing Mongo volumes:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/mongo_bootstrap_users.py \
  --mongo-uri "mongodb://<root-user>:<root-pass>@localhost:37017/admin" \
  --app-db coyote3_dev \
  --app-user coyote3_app \
  --app-password '<new-strong-password>'
```

## 7. Keeping `coyote3` and `coyote3_dev` aligned
When both DB names are used during migration/testing, keep data synchronized.

Recommended operator script pattern:
- source DB: `coyote3`
- target DB: `coyote3_dev`
- restore with `--db-map coyote3=coyote3_dev --drop-db`

Validation query (example):

```python
from pymongo import MongoClient
c = MongoClient("mongodb://localhost:37017")
for dbname in ["coyote3", "coyote3_dev"]:
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
- `docs/deployment/patient-data-backup-and-recovery.md`
- `scripts/mongo_backup_archive.sh`
- `scripts/mongo_restore_archive.sh`

Never run destructive Docker volume commands in environments containing clinical data unless under approved recovery/change procedure.

## 10. Quick health checklist
After startup/restore:
1. `docker ps` shows web/api/mongo/redis/tailwind all `Up`.
2. `GET /api/v1/health` returns `200`.
3. login succeeds for approved local user.
4. `/api/v1/samples` returns expected snapshot data.
5. dashboard/public routes render without repeated 401 loops.
6. restored users have `user_id` populated and variant docs have `simple_id_hash`.
