# Coyote3 – Genomic Variant Interpretation and Reporting Platform

### Core Stack
![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-UI-000000?logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-47A248?logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)

### Domain and Governance
![Clinical Genomics](https://img.shields.io/badge/Domain-Clinical%20Genomics-6A5ACD)
![DNA Support](https://img.shields.io/badge/DNA-Supported-1E90FF)
![RNA Support](https://img.shields.io/badge/RNA-Supported-20B2AA)
![RBAC](https://img.shields.io/badge/Security-RBAC-darkgreen)
![Audit Logging](https://img.shields.io/badge/Audit-Enabled-2E8B57)
![License: Proprietary](https://img.shields.io/badge/License-Proprietary-8B0000?style=flat&logo=shield&logoColor=white)

Coyote3 is a secure, schema-driven platform for clinical genomics workflows:

- `api/` (FastAPI): business logic, contracts, security, persistence
- `coyote/` (Flask): server-rendered UI that consumes API endpoints

It supports variant interpretation, collaborative annotation, reporting, and governed access for molecular diagnostics workflows.

## Who Built Coyote3

Coyote3 is developed and maintained by the bioinformatics team at the **Section for Molecular Diagnostics (SMD), Lund**, in collaboration with clinical users.

## Core Capabilities

- DNA/RNA variant interpretation workflows
- assay and gene-list driven filtering
- report preview/save/version workflows
- role and permission management with deny overrides
- structured audit logging and operational traceability

## Quick Start

1. Create environment files:

```bash
cp example.env .coyote3_env
cp example.env .coyote3_dev_env
cp example.stage.env .coyote3_stage_env
```

2. Set build metadata (recommended for traceability):

```bash
export COYOTE3_VERSION="$(python3 coyote/__version__.py)"
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

3. Start production-style stack:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

4. Start development stack:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

5. Verify API health:

```bash
curl -f http://localhost:${COYOTE3_API_PORT:-5816}/api/v1/health
```

## DB Migration and Snapshot Commands

Run identity migration after importing/restoring data:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev
```

Create a mixed-assay snapshot:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-count 60
```

Restore snapshot into dev:

```bash
scripts/snapshot_restore_dev.sh \
  --source-uri mongodb://localhost:5818 \
  --source-db coyote3 \
  --target-uri mongodb://localhost:37017 \
  --target-db coyote3_dev
```

## Test and Quality Gates

Run full family coverage gates:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_family_coverage_gates.sh
```

Run full suite with coverage:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_tests_with_coverage.sh
```

## Runtime Configuration Summary

- Required DB connection: `MONGO_URI`
- Build trace tags: `COYOTE3_VERSION`, `GIT_COMMIT`, `BUILD_TIME`
- Host ports are environment-driven (`COYOTE3_*` and `COYOTE3_DEV_*` keys)
- Use separate env files and secrets for dev/staging/prod

## Documentation

Primary docs:

- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Developer Guide](docs/development/developer-guide.md)
- [Testing Guide](docs/testing/TESTING_GUIDE.md)
- [Dev to Staging to Prod Flow](docs/deployment/dev-staging-prod-flow.md)
- [Operations Manual](docs/deployment/operations.md)

## License

Proprietary. See [LICENSE.txt](LICENSE.txt).

## Legal Notice

Copyright (c) 2026 Coyote3 Project Authors and Section for Molecular Diagnostics (SMD), Lund.
All rights reserved.
