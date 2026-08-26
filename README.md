# Coyote3

Coyote3 is a secure, schema-driven clinical genomics platform for
interpretation, triage, and reporting of DNA and RNA findings in governed
diagnostic workflows.

[![Quality Checks](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/quality.yml/badge.svg)](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/quality.yml)
![Coyote3 4.0.0](https://img.shields.io/badge/Coyote3-4.0.0-4F46A5)
![Python 3.12](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/API-FastAPI-009688?logo=fastapi&logoColor=white)
![Pydantic 2](https://img.shields.io/badge/Contracts-Pydantic%202-E92063?logo=pydantic&logoColor=white)
![React 19](https://img.shields.io/badge/UI-React%2019-087EA4?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?logo=typescript&logoColor=white)
![MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248?logo=mongodb&logoColor=white)
![Celery](https://img.shields.io/badge/Tasks-Celery-37814A?logo=celery&logoColor=white)
![Redis](https://img.shields.io/badge/Broker%20%26%20Cache-Redis-DC382D?logo=redis&logoColor=white)
![Docker Compose](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?logo=docker&logoColor=white)

![Clinical Genomics](https://img.shields.io/badge/Domain-Clinical%20Genomics-1F6FEB)
![DNA Support](https://img.shields.io/badge/DNA-Supported-1E90FF)
![RNA Support](https://img.shields.io/badge/RNA-Supported-20B2AA)
![Somatic and Germline](https://img.shields.io/badge/Analysis-Somatic%20%26%20Germline-8B5E3C)
![Report Snapshots](https://img.shields.io/badge/Reports-Immutable%20Snapshots-6B5B95)
![Casbin RBAC](https://img.shields.io/badge/Security-Casbin%20RBAC-2E8B57)
![Audit Logging](https://img.shields.io/badge/Audit-Enabled-2E8B57)
![License: Apache-2.0](https://img.shields.io/badge/License-Apache--2.0-2E7D32)

## Overview

Coyote3 brings sample ingestion, assay-aware filtering, finding review,
clinical annotation, and report generation into one traceable workspace. It is
designed for molecular diagnostics teams that require typed data contracts,
role- and scope-based access control, reproducible configuration, and an audit
record of significant clinical and administrative actions.

The application supports:

- DNA and RNA sample workflows;
- SNV, CNV, translocation, fusion, biomarker, and coverage review where enabled
  by the assay configuration;
- ASP, ASPC, and ISGL administration;
- somatic and germline SNV filtering with intent-specific rules;
- classifications, comments, finding actions, and cross-sample search;
- report preview and immutable saved report snapshots;
- public assay catalog and knowledgebase integrations;
- Casbin-backed permissions, scoped roles, audit events, and user notifications;
  and
- contract-validated background ingestion and operational maintenance.

## Architecture

| Component | Responsibility |
| --- | --- |
| `frontend/` | React interface, route workflows, shared tables, and API query state. |
| `api/` | FastAPI routes, application services, domain rules, contracts, authorization, and repositories. |
| Celery worker and Beat | Sample ingestion and scheduled maintenance. |
| MongoDB | Clinical findings, configuration, identity, audit, and operational records. |
| Redis | Task delivery, sessions, and non-clinical caches. |
| Reverse proxy | One public origin for the UI, API, public pages, and documentation. |

For the complete component and request flow, see
[Application Architecture](docs/architecture/current_application_context.md).

## Repository Layout

```text
api/                         FastAPI application and backend contracts
api/config/center/           Center-configurable TOML and YAML files
clinical_reporting_rules/    Versioned clinical report rule sources
frontend/                    React application and frontend tests
deploy/                      Compose, proxy, and container configuration
scripts/                     Bootstrap, quality, validation, and operations tools
docs/                        User, clinical, API, architecture, and operations guides
tests/                       Backend unit, API, integration, and contract tests
demo_data/                   Synthetic demonstration and ingest data
```

## Quick Start

### Prerequisites

- Git
- Docker with Docker Compose
- Python 3.12 or later for repository scripts and local quality checks
- MongoDB 8.2 or later when using an external database; the self-hosted stack
  uses the pinned `mongo:8.2` image

Create the development environment file:

```bash
cp deploy/env/example.env .coyote3_dev_env
```

Review the copied file and replace every `CHANGE_ME` value. Set `MONGO_URI` to
the MongoDB instance the containers should use, and configure the host data and
log roots for the local machine.

Start the development stack:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

The application always uses the MongoDB endpoint in `MONGO_URI`. It does not
start MongoDB, create a network, or join a database-specific Docker network.
The database may be host-installed, center-managed, or deployed independently
with Docker, provided that the URI is reachable from the application containers.

See [MongoDB deployment and recovery](docs/operations/mongodb_deployment_and_recovery.md)
for replica-set initialization, backups, and recovery testing.

The public application path is controlled by `SCRIPT_NAME`. With the example
development value `/coyote3_dev`, the standard endpoints are:

| Service | URL |
| --- | --- |
| Application | `http://localhost:6801/coyote3_dev/` |
| API documentation | `http://localhost:6801/coyote3_dev/api/v1/docs` |
| Documentation site | `http://localhost:6801/coyote3_dev/docs-site/` |
| Public catalog | `http://localhost:6801/coyote3_dev/public/catalog` |

For first deployment, baseline RBAC data, the initial superuser, demo
configuration, and synthetic sample ingestion, follow the
[Quickstart](docs/start_here/quickstart.md). Production deployments must follow
the [Initial Deployment Checklist](docs/operations/initial_deployment_checklist.md).

## Configuration Model

Coyote3 separates configuration by ownership:

- environment files hold deployment identity, secrets, public routing, service
  endpoints, and host mount paths;
- `api/config/center/` contains center-configurable clinical vocabulary,
  collection names, contact details, assay catalog text, filter metadata, and
  query policy;
- ASP, ASPC, and ISGL are versioned clinical configuration resources, while
  roles and users are managed as operational identity resources;
- `clinical_reporting_rules/` contains application-versioned clinical report
  rules; and
- fixed product behavior remains in Python and frontend theme configuration.

Start with the [Configuration Guide](docs/start_here/configuration.md) and
[Center Configuration Files](docs/operations/center_configuration_files.md).

## Documentation

| Reader or task | Documentation |
| --- | --- |
| First local run | [Quickstart](docs/start_here/quickstart.md) |
| Clinical use and administration | [Complete User Manual](docs/user_guide/complete_user_manual.md) |
| Clinical review | [Clinical Workflow](docs/user_guide/clinical_workflow_guide.md) |
| ASP, ASPC, ISGL, samples, and findings | [Core Concepts](docs/product/core_concepts.md) |
| System relationships | [System Overview](docs/product/complete_application_manual.md) |
| Center deployment | [Center Deployment Guide](docs/operations/center_deployment_guide.md) |
| Environment and secrets | [Environment and Secrets](docs/operations/environments_and_secrets.md) |
| Sample manifest and input contracts | [Sample YAML Manifest](docs/api/sample_yaml.md) and [Sample Input Files](docs/api/sample_input_files.md) |
| API organization and authentication | [API Organization](docs/api/api_organization.md) and [Authentication](docs/api/authentication.md) |
| Architecture | [Application Architecture](docs/architecture/current_application_context.md) |
| Development | [Complete Developer Manual](docs/developer/complete_developer_manual.md) |
| Testing and release checks | [Testing and Quality](docs/testing/testing_and_quality.md) |
| Operational troubleshooting | [Troubleshooting](docs/operations/troubleshooting.md) |

The documentation site is built with MkDocs. Its table of contents is defined
in `mkdocs.yml`.

## Development and Quality

Install the backend development dependencies and frontend packages using the
procedures in [Local Development](docs/start_here/local_development.md). Run the
complete repository quality suite with:

```bash
scripts/run_quality_suite.sh
```

The suite runs backend tests and coverage gates, strict Python typing, contract
checks, frontend lint and coverage, Playwright tests, the frontend production
build, and a strict documentation build. GitHub Actions selects the affected
backend, frontend, and documentation scopes for pull requests; default-branch
and manually dispatched runs retain backend XML and frontend LCOV coverage
artifacts for seven days.

Contributions must follow the [Contributing Guide](docs/project/contributing.md)
and [Engineering and Refactoring Standards](docs/maintainers/refactor_guidelines.md).

## Security and Clinical Use

- Never commit environment files, credentials, tokens, patient information, or
  real sample identifiers.
- Clinical and administrative writes are validated through typed contracts and
  explicit permissions.
- Internal endpoints are not part of the supported public OpenAPI contract and
  remain protected independently of documentation visibility.
- Each deploying organization is responsible for local validation, clinical
  governance, access policy, infrastructure security, and regulatory approval.

See the [Security Model](docs/architecture/security_model.md),
[Governance](docs/project/governance.md), and [NOTICE](NOTICE.txt) before using
the software in a clinical environment.

## Project and License

Coyote3 is developed and maintained by the bioinformatics team at the
**Section for Molecular Diagnostics (SMD), Lund**, in collaboration with
clinical users and platform maintainers.

Licensed under the [Apache License 2.0](LICENSE.txt). Clinical-use and
deployment responsibilities are described in [NOTICE.txt](NOTICE.txt).
