# Initial Deployment Checklist

**Last verified:** 6 August 2026

Use this checklist for a first deployment.

For a shorter command reference, see:
[Maintenance And Quality](maintenance_and_quality.md).

## Scope

- Bring up stack
- Validate environment and secrets
- Validate ingest payloads
- Execute ingest check
- Confirm UI/API behavior
- Capture handoff evidence

## 0. Preconditions

- Docker and Docker Compose available
- Repo cloned
- Environment file prepared from `deploy/env/example.env`
- Real values set for all `CHANGE_ME_*` entries

Use the application-owned bootstrap catalogs as the baseline:

- `api/config/bootstrap/rbac` contains the canonical permission policies and
  built-in roles.
- `api/config/bootstrap/reference` contains compressed HGNC and VEP snapshots
  used only when those destination collections are empty.
- `api/config/bootstrap/demo_center` contains a synthetic ASP, ASPC, and ISGL
  suitable for validating a new installation.
- Replace the demo clinical configuration with approved center configuration
  before clinical use. Keep center-owned values in the deployment repository,
  not in the Coyote3 source checkout.

The bootstrap catalogs intentionally do not contain a username, password,
patient, or sample. The first local superuser credentials are supplied to the
bootstrap command at deployment time.

## 1. Preflight

```bash
scripts/center_preflight.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --seed-file api/config/bootstrap/demo_center \
  --reference-seed-data api/config/bootstrap/rbac \
  --reference-seed-data api/config/bootstrap/reference \
  --yaml-file demo_data/ingest/generic_case_control.yaml
```

Expected: `[ok] preflight passed`.

## 2. Start stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

Check status:

```bash
docker compose --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml ps
```

If the stack uses the compose-managed Mongo service, add:

```bash
--profile with-mongo
```

Example:

```bash
docker compose \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  --profile with-mongo \
  up -d --build
```

If Mongo volume was pre-existing, bootstrap/rotate app DB user with `mongosh`:

```bash
mongosh "<admin-mongo-uri>" --eval '
  db = db.getSiblingDB("'"${COYOTE3_DB:-coyote3}"'");
  var user = "'"${MONGO_APP_USER}"'";
  var pwd  = "'"${MONGO_APP_PASSWORD}"'";
  var roles = [{role: "readWrite", db: "'"${COYOTE3_DB:-coyote3}"'"}];
  var info = db.getUser(user);
  if (info) { db.updateUser(user, {pwd: pwd, roles: roles}); print("updated"); }
  else       { db.createUser({user: user, pwd: pwd, roles: roles}); print("created"); }
'
```

Compose-managed MongoDB is internal-only. Use an external/admin MongoDB URI for
host-side maintenance, or run database maintenance from a container attached to
the compose network.

## 3. Health checks

- API: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}/api/v1/health`
- UI: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}`

Command-line API check:

```bash
curl -fsS "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}/api/v1/health"
```

## 4. Bootstrap first API superuser

Email format note for bootstrap:

- Local/private domains are supported (for example `admin@coyote3.local`).
- Minimum requirement is valid `local@domain` shape.
- Invalid examples: `admin`, `@domain`, `admin@`.

Role level note:

- `superuser` is the unrestricted bootstrap role.
- `admin` remains permission-bound and should not be treated as unrestricted.
- Recommended full baseline:
  - `external=1`
  - `viewer=5`
  - `intern=7`
  - `user=9`
  - `manager=99`
  - `developer=9999`
  - `admin=99999`
  - `superuser=1000000`

```bash
${PYTHON_BIN:-python} scripts/bootstrap_local_admin.py \
  --mongo-uri "${MONGO_URI}" \
  --db "${COYOTE3_DB:-coyote3}" \
  --username "admin" \
  --email "admin@your-center.org" \
  --password "CHANGE_ME_ADMIN_PASSWORD" \
  --role-id "superuser" \
  --assay-group "hematology" \
  --assay "assay_1"
```

First-deployment behavior:

- `bootstrap_local_admin.py` fails fast if any CLI value still contains `CHANGE_ME`.
- This prevents accidental first-user creation with placeholder secrets.
- The command installs all bundled permission policies and roles before creating
  the local superuser.
- It runs only when `users`, `roles`, and `permissions` are all empty.
- A database that already has a superuser is reported as initialized and is not
  changed.
- A partially initialized governance database without a superuser is rejected
  for manual inspection; it is never overwritten automatically.
- Additional superusers must be created by an authenticated existing superuser.

The installed focused roles are `asp_manager`, `aspc_manager`, `isgl_manager`,
`operations_viewer`, `app_control_operator`, and `user_account_manager`. The
general `admin`, `developer`, `tester`, `manager`, `user`, `intern`, `viewer`,
and `external` roles are installed as well.

## 5. Initialize baseline collections (strict order)

Required order before first DNA/RNA sample ingest:

1. `permissions` and `roles` from `api/config/bootstrap/rbac`
2. the first local `superuser`, supplied through the bootstrap CLI
3. `assay_specific_panels`, `asp_configs`, and `insilico_genelists` from an
   approved center seed or the synthetic demo catalog
4. `hgnc_genes` (required for MANE transcript selection and gene metadata)
5. `vep_metadata` (required reference metadata for variant interpretation)

Notes:

- `bootstrap_center_collections.sh` intentionally skips `users`.
- First superuser bootstrap is handled in step 4 (`bootstrap_local_admin.py`).
- Local-admin bootstrap writes user audit metadata: `created_by`, `created_on`, `updated_by`, `updated_on`.
- Collection bootstrap also stamps all seeded documents with runtime audit metadata:
  - `created_by`/`updated_by` = bootstrap superuser
  - `created_on`/`updated_on` = current UTC timestamp at seed execution
- `asp_configs` must include `is_active=true` (otherwise sample views can return "Assay config not found for sample").
- `asp_configs` must include valid `filters` and `reporting` objects.
- DNA SNV base strategy is defined by `asp_configs.filters` threshold/consequence fields.
- DNA assay-specific SNV operator rules are defined by `asp_configs.query.snv`.
- DNA CNV strategy is defined by `asp_configs.filters.cnv_*` fields.
- RNA fusion strategy is defined by `asp_configs.filters.fusion_*` fields.
- Managed admin forms (ASP/ASPC/ISGL/users/roles/permissions) are rendered from backend contracts, not DB `schemas` JSON.
- The application-owned RBAC catalog is the complete out-of-the-box baseline,
  so user creation and role policy mapping are available immediately.
- Confirm every bundled permission has `system_managed: true`. System policies
  must expose View and role-assignment behavior, but not edit, status-toggle, or
  delete actions.
- Existing deployments should synchronize newly bundled permission policies and
  built-in role grants after an application upgrade:

  ```bash
  python scripts/sync_rbac_catalog.py \
    --mongo-uri "$MONGO_URI" \
    --db "$COYOTE3_DB"
  ```

  The command inserts missing bundled policies and adds missing bundled grants
  to matching built-in roles. It preserves existing policy documents, custom
  roles, and center-added grants, and is safe to run repeatedly.
- The bundled demo clinical resources use `assay_1`, `base`, `production`, and
  `hematology`. They are synthetic smoke-test data, not a clinical definition.
- `permissions` and `roles` come from `api/config/bootstrap/rbac`.
- The release includes compact HGNC and VEP bootstrap snapshots. The bootstrap
  command checks collection occupancy first and skips any nonempty destination.
  Updating a populated reference collection is a separate, explicitly
  validated reference-release operation.

Optional collections:

1. `insilico_genelists` (focused gene-list filtering)
2. `civic_genes`
3. `civic_variants`
4. `cosmic`
5. `hpaexpr`
6. `iarc_tp53`
7. `oncokb_actionable`
8. `oncokb_genes`

Seed through internal collection insert endpoints documented in
[API / Ingestion API](../api/ingestion_api.md).
Use `GET /api/v1/internal/ingest/collections` to list the currently supported
validated collection names.

Recommended one-shot command:

```bash
scripts/bootstrap_center_collections.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}" \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --seed-file api/config/bootstrap/demo_center \
  --reference-seed-data api/config/bootstrap/rbac \
  --reference-seed-data api/config/bootstrap/reference \
  --with-optional
```

General first-run command shape:

```bash
scripts/center_first_run.sh \
  --env-file <ENV_FILE> \
  --compose-file <COMPOSE_FILE> \
  [--with-mongo] \
  [--compose-profile <PROFILE>] \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:<HTTP_PORT>" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@your-center.org" \
  --admin-password "<ADMIN_PASSWORD>" \
  --seed-file api/config/bootstrap/demo_center \
  --seed-data-pack api/config/bootstrap/rbac \
  --yaml-file demo_data/ingest/generic_case_control.yaml \
  --with-optional
```

Prod-like local Docker command with compose-managed Mongo:

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml \
  --with-mongo \
  --api-base-url "http://localhost:5815" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@coyote3.local" \
  --admin-password "<ADMIN_PASSWORD>" \
  --seed-file api/config/bootstrap/demo_center \
  --seed-data-pack api/config/bootstrap/rbac \
  --yaml-file demo_data/ingest/generic_case_control.yaml \
  --with-optional
```

Credential source rule:

- For `scripts/center_first_run.sh`, always pass:
  - `--admin-username`
  - `--admin-email`
  - `--admin-password`

Execution mode notes:

- Default mode retries one failed collection seed once with `ignore_duplicates=true`.
- `--skip-existing` enables duplicate-tolerant seeding from the first attempt.
- `--strict-no-retry` disables retry and fails immediately on first collection error.
- In `center_first_run.sh`, combine `--strict-no-retry` with `--skip-existing`
  because the first-user bootstrap creates RBAC documents before seeding.

Before clinical use, replace the synthetic demo ASP, ASPC, and ISGL with the
center's reviewed definitions. The bootstrap flow validates schema, ASPC, ASP,
and ISGL consistency before writing collections.

## 6. Validate and ingest demo sample

```bash
${PYTHON_BIN:-python} scripts/validate_ingest_spec.py \
  --yaml demo_data/ingest/generic_case_control.yaml \
  --check-files
```

```bash
scripts/center_check.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}" \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --yaml-file demo_data/ingest/generic_case_control.yaml
```

Notes:

- `center_check.sh` sets `increment=true` in the submitted YAML payload to avoid duplicate-sample failures on reruns.
- On local Docker deployments (`localhost` API), the script auto-stages ingest input files into the API container when needed.
- In general, ingest file paths in YAML must be readable from inside the API runtime (container/host where API runs), not only from your shell machine.
- Use [API / Sample YAML Guide](../api/sample_yaml.md) for the manifest contract and [API / Sample Input Files](../api/sample_input_files.md) for the raw file formats behind that manifest.

If you are upgrading an older deployment, write any reviewed one-time repair in
`migration_scripts/`. That folder is ignored by git, so center-specific
conversion code and operational scratch payloads stay out of the supported
application scripts. Promote only repeatable maintenance workflows back into
`scripts/` with tests and documentation.

## 7. Functional verification

- Login via UI using center-provisioned account
- Find ingested sample in sample listing
- Open variant/CNV/fusion views
- Open report pages and verify render succeeds

Admin verification matrix:

1. Users:
   - Create user (role dropdown populated from seeded `roles`)
   - Confirm role-derived permissions are shown
   - Confirm explicit user allow/deny overrides are saved
2. Roles:
   - Create role with allow/deny permissions
   - Verify role appears in user-create role dropdown
3. Permissions:
   - Create permission and confirm it appears in role permission lists
4. ASP:
   - Create assay panel and verify it appears in ASP list
5. ASPC (DNA/RNA):
   - Create config and verify `assay_name` dropdown is populated from ASP
6. ISGL:
   - Create genelist and verify assay-group and assay assignment behavior

Automated verification baseline:

```bash
PYTHONPATH=. python -m pytest -q tests/unit/test_admin_services.py tests/unit/test_services_admin_workflows_extended.py
```

## 8. Handoff artifacts

Record and store:

- Env file path used (not secret values)
- Compose file used
- `docker compose ps` output
- Health check output
- Ingest check result and seeded-collection order execution record
- Known follow-up items

## 9. Rollback and cleanup

Stop services:

```bash
docker compose --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml down
```

If data reset is required, follow backup/restore procedures in
[Backup Restore And Snapshots](backup_restore_and_snapshots.md).

## 10. One-command equivalent

For fully automated initial setup:

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_PORT:-8804}" \
  --admin-email "admin@your-center.org" \
  --admin-password "CHANGE_ME" \
  --seed-file api/config/bootstrap/demo_center \
  --seed-data-pack api/config/bootstrap/rbac \
  --yaml-file demo_data/ingest/generic_case_control.yaml \
  --with-optional \
  --skip-existing \
  --strict-no-retry
```
