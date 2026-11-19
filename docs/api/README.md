# API integration

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

The API provides access to permitted application resources and sample-ingestion
workflows. Requests use the deployment's base path and the `/api/v1` prefix.

## Connect an integration

1. Arrange [authentication and permissions](authentication.md) for the required operations.
2. Use HTTP directly or the independent [Python client](../core/README.md#coyote-pyclient).
3. For pipeline ingestion, follow [Submit a sample](submit-sample.md), including its
   manifest, file validation and job-status checks.

## Explore the installed API

Open `/api/v1/docs` for the interactive explorer or `/api/v1/redoc` for the reference,
under the application's mounted base path. These pages describe the running API;
optional routes depend on the installed services. **OpenAPI JSON** provides the full
schema. See [route groups and visibility](route-groups.md) for access restrictions.

## References

| Subject | Guide |
| --- | --- |
| Requests and resource workflows | [Routes and workflows](routes-and-workflows.md) |
| Sample bundles, uploads and updates | [Ingestion API](sample-ingestion.md) |
| Allowed field queries | [Resource fields](resource-fields.md) |
| Collection imports | [Imports and permissions](collection-imports.md) |
| Pipeline input shapes | [File formats](../reference/ingest-files/README.md) |
| Version compatibility | [API versioning](versioning-and-compatibility.md) |
| Frontend type generation | [Frontend API contracts](../development/frontend-api-contracts.md) |
| Failed or uncertain ingestion | [Ingest job recovery](../operations/ingest-job-recovery.md) |
