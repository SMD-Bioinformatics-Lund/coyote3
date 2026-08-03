# Coyote3 Clinical Genomics Platform

This site explains how to install, operate, use, and extend Coyote3. The guides
follow the same path as the application: configure an assay, ingest a sample,
review findings, prepare a report, and preserve the resulting audit record.

!!! info "Start here"

    New installations should begin with the [Quickstart](start_here/quickstart.md).
    Clinical and technical readers who need an end-to-end explanation can use
    the [Application Manual](product/complete_application_manual.md).

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

## Choose a Starting Point

| Goal | Start here |
| --- | --- |
| Run Coyote3 locally | [Quickstart](start_here/quickstart.md) |
| Review a DNA or RNA sample | [Clinical Workflow](user_guide/clinical_workflow_guide.md) |
| Understand ASP, ASPC, ISGL, and samples | [Core Concepts](product/core_concepts.md) |
| Prepare a center deployment | [Center Deployment](operations/center_deployment_guide.md) |
| Configure environment and center files | [Configuration](start_here/configuration.md) |
| Integrate with the API | [API Organization](api/api_organization.md) |
| Develop or test the application | [Local Development](start_here/local_development.md) |
| Diagnose an operational problem | [Operational Troubleshooting](operations/troubleshooting.md) |

---

## Platform Topology

![Coyote3 Platform Topology](assets/diagrams/runtime_topology.svg)

---

## Interface Reference

The [Interface Visual Reference](product/interface_visual_reference.md) contains
sample-neutral screenshots of the login page, dashboard, sample list, assay
catalog, variant search, administration workspace, and contact page.

---

!!! tip "Troubleshooting"

    For an installed system, begin with the
    [Operations Troubleshooting Guide](operations/troubleshooting.md). For a
    local code or test failure, use the
    [Developer Troubleshooting Guide](developer/troubleshooting_guide.md).
