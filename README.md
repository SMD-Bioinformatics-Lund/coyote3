# Coyote3

Coyote3 is a genomic interpretation and reporting platform with a split runtime:
- `api/` (FastAPI): business logic, security, persistence
- `coyote/` (Flask): server-rendered UI consuming API endpoints

## Quick Start

1. Create env files from template:

```bash
cp example.env .coyote3_env
cp example.env .coyote3_dev_env
```

2. Build and run production-style stack:

```bash
./scripts/compose-with-version.sh up -d --build
```

3. Build and run development stack:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml up -d --build
```

4. Run DB identity migration after import/restore:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev
```

## Snapshot and Restore (Dev)

Create a mixed-assay snapshot (default 60 samples):

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-count 60
```

One-command snapshot + restore into dev DB:

```bash
scripts/snapshot_restore_dev.sh \
  --source-uri mongodb://localhost:5818 \
  --source-db coyote3 \
  --target-uri mongodb://localhost:37017 \
  --target-db coyote3_dev
```

## Ports and Runtime Config

Host ports are environment-driven in compose files:
- Prod: `COYOTE3_WEB_PORT`, `COYOTE3_API_PORT`, `COYOTE3_REDIS_PORT`, `COYOTE3_MONGO_PORT`
- Dev: `COYOTE3_DEV_WEB_PORT`, `COYOTE3_DEV_API_PORT`, `COYOTE3_DEV_REDIS_PORT`, `COYOTE3_DEV_MONGO_PORT`

Mongo connection config:
- Required: `MONGO_URI`

Build metadata is also env-driven:
- `COYOTE3_VERSION`, `GIT_COMMIT`, `BUILD_TIME`

You can set these in env files or override on command line.

## Documentation

Use the docs for full deployment, architecture, and operations details:
- [Developer Guide](docs/development/developer-guide.md)
- [Maintenance Guide](docs/development/maintenance-guide.md)
- [Dev to Staging to Prod Flow](docs/deployment/dev-staging-prod-flow.md)
- [Mongo Docker Dev Runtime](docs/deployment/mongo-docker-dev-runtime.md)
- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)

## License

Proprietary. See [LICENSE.txt](LICENSE.txt).

## Legal Notice

Copyright (c) 2026 Coyote3 Project Authors and Section for Molecular Diagnostics (SMD), Lund.
All rights reserved.
