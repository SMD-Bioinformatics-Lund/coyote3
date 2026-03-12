# Patient Data Backup and Recovery Runbook

## 1. Scope and Criticality
This runbook defines required controls for MongoDB backup, restore, and storage protection in environments handling patient data. It applies to production and development environments where clinical or clinically-derived data can exist.

This runbook is mandatory operational guidance, not optional best effort.

## 2. Data Durability Objectives
- `RPO` target (maximum acceptable data loss): organization-defined, typically <= 24h for scheduled full backups.
- `RTO` target (maximum acceptable recovery time): organization-defined, typically <= 4h for primary service restore.
- Backups are considered valid only after periodic restore validation.

## 3. Storage Protection Model
### 3.1 External Docker volume policy
Mongo runtime data must use external Docker volumes in compose-backed deployments:
- production volume: `coyote3-prod-mongo-data`
- dev volume: `coyote3-dev-mongo-data`
- portable/local test volume: `coyote3-portable-mongo-data`

External volumes are not deleted by `docker compose down -v`.

### 3.2 Volume bootstrap
Create required external volumes:

```bash
./scripts/create_external_mongo_volumes.sh all
```

### 3.3 Non-destructive operations policy
Forbidden without explicit change approval:
- `docker compose down -v` on patient-data environments
- `docker volume rm <mongo-volume>`
- `docker system prune --volumes` on hosts running patient-data stacks

### 3.4 Least-privilege operations
- Restrict shell/SSH access to container hosts.
- Restrict Docker group membership.
- Restrict backup artifact directories with filesystem ACLs.

## 4. Backup Procedure (Archive + Checksum)
Use:
- [scripts/mongo_backup_archive.sh](/home/ram/dev/projects/coyote3/scripts/mongo_backup_archive.sh)

Example production-style backup:

```bash
./scripts/mongo_backup_archive.sh \
  --mongo-uri "mongodb://localhost:27017" \
  --db "coyote3" \
  --out-dir "/data/coyote3/backups/mongo" \
  --label "nightly"
```

If Mongo is reachable only inside a Docker network (common in WSL/compose):

```bash
./scripts/mongo_backup_archive.sh \
  --mongo-uri "mongodb://coyote3_dev_mongo:27017" \
  --db "coyote_dev_3" \
  --out-dir "/data/coyote3/restore-drills/mongo_backups" \
  --label "restore-drill" \
  --docker-network "coyote3-dev-net"
```

Output:
- `*.archive.gz` backup archive
- `*.archive.gz.meta` metadata containing UTC timestamp and SHA256

### 4.1 Backup retention baseline
Recommended minimum:
- Daily backups retained 35 days
- Weekly backups retained 12 weeks
- Monthly backups retained 12 months

Retention must align with clinical governance and legal retention rules.

## 5. Restore Procedure (Guarded)
Use:
- [scripts/mongo_restore_archive.sh](/home/ram/dev/projects/coyote3/scripts/mongo_restore_archive.sh)

Example restore:

```bash
./scripts/mongo_restore_archive.sh \
  --mongo-uri "mongodb://localhost:27017" \
  --db "coyote3" \
  --archive "/data/coyote3/backups/mongo/coyote3_20260311T000000Z.archive.gz" \
  --drop \
  --confirm RESTORE_PATIENT_DATA
```

For isolated drill restore into a temporary Mongo container on custom network:

```bash
./scripts/mongo_restore_archive.sh \
  --mongo-uri "mongodb://coyote3_restore_drill_mongo:27017" \
  --db "coyote_dev_3" \
  --archive "/data/coyote3/restore-drills/mongo_backups/coyote_dev_3_20260311T140633Z_restore-drill.archive.gz" \
  --drop \
  --confirm RESTORE_PATIENT_DATA \
  --docker-network "coyote3-restore-net"
```

The script blocks execution unless `--confirm RESTORE_PATIENT_DATA` is explicitly provided.

## 6. Restore Validation Checklist
After restore, verify:
1. Mongo service healthy and reachable.
2. Expected collection counts present.
3. API health endpoint returns success.
4. Authentication path works.
5. Sample/report read paths work for representative records.
6. Critical indexes present for high-risk collections (`users`, `samples`, `variants`, `reported_variants`).

Example validation query:

```bash
/home/ram/.virtualenvs/coyote3/bin/python - <<'PY'
from pymongo import MongoClient
c = MongoClient("mongodb://localhost:27017")
db = c["coyote3"]
for name in ("users", "samples", "variants", "reported_variants"):
    print(name, db[name].count_documents({}))
PY
```

## 7. Recovery Drill Policy
At least quarterly:
1. Restore latest backup to isolated environment.
2. Run validation checklist.
3. Measure and record achieved RTO/RPO.
4. Document failures and corrective actions.

Store drill evidence:
- backup identifier
- restore command and operator
- timings
- validation outputs
- incident/corrective ticket references

## 8. Optional Self-Hosted Mongo in Compose
Prod/dev compose files support optional Mongo services via profile `with-mongo`.

Examples:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml --profile with-mongo up -d
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml --profile with-mongo up -d
```

When using these profiles, ensure env files set:
- `FLASK_MONGO_HOST` to the matching service name (`coyote3_mongo` / `coyote3_dev_mongo`)

## 9. Platform Failure Scenarios and Expected Outcome
### 9.1 Container restart
Expected: no data loss; volume persists.

### 9.2 Host reboot
Expected: no data loss; volume persists.

### 9.3 Compose teardown without `-v`
Expected: no data loss; volume persists.

### 9.4 Compose teardown with `-v`
Expected: external Mongo volume preserved; non-external volumes may be removed.

### 9.5 Explicit volume deletion
Expected: permanent data loss unless backup restore executed.

## 10. Governance Requirements
- Every backup/restore action must be logged as an auditable operations event.
- Restore in production requires approved change ticket and dual-operator confirmation.
- Backup encryption-at-rest and encrypted transfer are required when leaving host boundary.
