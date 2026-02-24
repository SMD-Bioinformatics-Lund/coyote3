# Installation and Access

This chapter is for operators, analysts, and technical users who need to run Coyote3 reliably.

## Deployment targets

Coyote3 is typically deployed in three modes:

- Docker Compose production-like deployment.
- Docker Compose development deployment.
- Local Python run for debugging.

## Required services

Coyote3 needs these backend dependencies:

- MongoDB (primary data store).
- Redis (cache/session support).
- Filesystem path for report output.

## Required environment variables

Minimum required variables:

- `SECRET_KEY`
- `COYOTE3_FERNET_KEY`
- `FLASK_MONGO_HOST`
- `FLASK_MONGO_PORT`
- `COYOTE3_DB_NAME`
- `CACHE_REDIS_URL`
- `CACHE_REDIS_HOST`
- `SESSION_COOKIE_NAME`
- `REPORTS_BASE_PATH`
- `DEVELOPMENT`
- `TESTING`

Useful repository references:

- `example.env`
- `.coyote3_env`
- `.coyote3_dev_env`

## Database target selection (important)

Use `coyote3` for production/runtime documentation parity.

- Production DB name: `coyote3`
- Development DB name: `coyote_dev_3`

For real workflow behavior and complete data shapes, point Coyote3 runtime to `coyote3`:

```env
COYOTE3_DB_NAME=coyote3
FLASK_MONGO_HOST=172.17.0.1
FLASK_MONGO_PORT=27017
```

## Production-like install (Docker Compose)

From repo root:

```bash
docker-compose up -d
```

Then verify containers are healthy and logs are clean.

## Development install (Docker Compose)

```bash
docker-compose -f docker-compose.dev.yml up -d
```

Use this for iterative development and local debugging.

## Scripted installation

```bash
./scripts/install.sh
./scripts/install.dev.sh
```

These scripts typically:

1. Load environment files.
2. Build app image.
3. Start/ensure Redis.
4. Start Coyote3 container with configured mounts/network.

## Local Python setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python wsgi.py
```

Use this only when you need local code-level debugging.

## First-time access check

Open:

- `/` or `/login`

Then validate:

1. `/samples` opens.
2. `/dashboard/` opens.
3. One DNA sample opens from `/samples` into `/dna/sample/<sample_id>`.
4. One RNA sample opens from `/samples` into `/rna/sample/<sample_id>K=`.
5. A reported sample has accessible report links under `/samples/<sample_id>/reports/<report_id>`.

## Post-install data integrity checks

Confirm in `coyote3`:

- `samples` has rows.
- `variants` has rows.
- `annotation` has rows.
- `asp_configs` and `assay_specific_panels` have rows.
- `users`, `roles`, `permissions` are populated.

Without these, UI pages can load but show empty/broken behavior.

## Access model after login

Route access is controlled by:

- Session authentication.
- Permission checks (`require(...)`).
- Sample-level assay access (`require_sample_access`).

So users can be logged in but still blocked from specific pages/actions.

## Report storage setup

`REPORTS_BASE_PATH` must be writable by the Coyote3 runtime user.

At report save time, Coyote3 writes HTML report files and then updates sample/report metadata and `reported_variants` snapshot rows.

If write permission is missing, preview may work but save will fail.

## Recommended production checklist

1. Pin `COYOTE3_DB_NAME=coyote3`.
2. Verify Redis connectivity.
3. Verify report directory exists and is writable.
4. Confirm at least one admin user can open `/admin/`.
5. Confirm one analyst can open `/samples` and `/dna/sample/<sample_id>`.
6. Save one report and verify sample moves from live to reported.
