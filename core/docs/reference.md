# Core interface reference

| Import | Purpose |
| --- | --- |
| `coyote.__version__` | Installed core distribution version |
| `coyote.config.CenterConfiguration` | Explicit center-profile input |
| `coyote.config.configure_center` | Select the process-wide profile |
| `coyote.application.operations` | Supported application operations and host capabilities |
| `coyote.application.operations.inputs` | Typed operation inputs |
| `coyote.contracts.operations.OperationResult` | Portable mutation counts and identities |
| `coyote.domain.exceptions.AppError` | Application failure translated by a host |

The operations module exports `CoyoteApplication`, `ApplicationRuntime`,
`ApplicationServices`, typed results and reporting/resource-integrity
capabilities. Consult the callable's Google-style docstring for arguments,
units, return values and expected failures.

Internal services and domain helpers implement these operations; their module
paths do not automatically form a supported external API. Repository protocols
define the capabilities an adapter must implement. Adapter implementations must
preserve selection and transaction semantics, not just method names.

The distribution is named `coyote-core`; its Python import is `coyote`.
Its version is independent of the complete application's release version.

## Shared structural contracts

The separate `coyote-contracts` dependency owns sample manifest structure, YAML
normalization, database-version metadata and permitted resource response fields.
Import these directly from `coyote_contracts`; they require no clinical host or
database adapter. `coyote.contracts.schemas.samples.SamplesDoc` extends
`coyote_contracts.samples.SampleManifest` with center vocabulary, sequencing
policy, clinical filters and persistence fields. Clinical validation remains
mandatory in core workflows.

## Resource metadata retrieval

`CoyoteApplication.resources.query(resource, query)` applies current authentication,
resource permissions and exact assay/environment scope before invoking
`coyote.application.operations.resource_reads.ResourceReadRepository`. The host
supplies this database-independent port through
`ApplicationServices.resource_reads`. Portable request and response models live in
`coyote_contracts.retrieval`. The repository must apply scope before filtering,
aggregating or paging and must return only the declared safe metadata.
