# Coyote3

Coyote3 is a secure, schema-driven clinical genomics platform for interpretation, triage, and reporting of DNA and RNA findings in governed diagnostic workflows.

## Status

[![Quality Checks](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/quality.yml/badge.svg)](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/quality.yml)

## Platform

![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Flask](https://img.shields.io/badge/Web-Flask-000000?logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248?logo=mongodb&logoColor=white)
![Redis](https://img.shields.io/badge/Cache-Redis-DC382D?logo=redis&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white)

## Domain and Governance

![Clinical Genomics](https://img.shields.io/badge/Domain-Clinical%20Genomics-1F6FEB)
![DNA Support](https://img.shields.io/badge/DNA-Supported-1E90FF)
![RNA Support](https://img.shields.io/badge/RNA-Supported-20B2AA)
![RBAC](https://img.shields.io/badge/Security-RBAC-2E8B57)
![Audit Logging](https://img.shields.io/badge/Audit-Enabled-2E8B57)
![License: Proprietary](https://img.shields.io/badge/License-Proprietary-8B0000)

## What It Is

Coyote3 is split into two runtime applications:

- `api/` FastAPI backend for business logic, contracts, security, and persistence operations
- `coyote/` Flask web application for user workflows and management UI, consuming API endpoints

It is designed for molecular diagnostics teams that need traceability, policy-driven behavior, and role-based access across interpretation and reporting flows.

## Who Can Use It

- Molecular diagnostics and clinical genomics teams
- Bioinformatics teams operating interpretation/reporting pipelines
- Clinical lab operations teams managing assays, configurations, and governed user access
- Developers and maintainers extending domain logic, API contracts, and operations tooling

## Core Capabilities

- DNA and RNA variant interpretation workflows in one platform
- Assay and gene-list driven filtering and interpretation configuration
- Variant and structural finding review flows (SNV, CNV, translocation, fusion)
- Report preview, save, version-aware update flows, and controlled reporting outputs
- Internal ingestion APIs with contract-backed validation (Pydantic)
- Role and permission management with explicit policy boundaries and deny control support
- Structured audit-aware operations and deployment checks

## Who Developed It

Coyote3 is developed and maintained by the bioinformatics team at the **Section for Molecular Diagnostics (SMD), Lund**, in collaboration with clinical users and platform maintainers.

## Why Teams Use It

- One operational platform instead of separate ad hoc tools for interpretation and reporting
- Contract-first data handling to reduce schema drift across environments
- Center-operable deployment model with explicit environment templates and operational checks
- Clear separation between UI workflows and API domain logic

## Project Structure

- `api/` backend services, contracts, routers, handlers, and security
- `coyote/` Flask UI blueprints, templates, and web-side API client
- `deploy/` Docker Compose stacks and deployment assets
- `scripts/` bootstrap, ingest, validation, and operations scripts
- `docs/` full project, architecture, API, operations, and testing documentation
- `tests/` unit, API, integration, and UI boundary tests

## Quick Start

1. Create environment files from templates:

```bash
cp deploy/env/example.prod.env .coyote3_env
cp deploy/env/example.dev.env .coyote3_dev_env
cp deploy/env/example.stage.env .coyote3_stage_env
cp deploy/env/example.test.env .coyote3_test_env
```

2. Set real secret values in the env files (`SECRET_KEY`, `INTERNAL_API_TOKEN`, `PASSWORD_TOKEN_SALT`, Mongo credentials).

3. Start development stack:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

4. Verify API health:

```bash
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_DEV_API_PORT:-6802}/api/v1/health"
```

5. For first-time center setup, use:

```bash
scripts/center_first_run.sh --help
```

## Deployment Profiles

Coyote3 ships with four standard environment profiles:

- `prod` using `.coyote3_env`
- `stage` using `.coyote3_stage_env`
- `dev` using `.coyote3_dev_env`
- `test` using `.coyote3_test_env`

Compose definitions live in `deploy/compose/`, and environment templates live in `deploy/env/`.

Optional deployment profile:

- `with-proxy` profile adds an Nginx reverse proxy for single-entry routing (`/`, `/api/`, `/docs-site/`).

## Data And Configuration Model

- Runtime behavior is driven by typed contracts in `api/contracts/`.
- Collection ingest and updates are validated through Pydantic-backed normalization.
- Assay and list configuration is managed through ASP/ASPC/ISGL resources.
- Governance is enforced through roles, permissions, and auditable internal operations.

## Development And Contribution

- Main project standards and contribution expectations: [Contributing](docs/project/contributing.md)
- Architecture orientation: [Codebase Map](docs/architecture/codebase-map.md)
- Feature development path: [Add New Feature](docs/developer/adding-features.md)
- Quality gates and test strategy: [Testing And Quality](docs/testing/testing-and-quality.md)

## Documentation

- Start here: [Quickstart](docs/start-here/quickstart.md)
- Configuration model: [Configuration](docs/start-here/configuration.md)
- Architecture: [System Overview](docs/architecture/system-overview.md)
- API ingestion and contracts:
  - [Ingestion API](docs/api/ingestion-api.md)
  - [Collection Contracts](docs/api/collection_contracts.md)
- Operations:
  - [Center Deployment Guide](docs/operations/center-deployment-guide.md)
  - [Deployment Guide](docs/operations/deployment-guide.md)
  - [Initial Deployment Checklist](docs/operations/initial-deployment-checklist.md)
- Testing and quality: [Testing And Quality](docs/testing/testing-and-quality.md)

## Security and Compliance Notes

- Production deployment expects explicit secrets and controlled environment files.
- Internal ingest and management operations are protected by role/permission checks.
- Data operations are validated against typed contracts before persistence.
- API internal metrics endpoint: `/api/v1/internal/metrics` (requires `X-Internal-Token`).

## License

Proprietary. See [LICENSE.txt](LICENSE.txt).
