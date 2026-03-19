# Coyote3 – Genomic Variant Interpretation and Reporting Platform

### Core Stack
![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-Backend-009688?logo=fastapi&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-UI-000000?logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-47A248?logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?logo=docker&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-4.1.12-38BDF8?logo=tailwindcss&logoColor=white)

### Domain and Governance
![Clinical Genomics](https://img.shields.io/badge/Domain-Clinical%20Genomics-6A5ACD)
![DNA Support](https://img.shields.io/badge/DNA-Supported-1E90FF)
![RNA Support](https://img.shields.io/badge/RNA-Supported-20B2AA)
![Schema Driven](https://img.shields.io/badge/Architecture-Schema%20Driven-708090)
![RBAC](https://img.shields.io/badge/Security-RBAC-darkgreen)
![Audit Logging](https://img.shields.io/badge/Audit-Enabled-2E8B57)

### Status and Release
![Status](https://img.shields.io/badge/Status-Production%20%7C%20Active%20Development-blue)
![Version](https://img.shields.io/github/v/release/SMD-Bioinformatics-Lund/coyote3?label=version&logo=github)
![License: Proprietary](https://img.shields.io/badge/License-Proprietary-8B0000?style=flat&logo=shield&logoColor=white)

## Overview

Coyote3 is a secure, scalable, and extensible application for genomic variant interpretation, operational data management, and clinical reporting. The platform supports DNA and RNA diagnostic workflows in one governed runtime.

Coyote3 is engineered for molecular diagnostics environments that require:

- secure and auditable access to sensitive case and variant data
- reproducible assay-driven workflows
- role and permission controlled review and reporting
- extensibility for new assays, schemas, and interpretation rules

## Purpose

Coyote3 addresses clinical genomics workflow complexity by centralizing:

- sample and variant review
- annotation and classification decisions
- report preview, persistence, and traceability
- policy-controlled access and audit visibility

## Who Built It

Coyote3 is developed and maintained by the bioinformatics team at the **Section for Molecular Diagnostics (SMD), Lund**, in collaboration with clinical users.

## Core Capabilities

### Variant Interpretation
- Centralized views for DNA, RNA, CNVs, translocations, and fusions
- Assay-specific filtering and gene-list controls
- Classification, false-positive, irrelevant, and blacklist actions

### Data Management and Reporting
- Sample metadata, panel settings, and variant lifecycle tracking
- Report preview/save/history workflows
- Export and operational support tooling for migration/snapshot flows

### Identity and Access Management
- Session-based auth with internal policy enforcement
- Role and permission model with deny overrides
- Structured audit events for operational traceability

### Dashboards and Oversight
- Assay-level and platform-level summaries
- Sample and variant activity metrics
- Operational diagnostics through API/UI logs

## Architecture

Coyote3 runs as a split application:

| Layer | Technology / Pattern |
|---|---|
| UI Runtime | Flask (`coyote/blueprints`) |
| API Runtime | FastAPI (`api/routers`, `api/services`, `api/core`) |
| Persistence | MongoDB via repository/handler layers |
| Cache | Redis |
| Frontend | Jinja2 templates + Tailwind CSS |
| Access Control | RBAC + permission checks |
| Audit | Structured audit logging |

## Feature Modules

Major functionality is organized into route families and blueprints:

- `home` – landing workflows and samples navigation
- `dna` – small variants, CNVs, translocations, findings, reports
- `rna` – fusion and RNA findings/report flows
- `coverage` – coverage and blacklist workflows
- `admin` – users, roles, permissions, schemas, assay configs, logs
- `docs` – in-app handbook and metadata pages
- `public` – bounded public/catalog endpoints
- `common` – shared utility flows across route families

## Installation and Deployment

Production-style compose is the default deployment path. Development compose is the secondary path for active coding.

### 1. Prerequisites

Install and verify:

```bash
git --version
docker --version
docker compose version
python3 --version
```

### 2. Clone Repository

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3
```

### 3. Configure Environment Files

```bash
cp example.prod.env .coyote3_env
cp example.dev.env .coyote3_dev_env
cp example.stage.env .coyote3_stage_env
```

Set real values for secrets, Mongo credentials, and URIs per environment.
Use dedicated Mongo instances/users per environment (`prod`, `stage`, `dev`).

### 4. Build Metadata (Recommended)

```bash
export COYOTE3_VERSION="$(python3 coyote/__version__.py)"
export GIT_COMMIT="$(git rev-parse --short HEAD)"
export BUILD_TIME="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
```

### 5. Production-Style Deployment

Recommended:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

Alternative helper script:

```bash
./scripts/install.sh
```

### 6. Development Deployment

Recommended:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

Alternative helper script:

```bash
./scripts/install.dev.sh
```

### 7. Staging Deployment

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_stage_env \
  -f deploy/compose/docker-compose.stage.yml \
  up -d --build
```

### 7. Verify Runtime Health

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml ps
curl -f http://localhost:${COYOTE3_API_PORT:-5816}/api/v1/health
```

### 8. Stop Services

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml down
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml down
```

## Database Migration and Snapshot Operations

Run identity migration after restore/import:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/migrate_db_identity.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev
```

Create mixed-assay snapshot:

```bash
/home/ram/.virtualenvs/coyote3/bin/python scripts/create_mongo_snapshot.py \
  --mongo-uri mongodb://localhost:37017 \
  --db coyote3_dev \
  --sample-count 60
```

Snapshot restore helper:

```bash
scripts/snapshot_restore_dev.sh \
  --source-uri mongodb://localhost:5818 \
  --source-db coyote3 \
  --target-uri mongodb://localhost:37017 \
  --target-db coyote3_dev
```

## In-App Handbook Routes

Handbook blueprint routes:

- `/handbook/`
- `/handbook/about`
- `/handbook/changelog`
- `/handbook/license`
- `/handbook/<path-to-doc>.md`

Docs are rendered from repository markdown under `docs/`.

## Static Docs (MkDocs)

```bash
pip install -r requirements-docs.txt
mkdocs serve
mkdocs build
```

## Frontend CSS Build (Tailwind)

Input source:

- `coyote/static/css/tailwind.input.css`
- `tailwind.config.js`

Generated output used by templates:

- `coyote/static/css/tailwind.css`

Install frontend dependencies:

```bash
npm install
```

Build CSS once:

```bash
npm run build:css
```

Run continuous watch build:

```bash
npm run dev:css
```

Compose behavior:

- dev compose includes `coyote3_dev_tailwind` service for live CSS rebuilds
- production-style image build uses compiled CSS in runtime image

## Test and Quality Gates

Run family coverage gates:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_family_coverage_gates.sh
```

Run full suite with coverage:

```bash
PYTHON_BIN=/home/ram/.virtualenvs/coyote3/bin/python bash scripts/run_tests_with_coverage.sh
```

## Security and Compliance

- RBAC and permission checks on protected routes
- Structured audit event emission for critical actions
- Environment-scoped secrets and runtime config
- Deployment and rollback runbooks under `docs/deployment/`

## Extensibility

Coyote3 supports extension through:

- schema-driven admin resources
- assay-specific configuration workflows
- repository/service contract boundaries in API runtime
- route-family based UI/API implementation guides

## Documentation

Primary references:

- [Architecture Overview](docs/ARCHITECTURE_OVERVIEW.md)
- [Developer Guide](docs/development/developer-guide.md)
- [Testing Guide](docs/testing/TESTING_GUIDE.md)
- [Dev to Staging to Prod Flow](docs/deployment/dev-staging-prod-flow.md)
- [Operations Manual](docs/deployment/operations.md)

## License

Proprietary. See [LICENSE.txt](LICENSE.txt).

## Contact

For deployment and workflow support, contact the SMD Coyote3 maintainers.

## Legal Notice

Copyright (c) 2026 Coyote3 Project Authors and Section for Molecular Diagnostics (SMD), Lund.
All rights reserved.
