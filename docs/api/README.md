# API integration

The Coyote3 API provides authenticated access to application resources and sample
ingestion workflows. Integration requirements include client authentication, route
permissions, and request validation. Input formats and MongoDB schemas are defined
in the [data reference](../reference/README.md).

## Connect an integration

1. Read [authentication](authentication.md) and arrange the permissions required
   for the intended operations.
2. Choose [direct HTTP workflows](routes-and-workflows.md) or the independent
   [Python HTTP client](../sdk/python-client.md). Remote clients do not need to import
   the application's internal core SDK.
3. For ingestion, prepare a [sample manifest](../reference/sample-manifest.md) and
   [input files](../reference/ingest-files/README.md), then follow the
   [ingestion API](sample-ingestion.md).
4. Follow [ingest job recovery](../operations/ingest-job-recovery.md) when a submitted
   job fails or its outcome is uncertain.

For a frontend integration, use [frontend API contracts](../development/frontend-api-contracts.md).
For installation rather than API use, follow [deployment](../deployment/README.md).

## Guides

| Guide | Use it to |
| --- | --- |
| [API Authentication](authentication.md) | Authenticate with sessions, bearer tokens, and supported credentials. |
| [Python HTTP client](../sdk/python-client.md) | Use typed resources, sample workflows, pagination and client errors. |
| [Frontend API contracts](../development/frontend-api-contracts.md) | Generate TypeScript types and compare them with a running API or backend revision. |
| [API routes and workflows](routes-and-workflows.md) | Follow request workflows and their route responsibilities. |
| [API route groups and visibility](route-groups.md) | Find route prefixes, API groups, and OpenAPI visibility rules. |
| [Individual resource fields](resource-fields.md) | Retrieve one permitted metadata key from a resource. |
| [Ingestion API](sample-ingestion.md) | Submit sample bundles, uploads, queued jobs, and updates. |
| [Collection imports and permissions](collection-imports.md) | Import collection documents with the required permissions. |
| [API versioning and compatibility](versioning-and-compatibility.md) | Check API compatibility and runtime support commitments. |
| [Raw ingest file contracts](../reference/ingest-files/README.md) | Prepare pipeline files before submitting a sample bundle. |

[Documentation home](../README.md)
