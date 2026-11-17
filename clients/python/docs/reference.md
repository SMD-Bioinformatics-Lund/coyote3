# Client interface reference

| Import | Purpose |
| --- | --- |
| `coyote_pyclient.CoyoteClient` | Synchronous sessions and resources |
| `coyote_pyclient.AsyncCoyoteClient` | Asynchronous operations |
| `coyote_pyclient.models` | Client-owned response models |
| `coyote_pyclient.metadata` | Typed permitted metadata fields |
| `coyote_pyclient.errors` | Structured HTTP and local resource errors |

`CoyoteAPIError` retains status, request identity and safe server diagnostics.
Specialized exceptions include authentication, permission, missing-resource,
conflict, validation and rate-limit failures. `ResponseValidationError` indicates
a successful response that violates the client's response contract;
`ResourceNotLoadedError` indicates a local reference that needs refreshing.

The server's OpenAPI contract defines available HTTP endpoints. Fluent attributes
under `client.api` construct paths; they do not establish that an endpoint exists.

The distribution is `coyote-pyclient`; its namespace is `coyote_pyclient`.
Version ownership belongs to this project's metadata. See [usage](usage.md) for
pagination, asynchronous operations, reports and error handling.

## Metadata

`resource.meta` returns an immutable, permitted metadata snapshot. Its fields
are defined in `src/coyote_pyclient/metadata.py`:

| Model | Resource |
| --- | --- |
| `SampleMetadata` | Sample identity, assay context and ingestion state |
| `AssayMetadata` | Assay identity, supported analyses and expected files |
| `ConfigurationMetadata` | Applied configuration and analysis/report sections |
| `GroupMetadata` | Biological group and parent group |
| `DiagnosisMetadata` | Diagnosis identity and linked assays |
| `GeneListMetadata` | Gene-list identity, type and entry count |

Optional fields may be unavailable on a particular server. Refresh the resource
before relying on current metadata; permissions are checked on every request.
