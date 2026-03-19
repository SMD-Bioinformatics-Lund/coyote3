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

## 3. Health checks

- API: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}/api/v1/health`
- UI: `http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_WEB_PORT:-8005}`

Command-line API check:

```bash
curl -fsS "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}/api/v1/health"
```

## 4. Validate and ingest demo sample

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

## 5. Functional verification

- Login via UI using center-provisioned account
- Find ingested sample in sample listing
- Open variant/CNV/fusion views
- Open report pages and verify render succeeds

## 6. Handoff artifacts

Record and store:

- Env file path used (not secret values)
- Compose file used
- `docker compose ps` output
- Health check output
- Smoke ingest result
- Known follow-up items

## 7. Rollback and cleanup

Stop services:

```bash
docker compose --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml down
```

If data reset is required, follow backup/restore procedures in
[Backup Restore And Snapshots](backup-restore-and-snapshots.md).
