# Migrate an existing Coyote v3 installation

Use this procedure only when moving an existing Coyote v3 database and its
clinical records to Coyote3. It is not part of a first installation. For an
empty database, follow [first installation](../start_here/first_installation.md)
instead.

> **Caution**
>
> Migration changes configuration and identity documents to the Coyote3
> contract. Complete the procedure during a maintenance window, beginning with
> a verified backup and ending with documented validation evidence.

## Migration scope

The migration preserves clinical finding, comment, report, and audit data while
normalizing the configuration and identity records required by Coyote3.

| Document type | Required destination contract | Procedure |
| --- | --- | --- |
| ASP, ASPC, and ISGL | `asp_id`, `subpanel_id`, `environment`, `asp_ids`, and `asp_groups` | Normalize configuration records in step 4. |
| Sample filters | Intent-specific `somatic` and `germline` filter profiles | Preserve the stored filter snapshot while normalizing its structure in step 4. |
| Users and roles | Application permission identifiers and role grants | Synchronize bundled permissions and roles in step 5. |
| Permissions | System-managed application permission catalog | Synchronize in step 5; preserve centre-defined records. |

---

## Preconditions

Work through this list before starting. Do not proceed if any item cannot be satisfied.

- [ ] Archive backup of the full database taken and verified
      (`scripts/mongo_backup_archive.sh`)
- [ ] Source installation confirmed healthy: samples and saved reports can be read
- [ ] Target Coyote3 images build successfully in a controlled environment
- [ ] Center configuration files reviewed against the Coyote3 contract
      (`api/config/center/` — see [Center Configuration Files](center_configuration_files.md))
- [ ] `deploy/env/example.env` reviewed; every `CHANGE_ME` value replaced in
      the center env file
- [ ] Maintenance window scheduled and clinical users notified
- [ ] Rollback plan confirmed (see [Roll back safely](#roll-back-safely))

---

## Step 1 — Take a verified database backup

```bash
bash scripts/mongo_backup_archive.sh \
  --mongo-uri "${MONGO_URI}" \
  --out-dir "/data/coyote3/backups/mongo"
```

Verify the archive is non-empty and readable before continuing.

---

## Step 2 — Stop the source application

```bash
# Stop source containers without deleting volumes.
docker compose -f <your-v3-compose-file> down
```

---

## Step 3 — Start the Coyote3 application

Build and start the target stack using the centre environment file.

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

> **Note**
>
> The API performs **read-only index verification** on startup. It does not
> create or retire indexes automatically. If the startup log reports missing
> indexes, run `scripts/manage_mongo_indexes.py` as documented in
> [Maintenance and Quality](maintenance_and_quality.md).
>

---

## Step 4 — Normalize clinical configuration

This step normalizes ASP, ASPC, ISGL, sample, and user-scope documents to the
Coyote3 field contract. Place the reviewed migration script in
`migration_scripts/` (ignored by Git) and run it with `--dry-run` first.

> **Caution**
>
> Run `--dry-run` and inspect the output completely before applying.
> The script removes retired keys after writing the normalized replacement.
> Restore the backup from Step 1 to roll back.
>

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

## Step 5 — Synchronize permissions and roles

Coyote3 ships an application-owned permission and role catalog. Synchronize it
against the database to add missing system policies and grants without changing
centre-defined roles:

```bash
python scripts/sync_rbac_catalog.py \
  --mongo-uri "${MONGO_URI}" \
  --identity-db "${IDENTITY_DB}"
```

This command:

- inserts missing bundled permission documents (marked `system_managed: true`)
- adds missing built-in role grants
- does **not** delete or overwrite center-defined roles or custom policies

After syncing, verify that existing users can still log in and that their
role assignments are intact.

---

## Step 6 — Prepare reference collections when required

An empty target database requires the bundled reference collections and first
local administrator before clinical ingest:

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB" \
  --identity-db "$IDENTITY_DB" \
  --username "superuser" \
  --email "superuser@your-center.org" \
  --password "<GENERATED_ADMIN_PASSWORD>"
```

Run this only against an empty target database. It skips populated reference
collections and rejects partially initialized governance data. Use the dedicated
RBAC and reference-data maintenance procedures for a populated database.

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

## Step 8 — Complete operational validation

Record the following checks before the target installation is accepted for
clinical use:

- [ ] Review centre-owned ASPC definitions for the Coyote3
      intent-profile filter fields (`somatic` / `germline`)
- [ ] Verify that notification delivery is working (test with a broadcast from
      Admin → Notifications)
- [ ] Confirm audit log entries are appearing for clinical actions
      (Admin → Audit Logs)
- [ ] Update internal runbooks to reference the deployed Compose files

---

## Roll back safely

If the migration must be aborted after step 3:

1. Stop the target Coyote3 stack:

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

3. Restart the source application:

   ```bash
   docker compose -f <your-v3-compose-file> up -d
   ```

4. Verify that the source application is operational before notifying users.

---

## Operational consequences

| Area | Required operator action |
| --- | --- |
| Saved browser links | Update links to use Coyote3 name-based sample routes. |
| Browser sessions | Ask users to sign in again after the migration. |
| Queued background work | Drain source queues before the cut-over; do not transfer source queued tasks to the target worker. |
| Timestamps | Confirm the centre local-time-zone setting before reviewing UI dates. |
| API consumers | Point supported clients to `/api/v1/docs` and validate authentication before enabling integrations. |

---

## Getting help

If you encounter issues not covered here, check:

- [Troubleshooting](troubleshooting.md)
- [Backup and Recovery](backup_restore_and_snapshots.md)
- [GitHub Issues](https://github.com/SMD-Bioinformatics-Lund/coyote3/issues)
