# Dev -> Staging -> Prod Flow

This runbook defines the standard execution flow for Coyote3 changes from local development to staging validation and production deployment.

It is command-first, reproducible, and aligned to the repository CI gates and compose runtime.

## 1. Scope and Principles

- Dev, staging, and production use separate environment files and separate databases.
- Promotion happens only after CI gates and staging verification are green.
- Deployments are image/config based; no ad hoc manual edits inside running containers.
- Every deployment must have rollback commands prepared before execution.

## 2. Required Files and Environment Setup

Create environment files from templates:

```bash
cp example.dev.env .coyote3_dev_env
cp example.stage.env .coyote3_stage_env
cp example.prod.env .coyote3_env
```

Required per-environment differences:

- `MONGO_URI` and DB name (`COYOTE3_DB`)
- Mongo credentials (`MONGO_ROOT_USERNAME`, `MONGO_ROOT_PASSWORD`, `MONGO_APP_USER`, `MONGO_APP_PASSWORD`)
- secrets (`SECRET_KEY`, `COYOTE3_FERNET_KEY`, `INTERNAL_API_TOKEN`, `API_SESSION_SALT`)
- host ports
- session cookie names
- report path

Build metadata (set at deploy time or in env):

```bash
export COYOTE3_VERSION="$(python3 coyote/__version__.py)"
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

## 3. CI Flow (Repository Standard)

The quality workflow is defined in `.github/workflows/quality.yml`.

Execution order:

1. `ruff` static checks
2. `black --check`
3. unit tests
4. web boundary tests
5. API smoke tests
6. contract tests
7. family coverage gates (`scripts/run_family_coverage_gates.sh`)
8. DB boundary baseline check
9. web/api route contract guardrail
10. compose config smoke checks (prod + dev compose files)
11. snapshot tooling smoke checks

Local command to mirror core CI gates:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_family_coverage_gates.sh
PYTHONPATH=. /home/ram/.virtualenvs/coyote3/bin/python -m pytest -q tests
```

## 4. Development Flow

Start dev stack:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  -p coyote3-dev \
  up -d --build
```

Health checks:

```bash
docker compose --env-file .coyote3_dev_env -f deploy/compose/docker-compose.dev.yml -p coyote3-dev ps
curl -f http://localhost:${COYOTE3_DEV_API_PORT:-6816}/api/v1/health
```

Run test gates locally:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_family_coverage_gates.sh
```

Optional full coverage report:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_tests_with_coverage.sh
```

## 5. Staging Deployment Flow

Validate compose before deploy:

```bash
docker compose --env-file .coyote3_stage_env -f deploy/compose/docker-compose.stage.yml config -q
```

Deploy staging:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  -p coyote3-stage \
  up -d --build
```

Stage dataset refresh from production snapshot (recommended):

```bash
scripts/snapshot_restore_stage.sh \
  --source-uri "mongodb://<prod-app-user>:<prod-app-pass>@<prod-mongo-host>:27017/coyote3" \
  --source-db coyote3 \
  --sample-count 60
```

Run identity migration on staging DB after restore/import:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri "<staging-mongo-uri>" \
  --db "coyote3_stage"
```

Staging verification checklist:

```bash
docker compose --env-file .coyote3_stage_env -f deploy/compose/docker-compose.stage.yml -p coyote3-stage ps
curl -f http://localhost:${COYOTE3_STAGE_API_PORT:-7816}/api/v1/health
curl -f http://localhost:${COYOTE3_STAGE_WEB_PORT:-7814}/coyote3/
docker compose --env-file .coyote3_stage_env -f deploy/compose/docker-compose.stage.yml -p coyote3-stage logs --tail=200 coyote3_stage_api coyote3_stage_web
```

Functional staging checks (minimum):

- login/logout
- dashboard load
- samples listing and filters
- DNA/RNA detail page load
- report preview/save path
- admin pagination/search

## 6. Production Deployment Flow

Pre-deploy gate (must be complete):

- CI workflow green on release commit
- staging verification completed
- migration command prepared (if needed)
- rollback target tag identified

Deploy production:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  -p coyote3-prod \
  up -d --build
```

Post-deploy verification:

```bash
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.yml -p coyote3-prod ps
curl -f http://localhost:${COYOTE3_API_PORT:-5816}/api/v1/health
curl -f http://localhost:${COYOTE3_WEB_PORT:-5814}/coyote3/
docker compose --env-file .coyote3_env -f deploy/compose/docker-compose.yml -p coyote3-prod logs --tail=200 coyote3_api coyote3_web
```

## 7. Rollback Procedure

Rollback to previous known-good image/config commit:

```bash
git checkout <previous-good-tag-or-commit>
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  -p coyote3-prod \
  up -d --build
```

Then verify:

```bash
curl -f http://localhost:${COYOTE3_API_PORT:-5816}/api/v1/health
curl -f http://localhost:${COYOTE3_WEB_PORT:-5814}/coyote3/
```

## 8. Important Runtime Notes

- Do not share production Mongo URI or secrets with staging/dev.
- Production Mongo must be dedicated to production only (no dev/stage applications against prod DB).
- Use per-environment Mongo app users; avoid using root user for application traffic.
- Keep staging and prod ports distinct when on same host.
- This repository uses explicit `container_name`; avoid running multiple same-compose deployments on one host unless names/versioning are intentionally separated.
- Run migrations with explicit `--mongo-uri` and `--db` to prevent cross-environment mistakes.

## 9. Release Evidence Artifacts

For each production release, record:

- commit hash and image version
- CI run URL
- staging verification checklist result
- migration command and output summary
- smoke check output summary
- rollback target and verification command list
