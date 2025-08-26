# Coyote3 – Overview

Coyote3 is a **Flask + MongoDB** web application for clinical/diagnostic genomic data analysis and reporting.
It provides secure, role‑based workflows for DNA variants, RNA fusions, CNVs, assay configuration, and auditing.

**Core pillars**  
- **Schema‑driven admin UI** for assays (ASP) and assay configs (ASPC) with versioning and print/export.  
- **RBAC (roles + fine‑grained permissions)** with decorators (`require("permission", min_role, min_level)`).  
- **Audit logging** for sensitive routes (`@log_action`) capturing who/what/when/where.  
- **Sample access control** (assay‑scoped) via decorators in `coyote/util/decorators/access.py`.  
- **Extensible data layer** via a central `MongoAdapter` with typed handlers in `coyote/db/`.  
- **Operational observability** via structured logging with daily rotation (`logging_setup.py`).

## Live Environments & URLs
This repository is environment‑agnostic. Typical setup:
- **Dev**: Docker Compose with Mongo & Redis (see `docker-compose.yml` and `example.env`).
- **Prod**: Gunicorn behind a reverse proxy; external MongoDB and optional LDAP server.

## Supported
- **Python**: defined in `pyproject.toml`  
- **MongoDB**: app data; optional **BAM_Service** auxiliary DB  
- **Redis**: cache backend (see `CACHE_REDIS_URL` in `.env`)  
- **LDAP**: optional SSO (see `coyote/services/auth/ldap.py`)

## Release cadence & support
Track changes in `CHANGELOG.md`. Deploy using Docker + Gunicorn with environment profiles from `config.py`.
