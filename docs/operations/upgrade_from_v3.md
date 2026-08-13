# Upgrading from v3.x to v4.0.0

**Prepared:** 2026-08-10

!!! caution "This is a full-stack replacement"
    v4.0.0 replaces the entire Flask/Jinja/Tailwind application with a FastAPI
    backend and a React/Vite frontend. This is **not** a routine patch upgrade.
    Follow this guide in full before going live. Do not attempt an in-place
    container swap without completing the pre-upgrade checklist.

## What changed

| Area | v3.x (Flask) | v4.0.0 (FastAPI/React) |
|------|-------------|----------------------|
| Backend | Flask + Jinja2 blueprints | FastAPI + Pydantic v2 routers |
| Frontend | Server-rendered Jinja templates + Tailwind | React 19 + TypeScript + Vite |
| Auth | Flask session | Session-cookie + Bearer-token; Casbin RBAC |
| Workers | Celery (same) | Celery (same, new task contracts) |
| Database | MongoDB (same collections, evolved schema) | MongoDB (same collections, evolved schema) |
| Config | Flask env + JSON schema files | FastAPI env + TOML/YAML center config |
| Entrypoint | `wsgi.py` (Gunicorn/WSGI) | `asgi.py` (Uvicorn/ASGI) |
| Compose | Root-level Dockerfiles | `docker/` Dockerfiles; `deploy/compose/` files |

### Collections: same names, evolved documents

All MongoDB collection names are unchanged from v3.x (controlled by
`api/config/center/collections.toml`). Documents in core clinical collections
(`samples`, `variants`, `cnvs`, `fusions`, `translocations`, `annotation`,
`reports`, `reported_variants`) remain readable by the v4.0.0 application
without a bulk rewrite.

The following structural changes **do** require a migration run before the
application will operate correctly:

| Document type | Change | Migration required |
|--------------|--------|--------------------|
| ASP / ASPC / ISGL | Keys renamed to `asp_id`, `subpanel_id`, `environment`, `asp_ids`, `asp_groups` | Yes — see Step 4 |
| Sample filter profiles | Flat filter dict promoted to intent profiles (`somatic` / `germline`) | Yes — see Step 4 |
| Users and roles | RBAC catalog replaced; existing users kept but roles must be re-synced | Yes — see Step 5 |
| Permissions | Application-owned catalog replaces ad-hoc records | Yes — see Step 5 |

---

## Pre-upgrade checklist

Work through this list before starting. Do not proceed if any item cannot be satisfied.

- [ ] Archive backup of the full database taken and verified
      (`scripts/mongo_backup_archive.sh`)
- [ ] Current v3.x stack confirmed healthy (all samples accessible, reports rendering)
- [ ] New v4.0.0 image builds succeed on a staging host
- [ ] Center configuration files reviewed against the v4.0.0 contract
      (`api/config/center/` — see [Center Configuration Files](center_configuration_files.md))
- [ ] `deploy/env/example.env` reviewed; every `CHANGE_ME` value replaced in
      the center env file
- [ ] Maintenance window scheduled and clinical users notified
- [ ] Rollback plan confirmed (see [Rollback](#rollback))

---

## Step 1 — Take a verified database backup

```bash
bash scripts/mongo_backup_archive.sh \
  --mongo-uri "${MONGO_URI}" \
  --out-dir "/data/coyote3/backups/mongo"
```

Verify the archive is non-empty and readable before continuing.

---

## Step 2 — Stop the v3.x stack

```bash
# Bring down all v3.x containers (do NOT use -v — keep volumes)
docker compose -f <your-v3-compose-file> down
```

---

## Step 3 — Deploy the v4.0.0 stack

Build and start the new stack. Use the appropriate compose file for your
environment.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

Wait for all services to report healthy:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml ps
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-5815}/api/v1/health"
```

!!! note
    The API performs **read-only index verification** on startup. It does not
    create or retire indexes automatically. If the startup log reports missing
    indexes, run `scripts/manage_mongo_indexes.py` as documented in
    [Maintenance and Quality](maintenance_and_quality.md).

---

## Step 4 — Run the clinical configuration migration

This step normalizes ASP, ASPC, ISGL, sample, and user scope documents to the
v4.0.0 field contract. Place the script in `migration_scripts/` (ignored by
git) and run with `--dry-run` first.

!!! caution
    Run `--dry-run` and inspect the output completely before applying.
    The script removes retired keys after writing the normalized replacement.
    Restore the backup from Step 1 to roll back.

```bash
# Dry run — inspect output before applying
PYTHONPATH=. python migration_scripts/20260729_normalize_clinical_configuration.py \
  --uri "${MONGO_URI}" \
  --database "${COYOTE3_DB}" \
  --dry-run

# Apply — run during the maintenance window only
PYTHONPATH=. python migration_scripts/20260729_normalize_clinical_configuration.py \
  --uri "${MONGO_URI}" \
  --database "${COYOTE3_DB}"
```

The script resolves collection names from `api/config/center/collections.toml`.

---

## Step 5 — Synchronize RBAC catalog

v4.0.0 ships an application-owned permission and role catalog. Sync it against
the existing database to insert any missing built-in policies and grants without
touching center-defined roles:

```bash
python scripts/sync_rbac_catalog.py \
  --mongo-uri "${MONGO_URI}" \
  --db "${COYOTE3_DB}"
```

This command:

- inserts missing bundled permission documents (marked `system_managed: true`)
- adds missing built-in role grants
- does **not** delete or overwrite center-defined roles or custom policies

After syncing, verify that existing users can still log in and that their
role assignments are intact.

---

## Step 6 — Seed new reference collections

v4.0.0 introduces collections that did not exist in v3.x. Seed them before
clinical ingest:

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB" \
  --username "superuser" \
  --email "superuser@your-center.org" \
  --password "<GENERATED_ADMIN_PASSWORD>"
```

Run this only for a new empty v4 database. It skips populated reference
collections and rejects partially initialized governance data. For an existing
v4 database, use the dedicated RBAC and reference-data maintenance procedures
instead of first-deployment bootstrap.

---

## Step 7 — Validate

Run the standard post-deployment checks:

```bash
# API health
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-5815}/api/v1/health"

# Confirm existing samples are visible
# Navigate to the application URL and verify sample list loads

# Confirm reports are accessible
# Open a previously generated report and verify it renders
```

Run the release browser smoke test against a controlled account if a staging
environment with real data is available:

```bash
export COYOTE3_E2E_BASE_URL="http://your-staging-host/coyote3"
export COYOTE3_E2E_USERNAME="validation-account"
export COYOTE3_E2E_PASSWORD="..."
export COYOTE3_E2E_DNA_SAMPLE="known-dna-sample-name"
export COYOTE3_E2E_RNA_SAMPLE="known-rna-sample-name"
cd frontend && npm run test:e2e:real
```

---

## Step 8 — Post-upgrade tasks

These items do not block go-live but should be completed within the first week:

- [ ] Review and update center-owned ASPC definitions to use the v4.0.0
      intent-profile filter fields (`somatic` / `germline`)
- [ ] Verify that notification delivery is working (test with a broadcast from
      Admin → Notifications)
- [ ] Confirm audit log entries are appearing for clinical actions
      (Admin → Audit Logs)
- [ ] Update your internal runbooks to reference the new compose files
      (`deploy/compose/` not the repo root)
- [ ] Remove the retired root-level `Dockerfile`, `Dockerfile.dev`, and
      `Dockerfile.redis` from any CI/CD pipelines that referenced them directly

---

## Rollback

If the upgrade must be aborted after Step 3:

1. Stop the v4.0.0 stack:

   ```bash
   ./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml down
   ```

2. If Step 4 (migration) was already applied, restore the database from the
   Step 1 backup:

   ```bash
   bash scripts/mongo_restore_archive.sh \
     --mongo-uri "${MONGO_URI}" \
     --archive "/data/coyote3/backups/mongo/backup.archive.gz" \
     --confirm RESTORE_PATIENT_DATA
   ```

3. Restart the v3.x stack:

   ```bash
   docker compose -f <your-v3-compose-file> up -d
   ```

4. Verify v3.x is operational before notifying users.

---

## Known differences after upgrade

| Behavior | v3.x | v4.0.0 |
|----------|------|--------|
| Sample URLs | ObjectId-based (`/sample/<id>`) | Name-based (`/sample/<name>`) — existing bookmarks will break |
| Report filenames | Flask-generated with legacy timestamp format | Backend-generated with UTC compact timestamp |
| Timestamp display | Server timezone | UTC storage; center-configured local time zone in UI |
| API documentation | None | `/api/v1/docs` (OpenAPI / Swagger UI) |
| Tailwind CSS pipeline | Separate build step | Embedded in Vite bundle — no separate build needed |
| Background workers | Same Celery | Same Celery but task contracts updated — old queued tasks will fail; drain the queue before upgrade |
| Auth cookies | Flask `session` cookie | New `coyote3_session` cookie — users will need to log in again |

---

## Getting help

If you encounter issues not covered here, check:

- [Troubleshooting](troubleshooting.md)
- [Backup and Recovery](backup_restore_and_snapshots.md)
- [GitHub Issues](https://github.com/SMD-Bioinformatics-Lund/coyote3/issues)
