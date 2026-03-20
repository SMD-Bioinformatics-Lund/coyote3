# Troubleshooting

## `createIndexes requires authentication`

Symptom:

- startup fails while ensuring indexes

Cause:

- app connects without valid Mongo app credentials

Action:

1. verify `MONGO_URI` includes user/password
2. ensure app user exists in target DB
3. if old volume predates auth bootstrap, create user manually or re-init volume

## Missing env file in compose

Symptom:

- compose fails: `.coyote3_env not found`

Action:

```bash
cp deploy/env/example.prod.env .coyote3_env
```

Then set real secret values.

## Wrong Python interpreter for gates

Symptom:

- `No module named pytest` in gate scripts

Action:

```bash
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

## Pre-commit failing with `.venv/bin/pytest not found`

Action:

- update hook commands to use interpreter from active env (or explicit absolute python path)
- rerun:

```bash
python -m pre_commit run --all-files
```

## CI compose config check fails on env file

Action:

- ensure workflow creates or templates required env files before `docker compose config -q`
- keep `deploy/env/example.*.env` synchronized with actual required keys

## Dashboard metrics collection growth

Symptom:

- `dashboard_metrics` collection grows continuously

Checks:

1. Confirm `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` is set to a positive value.
2. Verify TTL index exists on `updated_at`:

```javascript
db.dashboard_metrics.getIndexes().filter(i => i.name === "updated_at_ttl_1")
```

3. Confirm `updated_at` is being set on snapshot writes.
4. Remember Mongo TTL cleanup runs asynchronously (not immediate at exact second).

Action:

- If index missing, restart API once after config update so index bootstrap runs.
- If retention should be longer/shorter, tune `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS`.
