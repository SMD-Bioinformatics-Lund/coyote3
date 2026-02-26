### Core Stack
![Python 3.12+](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-Framework-000000?logo=flask&logoColor=white)
![MongoDB](https://img.shields.io/badge/MongoDB-Database-47A248?logo=mongodb&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker&logoColor=white)
![Tailwind CSS](https://img.shields.io/badge/Tailwind%20CSS-4.1.12-38BDF8?logo=tailwindcss&logoColor=white)
### Domain & Capabilities
![Clinical Genomics](https://img.shields.io/badge/Domain-Clinical%20Genomics-6A5ACD)
![DNA Support](https://img.shields.io/badge/DNA-Supported-1E90FF)
![RNA Support](https://img.shields.io/badge/RNA-Supported-20B2AA)
![Schema Driven](https://img.shields.io/badge/Architecture-Schema%20Driven-708090)
### Security & Governance
![RBAC Enabled](https://img.shields.io/badge/Security-RBAC%20Enabled-darkgreen)
![Audit Logging](https://img.shields.io/badge/Audit-Logging%20Enabled-2E8B57)
### Status & Release
![Status](https://img.shields.io/badge/Status-Production%20%7C%20Active%20Development-blue)
![Version](https://img.shields.io/github/v/release/SMD-Bioinformatics-Lund/coyote3?label=version&logo=github)
![License: Proprietary](https://img.shields.io/badge/License-Proprietary-8B0000?style=flat&logo=shield&logoColor=white)

# Coyote3 – Genomic Variant Interpretation & Reporting Platform

**Coyote3** is a secure, scalable, and extensible web application designed as a one-stop solution for **genomic variant interpretation**, **data management**, and **clinical reporting**. Built by the **Section for Molecular Diagnostics (SMD), Lund**, Coyote3 streamlines complex diagnostics workflows into a unified interface for clinical geneticists, bioinformaticians, and laboratory personnel.

---

## Overview

Coyote3 serves as a comprehensive platform for managing and interpreting DNA and RNA variant data within a clinical diagnostics context. It supports detailed analysis, collaborative review, and permission-controlled access to variant annotations, assay configurations, and reporting assets.

Coyote3 is engineered to meet the needs of modern molecular diagnostics laboratories by offering:

- Secure and auditable access to variant data
- Seamless integration with existing directory (LDAP) and storage systems (MongoDB)
- Role-based workflows supporting multiple user groups
- Extensible architecture tailored to evolving diagnostic pipelines

---

## Purpose

Coyote3 was developed to address the growing complexity and regulatory requirements in **clinical genomics**, particularly:

- Ensuring secure, traceable access to sensitive patient-derived variant data
- Supporting multi-assay, multi-user workflows across DNA and RNA pipelines
- Centralizing variant review, interpretation, and reporting in one application
- Allowing dynamic adaptation to different diagnostic panels, rules, and labs

---

## Who Built It?

Coyote3 is developed and maintained by the bioinformaticians at **Section for Molecular Diagnostics (SMD)**, **Lund**, in close collaboration with clinical geneticists. The system is in active use for diagnostics casework, variant interpretation, and report creation.

---

## Core Capabilities

### Variant Interpretation
- Centralized views for DNA, RNA, CNVs, and fusions
- Assay-specific panel and gene filtering
- Clinical-grade annotations and classification workflows

### Data Management & Reporting
- Sample metadata, gene panels, and variant tracking
- Per-assay default configurations for filtering and quality
- Exportable reports for review boards and clinicians

### Identity & Access Management
- LDAP authentication with organizational group sync
- Role- and group-based permissions (admin, user, reviewer)
- Audit trail of changes and logins

### Dashboards & Oversight
- Assay-level summaries and quality metrics
- Sample and variant statistics by panel or user group
- Custom dashboards for reviewers or leads

---

## Architecture

Coyote3 is built using Python’s **Flask** web framework and structured with a **modular blueprint-based architecture**.

| Layer            | Technology / Pattern                            |
|------------------|--------------------------------------------------|
| Web Runtime       | Flask + Jinja (`coyote3_web`)                   |
| API Runtime       | FastAPI ASGI (`coyote3_api`)                    |
| Backend Database  | MongoDB (via PyMongo)                           |
| Authentication    | LDAP (via Flask-LDAP3-Login or custom binding)  |
| Frontend          | Jinja2 templates + Tailwind CSS                 |
| Permissions       | Role-Based Access Control (RBAC)                |
| Audit Logging     | Action/event logging for traceability           |

---

## Feature Modules

Each major functionality is organized into a Flask blueprint:

- `home` – Landing page and samples dashboard
- `dna` – DNA variant search, filter, review
- `rna` – RNA fusion events
- `coverage` – Depth metrics by panel/sample
- `admin` – Users, roles, permissions
- `dashboard` – Case review summaries
- `profile` – User-specific profile and account operations
- `login` – LDAP auth and session handling
- `public` – Minimal open endpoints (optional)
- `common` – Shared comments, search, and cross-workflow utilities
- `docs` – In-app handbook and release information

---

## Installation and Deployment

Production is the default and recommended path. Development options are listed after production.

### 1. Prerequisites

Install and verify:

```bash
git --version
docker --version
docker compose version
python3 --version
```

### 2. Clone repository

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3
```

### 3. Configure environment files

Production env file:

```bash
cp example.env .coyote3_env
```

Development env file:

```bash
cp example.env .coyote3_dev_env
```

Update values in `.coyote3_env` / `.coyote3_dev_env` (at minimum):

- `SECRET_KEY`
- `COYOTE3_FERNET_KEY`
- `FLASK_MONGO_HOST`
- `FLASK_MONGO_PORT`
- `COYOTE3_DB_NAME`
- `CACHE_REDIS_URL`
- `CACHE_REDIS_HOST`
- `REPORTS_BASE_PATH`
- `APP_DNS`
- `PORT_NBR`
- `GENS_URI`
- `IGV_URI`

### 4. Production install and deploy (recommended)

Option A: compose wrapper (recommended)

```bash
./scripts/compose-with-version.sh up -d --build
```

Option B: scripted wrapper

```bash
./scripts/install.sh
```

### 5. Verify production deployment

```bash
./scripts/compose-with-version.sh ps
./scripts/compose-with-version.sh logs --tail=100 coyote3_web
./scripts/compose-with-version.sh logs --tail=100 coyote3_api
```

Open:

- App: `/`
- Handbook: `/handbook`

### 6. Development deploy (secondary)

Option A: compose wrapper

```bash
./scripts/compose-with-version.sh -f docker-compose.dev.yml up -d --build
```

Option B: scripted wrapper

```bash
./scripts/install.dev.sh
```

### 7. Direct compose (manual version export)

```bash
export COYOTE3_VERSION="$(python3 coyote/__version__.py)"
docker compose up -d --build
docker compose -f docker-compose.dev.yml up -d --build
```

### 8. Stop services

```bash
./scripts/compose-with-version.sh down
./scripts/compose-with-version.sh -f docker-compose.dev.yml down
```

Documentation for setup, operations, user workflows, and developer internals is maintained in `docs/handbook/`.

### In-app handbook routes

- Handbook home: `/handbook`
- Handbook page renderer: `/handbook/<path-to-markdown>.md`
- About page: `/handbook/about`
- Changelog: `/handbook/changelog`
- License: `/handbook/license`

The in-app handbook renders markdown directly from `docs/handbook/`.

### Static docs site (MkDocs, ReadTheDocs theme)

MkDocs configuration lives in `mkdocs.yml`.

Run locally:

```bash
pip install -r requirements-docs.txt
mkdocs serve
```

Build static site:

```bash
mkdocs build
```

---

## Frontend CSS build (Tailwind via npm)

Tailwind is compiled locally from source instead of using a CDN stylesheet.

Input source:

- `coyote/static/css/tailwind.input.css`
- `tailwind.config.js`

Generated output used by templates:

- `coyote/static/css/tailwind.css`

Tailwind scans templates/source files and generates only the classes used by the application. Custom project color aliases (for example `brown` and `olive`) are defined once in `tailwind.config.js` and full shade scales are generated automatically.

Install frontend build dependencies:

```bash
npm install
```

Build CSS once:

```bash
npm run build:css
```

Run continuous CSS build in development:

```bash
npm run dev:css
```

Keep `npm run dev:css` running while editing templates/styles so the generated CSS stays up to date.

`package.json` version is auto-synced from `coyote/__version__.py` by:

- `scripts/sync-package-version.js`
- `npm install` (via `postinstall`)
- `npm run build:css` / `npm run dev:css` (via pre-scripts)

### Docker/Compose behavior

- Production image build (`Dockerfile`) compiles Tailwind CSS during image build.
- Development app image (`Dockerfile.dev`) does not compile Tailwind during build.
- `docker-compose.dev.yml` includes a dedicated `coyote3_dev_tailwind` service that installs npm dependencies, builds CSS, and continuously rebuilds CSS (`npm run dev:css`) while developing.
- Compose image tags use `COYOTE3_VERSION` instead of hardcoded values.
- Use `./scripts/compose-with-version.sh up -d` to run compose with `COYOTE3_VERSION` exported from `coyote/__version__.py`.

---

## Security & Compliance

- Fine-grained permissions enforced by custom RBAC middleware
- LDAP-based identity binding and group mapping
- Full audit logging of user logins, data changes, and role escalations
- Access isolation between diagnostic groups or hospital units

---

## Extensibility

Coyote3 is architected to support lab-specific workflows and pipelines:

- **Custom assay configuration UI**
- **Dynamic filtering and gene set expansion**
- **Extendable role definitions and permission schemes**
- **Schema-aware editing of variant data and QC thresholds**

---

## License

© 2026 Section for Molecular Diagnostics (SMD), Lund.
All rights reserved. Internal use only.

---

## Contact

For inquiries, feedback, or deployment support, please contact the SMD development team at Lund.

---
