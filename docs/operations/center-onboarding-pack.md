# Center Onboarding Pack

This pack is intended for a new center taking this repo and standing up Coyote3 end-to-end.

## 1. Clone and prepare environment

```bash
git clone <your-fork-or-upstream>
cd coyote3
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Select your target environment template:

```bash
cp deploy/env/example.stage.env .coyote3_stage_env
# or
cp deploy/env/example.prod.env .coyote3_env
```

Set real values for all `CHANGE_ME_*` keys.

## 2. Run preflight validation

```bash
scripts/center_preflight.sh \
  --env-file .coyote3_stage_env \
  --compose-file deploy/compose/docker-compose.stage.yml
```

This validates:

- required secrets present and non-placeholder
- compose renders successfully
- mandatory runtime keys exist
- numeric port values are valid

## 3. Start stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

## 4. Validate ingestion inputs

```bash
python scripts/validate_ingest_spec.py \
  --yaml tests/data/ingest_demo/generic_case_control.yaml \
  --check-files --json
```

## 5. Run end-to-end smoke ingest

```bash
scripts/center_smoke.sh \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:${COYOTE3_STAGE_API_PORT:-8006}" \
  --internal-token "$INTERNAL_API_TOKEN" \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

## 6. Verify UI/API

- API health: `GET /api/v1/health`
- Open UI and login using provisioned user
- Verify sample appears and related findings pages load

## 7. Next hardening steps

Use:

- [Minimum Production Baseline](minimum-production-baseline.md)
- [First Day Runbook](first-day-runbook.md)
