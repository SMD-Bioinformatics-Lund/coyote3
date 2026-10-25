# API integration

The Coyote3 API provides authenticated access to application resources and sample
ingestion workflows. Integration requirements include client authentication, route
permissions, and request validation. Input formats and MongoDB schemas are defined
in the [data reference](../reference/README.md).

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
