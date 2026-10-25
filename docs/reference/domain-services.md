# Application domains and services

This reference maps capabilities to their owning packages and resources. Use the
[application guide](../user-guide/application-guide.md) for clinical tasks and the
[architecture guide](../architecture/application-architecture.md) for dependency boundaries.

## 1. Primary sample domain

The `samples` document is the main record for a case. Most findings collections link back to the sample through `SAMPLE_ID`.

### Operational component mapping

| Identifier | Collection | Primary Key | Operational Scoping |
|---|---|---|---|
| **ASP** | `assay_specific_panels` | `asp_id` | Enforces the physical gene universe and assay metrics. |
| **ASPC** | `asp_configs` | `aspc_id` | Enforces assay/diagnosis/environment filtering and reporting strategies. |
| **ISGL** | `insilico_genelists` | `isgl_id` | Provides curated clinical gene cohorts for interpretation. |

### Resource identification and uniqueness

Administrative resources use stable business IDs for routing and lookup.

| Resource Type | ID Attribute | Specification | Constraint |
|---|---|---|---|
| **User** | `username` | Login identifier. | Unique within the configured identity database. |
| **Role** | `role_id` | Functional slug, such as `viewer` or `admin`. | Unique within the configured identity database. |
| **Permission** | `permission_id` | `resource:action[:scope]` key, such as `sample:edit:global`. | Unique within the configured identity database. |
| **ASP** | `asp_id` | Assay identifier mapped to `sample.asp_id`. | Identifier plus `version` identifies a stored revision. |
| **ASPC** | `aspc_id` | Identifier for an ASP, diagnosis and environment configuration. | Identifier plus `version` identifies a stored revision. |
| **ISGL** | `isgl_id` | Gene-list identifier. | Identifier plus `version` identifies a stored revision. |

A stable business ID is not a globally unique revision. Samples retain resolved
configuration references; repositories select revisions according to their contracts.
See [clinical identities](clinical-concepts.md) and the generated
[collection reference](mongodb-collections.md).

Creation operations check resource uniqueness. Conflict handling depends on the
endpoint. FastAPI request-model validation returns `422 Unprocessable Entity` for
missing or invalid required fields; application validation can also return `400`.
The endpoint response contract defines the applicable errors.

## 2. Findings and interpretation domains

The platform separates findings into these genomic domains, each linked to the sample by `SAMPLE_ID`.

| Interface Domain | Collection | Primary Intent |
|---|---|---|
| **SNV / Indel** | `variants` | Point mutations, transcript consequences, and clinical flags. |
| **CNV** | `cnvs` | Copy-number segment analysis and panel-gene impact. |
| **Translocation** | `translocations` | Genomic structural DNA events. |
| **RNA Fusion** | `fusions` | Fusion-call evidence and caller-specific metrics. |
| **Annotation** | `annotations` | Unified repository for interpretation text and classification history. |

### Classification identity and assay context

Small-variant tiering stores the most specific available identity in this order:
protein HGVS (`p`), coding HGVS (`c`), then genomic
`chromosome:position:reference/alternate` (`g`). Retrieval checks the same
identities for the same gene. Classification documents persist the
server-resolved assay group and diagnosis, matching the clinical annotation
identity used for retrieval. ASP and ASPC identifiers, configuration versions,
environment, and API resource-dispatch fields are not embedded in annotation
documents. Solid-tumor retrieval additionally constrains the classification by
diagnosis. Clients do not supply authoritative assay context; the API derives it
from the sample's recorded ASPC revision.

Classification and report narration are independent workflows. A bulk Tier
III classification can optionally create an accompanying text annotation for
a small variant by calling `create_annotation_text_from_gene`. Its inputs are
the selected transcript consequence, gene, sample assay group, and locally
stored OncoKB gene status. Its tumor-type terminology is resolved from the published
DNA clinical-rule release for the sample's assay, diagnosis and language. The existing
automatic sentence requires Swedish terminology. Tier I, II and IV classifications
are stored without generated text. Classification does not execute the report's
section-narrative evaluation.

## 3. Filter and logic domains

### Saved filter profiles

ASPC defaults and sample snapshots use intent-aware profiles:

- DNA: `filters.somatic.snv`, `filters.germline.snv`, `filters.somatic.cnv`,
  `filters.somatic.coverage` and `filters.somatic.translocation`.
- RNA: `filters.somatic.fusion`.

The [filter field reference](filter-profile-fields.md) owns keys, units, defaults
and bounds. [Assay filtering](assay-filtering.md) defines precedence and query-rule
exceptions. A saved selection is not automatically replaced by a later ASPC revision,
and updating filters does not rewrite a saved report.

Both SNV intents support `exclude_flags`. Options come from the center's
`filter_flag_metadata.yaml`; exclusions match raw flags exactly. Metadata labels,
badge colors and prefix descriptions do not change query semantics. See the
[flag metadata contract](../configuration/filter-flag-metadata-file.md).

### Query operators

The backend uses standard MongoDB operators to enforce analysis thresholds:

- **Range Constraints**: `$gte` / `$lte` for numeric metric boundaries.
- **Set Inclusion**: `$in` for list-based filtering (genes, callers, consequences).
- **Complex Objects**: `$elemMatch` for traversing nested array structures (Genotypes, VEP consequences).
- **Logical Unions**: `$or` / `$and` for multi-dimensional criteria consolidation.

## 4. Workload pagination strategy

The platform uses two pagination patterns:

### Server-side pagination

Primary sample listings use independent server-side pagination for live and
reported cohorts.

- **State Partitioning**: Navigating one dataset does not reset the cursor of the parallel list.
- **Complete Search Scope**: Search criteria are applied to the complete accessible sample catalog before page boundaries are calculated.
- **Stable Ordering**: Multi-column sorting is applied before pagination so each page belongs to one deterministic result order.
- **Metadata**: Response payloads provide exact totals and `has_next` flags to control pagination and result counts.

### Finding table pagination

Finding tables send paging, search, filter, and multi-column sort state to the
API. The backend applies those operations to the complete matching result set
before returning one page. The frontend query cache reuses an unchanged result
and invalidates affected entries after finding or filter mutations.

Finding hydration is batched. Deep sorted pages use private temporary merge runs;
complete exports still retain their output. See the measured fixture and temporary
storage requirements in [background delivery](../operations/background-delivery.md#deep-finding-pages).

## 5. Temporal standards

- **Durable storage**: Audit, notification and other typed contracts use UTC BSON
  datetime values where declared. API serializers commonly expose ISO-8601 strings;
  this does not mean every MongoDB timestamp is stored as a string.
- **Client Visualization**: The UI renders absolute timestamps in the
  deployment's configured `LOCAL_TIME_ZONE`. Relative labels are calculated from
  the same UTC instant.

## 6. Center-configurable UI metadata

### VCF filter flag metadata

VCF caller/filter badges are described in `config/examples/center/filter_flag_metadata.yaml`.
The UI reads this metadata through:

`GET /api/v1/public/filter-flags/metadata`

Centers can update labels and descriptions without changing React code. Matching order is:

1. `terms`: exact flag-specific metadata, for example `FAIL_STRANDBIAS`.
2. `exact`: exact generic values, for example `PASS`.
3. `prefixes`: first matching prefix, for example `WARN`, `FAIL`, or `PON`.
4. UI fallback prefix rules if no metadata exists.

Each metadata entry supports:

| Key | Purpose |
|---|---|
| `label` | Short UI label shown inside the badge. |
| `severity` | Badge tone: `pass`, `warn`, `fail`, `info`, or `neutral`. |
| `description` | Tooltip explanation shown on hover/focus. |

Example:

```yaml
terms:
  WARN_PON_FREEBAYES:
    label: PON FreeBayes
    severity: warn
    description: FreeBayes evidence overlaps the panel of normals.
```

This lets a center adapt filter descriptions to its caller stack, local validation rules,
and naming conventions while retaining the same API and UI contract.

## 7. Capability ownership

| Capability | Owning package | Execution and persistence |
| --- | --- | --- |
| Sample ingestion | `src/coyote3/application/ingest/` | Validated samples and dependent evidence commit through repository transactions on the ingest worker. |
| Clinical classification | `src/coyote3/application/classification/` | Shared annotation identity and classification history; independent from report narration. |
| Report wording | `src/coyote3/application/reporting/clinical_rules/` | Published scoped releases evaluate prepared facts; reports retain snapshots. |
| In-app and broadcast notices | `src/coyote3/application/notifications/` | Application-database messages and recipient state; maintenance workers deliver committed activity and email. |
| Audit events | `src/coyote3/application/audit/` | Event construction delegates persistence, outboxes and disk recovery to infrastructure repositories. |
| Diagnostic logging and error mail | `api/infra/observability/` | Daily service logs and an independent monitor. |
| Bundled installation data | `api/services/provisioning/deployment_data.py`, `api/services/provisioning/demo_installation.py` | Fresh bootstrap installs selected modules; later maintenance uses administrator authentication through the API. |

These are packages in one application, with worker processes providing execution
isolation. See [background delivery and recovery](../operations/background-delivery.md)
for queue ownership, retry limits and operational inspection.
