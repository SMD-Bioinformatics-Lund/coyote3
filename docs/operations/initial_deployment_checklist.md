# Initial Deployment Checklist

Use this checklist for first-time Coyote3 deployment at a new center.

For a concise command-only version without repeated context blocks, see:
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
- Environment file prepared from `deploy/env/example.*.env`
- Real values set for all `CHANGE_ME_*` entries

Use the repository seed as the first-run baseline:

- `tests/fixtures/db_dummy/all_collections_dummy`
- `tests/data/seed_data` (when passed via `--reference-seed-data`)
- Replace neutral placeholders (`assay_1`, `hematology`) with your center values
- Keep those edited seed values under version control in your deployment repo

Seed source split:

- `all_collections_dummy` provides demo/runtime collections (including `asp_configs`, `assay_specific_panels`, and demo data payload collections).
- `seed_data` provides compressed baseline reference/RBAC collections (`permissions`, `roles`, `refseq_canonical`, `hgnc_genes`, `vep_metadata`).

## 1. Preflight

```bash
scripts/center_preflight.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
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

If Mongo volume was pre-existing, bootstrap/rotate app DB user:

```bash
${PYTHON_BIN:-python} scripts/mongo_bootstrap_users.py \
  --mongo-uri "mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/admin?authSource=admin" \
  --app-db "${COYOTE3_DB:-coyote3}" \
  --app-user "${MONGO_APP_USER}" \
  --app-password "${MONGO_APP_PASSWORD}"
```

## 3. Health checks

- API: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}/api/v1/health`
- UI: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_WEB_PORT:-8805}`

Command-line API check:

```bash
curl -fsS "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}/api/v1/health"
```

## 4. Bootstrap first API admin (one-time)

Email format note for bootstrap:

- Local/private domains are supported (for example `admin@coyote3.local`).
- Minimum requirement is valid `local@domain` shape.
- Invalid examples: `admin`, `@domain`, `admin@`.

Role level note for bootstrap and seeds:

- `admin` role must be level `99999` (not `100`).
- Recommended full baseline:
  - `external=1`
  - `viewer=5`
  - `intern=7`
  - `user=9`
  - `manager=99`
  - `developer=9999`
  - `admin=99999`

```bash
${PYTHON_BIN:-python} scripts/bootstrap_local_admin.py \
  --mongo-uri "mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/${COYOTE3_DB:-coyote3}?authSource=${COYOTE3_DB:-coyote3}" \
  --db "${COYOTE3_DB:-coyote3}" \
  --email "admin@your-center.org" \
  --password "CHANGE_ME_ADMIN_PASSWORD" \
  --assay-group "hematology" \
  --assay "assay_1"
```

Guardrail:

- `bootstrap_local_admin.py` now fails fast if any CLI value still contains `CHANGE_ME`.
- This prevents accidental first-user creation with placeholder secrets.

## 5. Initialize baseline collections (strict order)

Required order before first DNA/RNA sample ingest:

1. `permissions`
2. `roles`
3. `refseq_canonical` (required for DNA canonical transcript selection)
4. `hgnc_genes` (required for gene metadata endpoints/UI)
5. `vep_metadata` (required reference metadata for variant interpretation)
6. `asp_configs`
7. `assay_specific_panels`

Notes:

- `bootstrap_center_collections.sh` intentionally skips `users`.
- First user bootstrap is handled in step 4 (`bootstrap_local_admin.py`).
- Local-admin bootstrap writes user audit metadata: `created_by`, `created_on`, `updated_by`, `updated_on`.
- Collection bootstrap also stamps all seeded documents with runtime audit metadata:
  - `created_by`/`updated_by` = bootstrap admin user
  - `created_on`/`updated_on` = current UTC timestamp at seed execution
- `asp_configs` must include `is_active=true` (otherwise sample views can return "Assay config not found for sample").
- `asp_configs` must include valid `filters` and `reporting` objects.
- DNA SNV base strategy is defined by `asp_configs.filters` threshold/consequence fields.
- DNA assay-specific SNV operator rules are defined by `asp_configs.query.snv`.
- DNA CNV strategy is defined by `asp_configs.filters.cnv_*` fields.
- RNA fusion strategy is defined by `asp_configs.filters.fusion_*` fields.
- Managed admin forms (ASP/ASPC/ISGL/users/roles/permissions) are rendered from backend contracts, not DB `schemas` JSON.
- Baseline seed includes a complete out-of-the-box RBAC baseline (`permissions` + `roles`) so user creation dropdowns and role policy mapping are immediately available on first bootstrap.
- Non-RBAC admin baseline collections (`asp_configs`, `assay_specific_panels`, `insilico_genelists`) intentionally remain demo-safe first-run data (`assay_1`, `hematology`) and should be replaced with center-specific values during onboarding.
- `asp_configs` and `assay_specific_panels` are first-sample demo onboarding collections
  sourced from `--seed-file`; compressed files in `tests/data/seed_data` are optional overrides.
- `permissions`, `roles`, `refseq_canonical`, `hgnc_genes`, and `vep_metadata`
  are sourced from `--reference-seed-data` when that argument is provided.

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
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}" \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --reference-seed-data tests/data/seed_data \
  --with-optional
```

All-environment first-load (single command shape):

```bash
scripts/center_first_run.sh \
  --env-file <ENV_FILE> \
  --compose-file <COMPOSE_FILE> \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:<API_PORT>" \
  --admin-email "admin@your-center.org" \
  --admin-password "<ADMIN_PASSWORD>" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

Credential source rule:

- For `scripts/center_first_run.sh`, always pass `--admin-email` and `--admin-password` explicitly.

Execution mode notes:

- Default mode retries one failed collection seed once with `ignore_duplicates=true`.
- `--skip-existing` enables duplicate-tolerant seeding from the first attempt.
- `--strict-no-retry` disables retry and fails immediately on first collection error.
- In `center_first_run.sh`, combine `--strict-no-retry` with `--skip-existing`
  because first-admin bootstrap pre-creates RBAC documents before seeding.

Before running, adapt `tests/fixtures/db_dummy/all_collections_dummy` to
your local assay names/groups. The bootstrap flow validates schema, ASPC, ASP,
and ISGL consistency before writing collections.

## 6. Validate and ingest demo sample

```bash
${PYTHON_BIN:-python} scripts/validate_ingest_spec.py \
  --yaml tests/data/ingest_demo/generic_case_control.yaml \
  --check-files
```

```bash
scripts/center_check.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}" \
  --username "admin@your-center.org" \
  --password "CHANGE_ME" \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

Notes:

- `center_check.sh` sets `increment=true` in the submitted YAML payload to avoid duplicate-sample failures on reruns.
- On local Docker deployments (`localhost` API), the script auto-stages ingest input files into the API container when needed.
- In general, ingest file paths in YAML must be readable from inside the API runtime (container/host where API runs), not only from your shell machine.

If you are upgrading an older deployment,
run one-time repair before ingest check:

```bash
${PYTHON_BIN:-python} scripts/repair_center_seed_baseline.py \
  --mongo-uri "mongodb://${MONGO_APP_USER}:${MONGO_APP_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8808}/${COYOTE3_DB:-coyote3}?authSource=${COYOTE3_DB:-coyote3}" \
  --db "${COYOTE3_DB:-coyote3}"
```

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
   - Create permission and confirm it appears in role/user permission lists
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
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8806}" \
  --admin-email "admin@your-center.org" \
  --admin-password "CHANGE_ME" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional \
  --skip-existing \
  --strict-no-retry
```
