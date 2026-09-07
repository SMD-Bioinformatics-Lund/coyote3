# Coyote3 Clinical Genomics Platform

This is the public, authoritative documentation for Coyote3. It covers clinical
use, administration, deployment, data contracts, APIs, and engineering. The
site is organised by the work being done: start, use, administer, reference,
develop, operate, and validate.

> **Info: Start here**
>
>
> New production installations should follow
> [Production deployment](start_here/production_deployment.md). Developers
> evaluating Coyote3 locally should begin with the
> [Quickstart](start_here/quickstart.md).
> Clinical users should use the
> [complete user manual](user_guide/complete_user_manual.md). Developers and
> maintainers should use the
> [complete developer manual](developer/complete_developer_manual.md).
>

---

## What Coyote3 Does

Coyote3 supports the clinical genomics workflow from validated analysis output
to a saved report. It provides:

- assay-aware sample ingestion and readiness checks;
- separate DNA and RNA review workflows;
- server-side filtering, sorting, tiering, comments, and finding actions;
- report previews and immutable saved report snapshots;
- role- and scope-based access control;
- audit records for clinically and operationally significant actions; and
- administration of assays, configurations, gene lists, users, and runtime controls.

---

## Runtime Architecture

The platform separates browser, API, background, and persistence responsibilities:

- **React frontend** presents clinical and administrative workflows.
- **FastAPI service** validates requests, enforces authorization, and coordinates domain services.
- **Celery workers and scheduler** run ingestion and maintenance work.
- **MongoDB** stores clinical, configuration, identity, audit, and operational documents.
- **Redis** supports background task delivery, sessions, and non-clinical caching.
- **Reverse proxy** exposes the UI, API, and documentation through one public origin.

---

## Find the right guide

| Goal | Start here |
| --- | --- |
| Run Coyote3 locally | [Quickstart](start_here/quickstart.md) |
| Install or update production | [Production deployment](start_here/production_deployment.md) |
| Use the application | [Complete user manual](user_guide/complete_user_manual.md) |
| Review a DNA or RNA sample | [Clinical Workflow](user_guide/clinical_workflow_guide.md) |
| Understand ASP, ASPC, ISGL, and samples | [Core Concepts](product/core_concepts.md) |
| Prepare a center deployment | [Center Deployment](operations/center_deployment_guide.md) |
| Configure environment and center files | [Configuration](start_here/configuration.md) |
| Integrate with the API | [API Organization](api/api_organization.md) |
| Develop or test the application | [Complete developer manual](developer/complete_developer_manual.md) |
| Diagnose an operational problem | [Operational Troubleshooting](operations/troubleshooting.md) |

### Use Coyote3

Read the [complete user manual](user_guide/complete_user_manual.md) first,
then use the DNA, RNA, coverage, report, and table-reference guides while
working. These pages describe user-visible behaviour and the meaning of
clinical controls; they do not require knowledge of implementation details.

### Administer and operate Coyote3

For a new centre, follow [first installation](start_here/first_installation.md)
and [production deployment](start_here/production_deployment.md) in order.
Use the [management guide](user_guide/management_guide.md) to administer
users, roles, permissions, ASPs, ASPCs, ISGLs, and application controls. The
operations section is the reference for configuration, backup, recovery,
monitoring, and incident response.

### Develop Coyote3

Start with the [complete developer manual](developer/complete_developer_manual.md).
It defines the repository boundaries, contracts, test expectations, and change
process. The architecture, API, generated collection-contract, and testing
sections provide the detailed technical reference.

## Reference pages

The manuals explain workflows. The [reference guide](reference/index.md)
collects the canonical pages for configuration keys, collection fields, API
routes, and rule grammar. It is shared by clinical users, administrators, and
developers, while each audience keeps a separate workflow guide.

The following pages define the most commonly used reference material:

| Subject | Authoritative reference |
| --- | --- |
| Installation and center configuration | [Configuration](start_here/configuration.md) |
| ASP, ASPC, ISGL, and sample relationships | [Core Concepts](product/core_concepts.md) |
| DNA and RNA ingest manifests | [Sample YAML specification](api/sample_yaml.md) |
| Clinical reporting rules | [Clinical Reporting Rules](product/clinical_reporting_rules.md) |
| Collection fields and validation | [Generated Collection Contracts](api/collection_contracts.md) |
| Authentication and authorization | [Security Model](architecture/security_model.md) |
| Deployment and reverse proxy topology | [Deployment Guide](operations/deployment_guide.md) |
| Release evidence and required checks | [Release Readiness](operations/release_readiness.md) |

The collection-contract page is generated from Pydantic schemas. Change the
schema and regenerate the reference rather than editing that page directly.

---

## Platform Topology

![Coyote3 Platform Topology](assets/diagrams/runtime_topology.svg)

---

## Interface Reference

The [Interface Visual Reference](product/interface_visual_reference.md) contains
sample-neutral screenshots of the login page, dashboard, sample list, assay
catalog, variant search, administration workspace, and contact page.

---

> **Tip: Troubleshooting**
>
>
> For an installed system, begin with the
> [Operations Troubleshooting Guide](operations/troubleshooting.md). For a
> local code or test failure, use the
> [Developer Troubleshooting Guide](developer/troubleshooting_guide.md).
