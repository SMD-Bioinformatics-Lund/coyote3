<img src="docs/assets/coyote4-logo.svg" alt="Coyote4" width="320">

<!-- badges:start -->

### Build and validation

[Quality Checks](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/quality.yml?query=branch%3Aapi) [Bootstrap and Ingest](https://github.com/SMD-Bioinformatics-Lund/coyote3/actions/workflows/bootstrap-and-ingest-check.yml?query=branch%3Aapi) ![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)

### Core Stack

![Python: 3.14.7](https://img.shields.io/badge/Python-3.14.7-3776AB?style=flat&logo=python&logoColor=white) ![API: FastAPI](https://img.shields.io/badge/API-FastAPI-009688?style=flat&logo=fastapi&logoColor=white) ![Contracts: Pydantic 2](https://img.shields.io/badge/Contracts-Pydantic%202-E92063?style=flat&logo=pydantic&logoColor=white) ![UI: React 19](https://img.shields.io/badge/UI-React%2019-087EA4?style=flat&logo=react&logoColor=white) ![Language: TypeScript](https://img.shields.io/badge/Language-TypeScript-3178C6?style=flat&logo=typescript&logoColor=white) ![Database: MongoDB](https://img.shields.io/badge/Database-MongoDB-47A248?style=flat&logo=mongodb&logoColor=white) ![Tasks: Celery](https://img.shields.io/badge/Tasks-Celery-37814A?style=flat&logo=celery&logoColor=white) ![Broker & Cache: Redis](https://img.shields.io/badge/Broker%20%26%20Cache-Redis-DC382D?style=flat&logo=redis&logoColor=white) ![Deploy: Docker Compose](https://img.shields.io/badge/Deploy-Docker%20Compose-2496ED?style=flat&logo=docker&logoColor=white) ![Build: Vite](https://img.shields.io/badge/Build-Vite-646CFF?style=flat&logo=vite&logoColor=white) ![Styles: Tailwind CSS](https://img.shields.io/badge/Styles-Tailwind%20CSS-06B6D4?style=flat&logo=tailwindcss&logoColor=white) ![Documentation: MkDocs](https://img.shields.io/badge/Documentation-MkDocs-624080?style=flat) ![Backend tests: pytest](https://img.shields.io/badge/Backend%20tests-pytest-0A9EDC?style=flat&logo=pytest&logoColor=white) ![Frontend tests: Vitest](https://img.shields.io/badge/Frontend%20tests-Vitest-6E9F18?style=flat&logo=vitest&logoColor=white) ![Browser tests: Playwright](https://img.shields.io/badge/Browser%20tests-Playwright-2EAD33?style=flat)

### Domain & Capabilities

![Domain: Clinical Genomics](https://img.shields.io/badge/Domain-Clinical%20Genomics-1F6FEB?style=flat) ![DNA: Supported](https://img.shields.io/badge/DNA-Supported-1E90FF?style=flat) ![RNA: Supported](https://img.shields.io/badge/RNA-Supported-20B2AA?style=flat) ![Analysis: Somatic & Germline](https://img.shields.io/badge/Analysis-Somatic%20%26%20Germline-8B5E3C?style=flat) ![Reports: Immutable Snapshots](https://img.shields.io/badge/Reports-Immutable%20Snapshots-6B5B95?style=flat)

### Security & Governance

![Security: Casbin RBAC](https://img.shields.io/badge/Security-Casbin%20RBAC-2E8B57?style=flat) ![Audit: Enabled](https://img.shields.io/badge/Audit-Enabled-2E8B57?style=flat)
<!-- badges:end -->

Coyote4 is a clinical genomics application for reviewing DNA and RNA findings,
recording interpretations and preparing reports. It is developed by the Section
for Molecular Diagnostics (SMD), Lund.

This branch contains the FastAPI and React application. The GitHub repository
remains named `coyote3`; the production version 3 application is maintained separately.

## Start here

| Your task | Guide |
| --- | --- |
| Review a sample and save its report | [Clinical review](docs/user-guide/clinical-review-workflow.md) |
| Configure an assay | [Assay setup](docs/administration/assay-setup.md#step-by-step-add-a-new-assay) |
| Try the application with synthetic data | [Local quickstart](docs/getting-started/local-quickstart.md) |
| Install at a center | [First installation](docs/deployment/first-installation.md) |
| Update an existing installation | [Upgrade procedure](docs/deployment/application-upgrades.md) |
| Submit data from a pipeline | [Sample ingestion](docs/api/sample-ingestion.md) |
| Work on the code | [Developer setup](docs/getting-started/developer-environment.md) |
| Investigate a problem | [Troubleshooting](docs/operations/troubleshooting.md) |

The [documentation home](docs/README.md) links to the remaining guides and references.
Follow one procedure for your task; references explain individual fields and settings.

## How the application fits together

The React interface calls the FastAPI API. Application and domain services live
in the `coyote` core package. MongoDB stores application, identity,
knowledgebase and BAM-service records in separately configured databases.
Celery workers process background jobs using Redis. `smd-reports` supplies the
HTML and PDF report templates; the report conclusion uses the reviewed sample comment.

An assay definition (ASP) describes the physical assay. Its configuration (ASPC)
controls analyses, filters and reporting for a diagnosis and environment. Optional
gene lists (ISGLs) narrow the gene scope. Query rules select findings; reporting
rules generate suggested wording. Saving a report preserves its files, selected
findings and configuration provenance.

See [application architecture](docs/architecture/application-architecture.md)
for component boundaries and [clinical concepts](docs/reference/clinical-concepts.md)
for resource definitions.

The packaging rationale is recorded in
[ADR 0004](docs/architecture/decisions/0004-installable-application-packages.md).

## Repository layout

| Directory | Contents |
| --- | --- |
| `core/` | Independent clinical core; importable code in `src/coyote/` |
| `api/` | FastAPI host, background tasks and installation catalogs; code in `src/coyote_api/` |
| `adapters/mongo/` | Independent MongoDB adapter; code in `src/coyote_mongo/` |
| `clients/python/` | Independent HTTP client |
| `frontend/` | React interface and frontend tests |
| `deploy/` | Compose definitions, environment examples and deployment configuration |
| `docker/` | Container build definitions and frontend proxy templates |
| [api/src/coyote_api/config/](api/src/coyote_api/config/) | Backend environment loading, settings, defaults and center configuration examples |
| `scripts/` | Maintained installation, operations and validation commands |
| [api/src/coyote_api/bootstrap/demo_data/clinical_workflows/](api/src/coyote_api/bootstrap/demo_data/clinical_workflows/) | Actual synthetic demo files: setup resources, raw inputs and manifests |
| `migrations_scripts/` | Supported version 2 and version 3 data converters |
| `tests/` | Backend tests and synthetic fixtures |
| `docs/` | Procedures and technical references |

Each Python project owns its `pyproject.toml`, `src/`, tests, docs, README,
changelog and license. The root is a virtual uv workspace. See
[editable development](docs/sdk/uv-development.md) for setup and reload commands.

Use [deployment requirements](docs/deployment/production-requirements.md) for
server prerequisites. Container images supply the API interpreter. Host deployment
helpers require Python 3.12 or later; the standard API development environment uses
Python 3.14.7. The optional MongoDB Compose services pin their own image version.

## Configuration

The backend configuration entry point is
[api/src/coyote_api/config/bootstrap.py](api/src/coyote_api/config/bootstrap.py).
It loads `.env` from `COYOTE4_RUNTIME_ROOT`, or the working directory when unset,
without overriding existing process environment variables. Settings are assembled
in [runtime_settings.py](api/src/coyote_api/config/runtime_settings.py).
The [backend settings assembler](api/src/coyote_api/config/backend.py) validates
and distributes package-specific inputs. Packages receive their own settings,
not the full backend runtime or unrelated secrets.
There is no root `config/` directory in the current layout.

Copy [the environment example](deploy/env/example.env) for each deployment and
set its connections, secrets, storage paths and public URL. Keep private environment
files outside Git. Optional tuning settings are listed in the
[environment reference](docs/deployment/configuration-reference.md).

Center-owned contact, vocabulary and report presentation files live in an external
reviewed configuration directory. Assays, gene lists, users and published rules
are database-backed resources managed through the application. See
[configuration ownership](docs/configuration/README.md).

## Contributing and licensing

Read [CONTRIBUTING.md](CONTRIBUTING.md) before making a change. Report reproducible
bugs in the [issue tracker](https://github.com/SMD-Bioinformatics-Lund/coyote3/issues)
with synthetic examples; do not include patient information or credentials.

The application and independent Python packages use [GNU GPL version 3 only](LICENSE.txt).
See [LICENSING.md](LICENSING.md)
for package boundaries, [COPYRIGHT.txt](COPYRIGHT.txt) for ownership and affiliation,
and [NOTICE.txt](NOTICE.txt) for additional notices.
Each deploying organization remains responsible for its clinical validation and approval.

Copyright holder and original developer: **Ram Nanduri**, affiliated with
**Sektion för molekylär diagnostik (SMD), Lund, Region Skåne, Sweden**.
Contributors: **Viktor Henmyr** and **Sailendra Pradhananga**.
