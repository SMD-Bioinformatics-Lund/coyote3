![Python 3.12+](https://img.shields.io/badge/python-3.12+-orange.svg)
![Flask](https://img.shields.io/badge/framework-Flask-indigo)
![MongoDB](https://img.shields.io/badge/database-MongoDB-brightgreen)
![Dockerized](https://img.shields.io/badge/docker-ready-blue)
![License](https://img.shields.io/badge/license-Proprietary-red)
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
| Web Framework     | Flask (Blueprint modules for each feature)      |
| Backend Database  | MongoDB (via PyMongo)                           |
| Authentication    | LDAP (via Flask-LDAP3-Login or custom binding)  |
| Frontend          | Jinja2 templates + Tailwind CSS                 |
| Permissions       | Role-Based Access Control (RBAC)                |
| Audit Logging     | Action/event logging for traceability           |

---

## Feature Modules

Each major functionality is organized into a Flask blueprint:

- `dna` – DNA variant search, filter, review
- `rna` – RNA fusion events
- `coverage` – Depth metrics by panel/sample
- `admin` – Users, roles, permissions
- `dashboard` – Case review summaries
- `profile` – User-specific data and logs
- `login` – LDAP auth and session handling
- `public` – Minimal open endpoints (optional)

---

## Configuration & Deployment

- Separate configuration profiles for **development**, **testing**, and **production**
- Environment variables or `.env` for secrets and LDAP/MongoDB endpoints
- Deployable via **Gunicorn**, **Docker**

Documentation for environment setup, deployment, and schema initialization is available in the `docs/` directory. (under construction)

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

© 2025 Section for Molecular Diagnostics (SMD), Lund.  
All rights reserved. Internal use only.

---

## Contact

For inquiries, feedback, or deployment support, please contact the SMD development team at Lund.

---

