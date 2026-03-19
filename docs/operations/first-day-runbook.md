# First Day Runbook

Use this runbook on day 1 when bringing up Coyote3 at a new center.

## Scope

- Bring up stack
- Validate environment and secrets
- Validate ingest payloads
- Execute smoke ingest
- Confirm UI/API behavior
- Capture handoff evidence

## 0. Preconditions

- Docker and Docker Compose available
- Repo cloned
- Environment file prepared from `deploy/env/example.*.env`
- Real values set for all `CHANGE_ME_*` entries

## 1. Preflight

```bash
scripts/center_preflight.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml
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
python scripts/mongo_bootstrap_users.py \
  --mongo-uri "mongodb://${MONGO_ROOT_USERNAME}:${MONGO_ROOT_PASSWORD}@localhost:${COYOTE3_STAGE_MONGO_PORT:-8008}/admin?authSource=admin" \
  --app-db "${COYOTE3_DB:-coyote3}" \
  --app-user "${MONGO_APP_USER}" \
  --app-password "${MONGO_APP_PASSWORD}"
```

## 3. Health checks

- API: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}/api/v1/health`
- UI: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_WEB_PORT:-8005}`

Command-line API check:

```bash
curl -fsS "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}/api/v1/health"
```

## 4. Seed baseline collections (strict order)

Required order before first DNA/RNA sample ingest:

1. `permissions`
2. `roles`
3. `users`
4. `asp_configs`
5. `assay_specific_panels`
6. `insilico_genelists`
7. `refseq_canonical` (required for DNA canonical transcript selection)
8. `hgnc_genes` (required for gene metadata endpoints/UI)

Optional but recommended:

1. `civic_genes`
2. `civic_variants`
3. `oncokb_genes`
4. `oncokb_actionable`
5. `brcaexchange`
6. `iarc_tp53`
7. `cosmic`
8. `vep_metadata`

Seed through internal collection insert endpoints documented in
[API / Ingestion API](../api/ingestion-api.md).

Recommended one-shot command:

```bash
scripts/bootstrap_center_collections.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}" \
  --internal-token "${INTERNAL_API_TOKEN}" \
  --seed-file tests/fixtures/db_dummy/center_template_seed.json \
  --with-optional
```

Before running, adapt `tests/fixtures/db_dummy/center_template_seed.json` to
your local assay names/groups. The bootstrap flow validates ASPC and ISGL
consistency before writing collections.

## 5. Validate and ingest demo sample

```bash
python scripts/validate_ingest_spec.py \
  --yaml tests/data/ingest_demo/generic_case_control.yaml \
  --check-files
```

```bash
scripts/center_smoke.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}" \
  --internal-token "$INTERNAL_API_TOKEN" \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

## 6. Functional verification

- Login via UI using center-provisioned account
- Find ingested sample in sample listing
- Open variant/CNV/fusion views
- Open report pages and verify render succeeds

## 7. Handoff artifacts

Record and store:

- Env file path used (not secret values)
- Compose file used
- `docker compose ps` output
- Health check output
- Smoke ingest result and seeded-collection order execution record
- Known follow-up items

## 8. Rollback and cleanup

Stop services:

```bash
docker compose --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml down
```

If data reset is required, follow backup/restore procedures in
[Backup Restore And Snapshots](backup-restore-and-snapshots.md).
