# Domain-Specific Application Reference

This document maps the main platform domains, UI identifiers, API keys, and stored backend fields.

## 1. Primary Sample Domain

The `samples` document is the main record for a case. Most findings collections link back to the sample through `SAMPLE_ID`.

### Operational Component Mapping

| Identifier | Collection | Primary Key | Operational Scoping |
|---|---|---|---|
| **ASP** | `assay_specific_panels` | `asp_id` | Enforces the physical gene universe and assay metrics. |
| **ASPC** | `asp_configs` | `aspc_id` | Enforces assay/subpanel/environment filtering and reporting strategies. |
| **ISGL** | `insilico_genelists` | `isgl_id` | Provides curated clinical gene cohorts for interpretation. |

### Resource Identification and Uniqueness

Administrative resources use stable business IDs for routing and lookup.

| Resource Type | ID Attribute | Specification | Constraint |
|---|---|---|---|
| **User** | `username` | Lowercase alphanumeric login identifier. | Global Uniqueness |
| **Role** | `role_id` | Lowercase functional slug (e.g., `viewer`, `admin`). | Global Uniqueness |
| **Permission** | `permission_id` | Standardized `resource:action[:scope]` key (for example, `samples:edit`). | Global Uniqueness |
| **ASP** | `asp_id` | Assay identifier mapped to `sample.asp_id`. | Global Uniqueness |
| **ASPC** | `aspc_id` | Stable identifier for one ASP, subpanel, and environment configuration. | Global Uniqueness |
| **ISGL** | `isgl_id` | Organizational genelist identifier. | Global Uniqueness |

Creation operations check uniqueness. Conflicts return `409 Conflict`. Missing required fields return `400 Bad Request`.

## 2. Findings and Interpretation Domains

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
server-resolved assay group and subpanel, matching the clinical annotation
identity used for retrieval. ASP and ASPC identifiers, configuration versions,
environment, and API resource-dispatch fields are not embedded in annotation
documents. Solid-tumor retrieval additionally constrains the classification by
subpanel. Clients do not supply authoritative assay context; the API derives it
from the sample's recorded ASPC revision.

## 3. Filter and Logic Domains

### Persistent DNA Filter Specifications

Sample-level filters are persisted within the domain sections
`samples.filters.snv`, `samples.filters.cnv`, `samples.filters.coverage`, or
`samples.filters.fusion`. These values override ASPC defaults until reset.

| Attribute Key | Type | Functional Definition | Implementation |
|---|---|---|---|
| `snv.min_alt_reads` | Integer | Minimum supporting alternate reads for SNV calls. | Query Gate |
| `snv.min_depth` | Integer | Absolute minimum sequencing depth at position. | Query Gate |
| `snv.min_freq` | Float | Minimum Allele Frequency (VAF) in target sample. | Query Gate |
| `snv.max_popfreq` | Float | Upper-bound population frequency threshold. | Logic & UI |
| `cnv.min_cnv_size` | Integer | Minimum structural size for CNV consideration. | Query Gate |
| `cnv.cnv_loss_cutoff` | Float | Segment ratio threshold for designated loss events. | Query Gate |
| `snv.vep_consequences`| List | UI consequence groups resolved through versioned VEP metadata. | Query Gate |
| `snv.snvlists` / `cnv.cnvlists` / `fusion.fusionlists` | List | Active typed ISGL identifiers restricting analysis scope. | Logic Gate |

### Persistent RNA Filter Specifications

| Attribute Key | Type | Functional Definition | Implementation |
|---|---|---|---|
| `fusion.min_spanning_reads` | Integer | Minimum supporting split/span read counts. | Query Gate |
| `fusion.fusion_callers` | List | Array of authorized or selected fusion callers. | Query Gate |
| `fusion.fusion_effects` | List | Functional effect classifications (e.g., in-frame). | Query Gate |
| `fusion.fusion_descriptions` | List | Exact comma-delimited caller evidence terms. Terms within the list are alternatives; this group is cumulative with caller, effect, and support filters. | Query Gate |

### Query Operators

The backend uses standard MongoDB operators to enforce analysis thresholds:

- **Range Constraints**: `$gte` / `$lte` for numeric metric boundaries.
- **Set Inclusion**: `$in` for list-based filtering (genes, callers, consequences).
- **Complex Objects**: `$elemMatch` for traversing nested array structures (Genotypes, VEP consequences).
- **Logical Unions**: `$or` / `$and` for multi-dimensional criteria consolidation.

## 4. Workload Pagination Strategy

The platform uses two pagination patterns:

### Server-Side Pagination

Primary sample listings use independent server-side pagination for live and
reported cohorts.

- **State Partitioning**: Navigating one dataset does not reset the cursor of the parallel list.
- **Complete Search Scope**: Search criteria are applied to the complete accessible sample catalog before page boundaries are calculated.
- **Stable Ordering**: Multi-column sorting is applied before pagination so each page belongs to one deterministic result order.
- **Metadata**: Response payloads provide exact totals and `has_next` flags to control pagination and result counts.

### Finding Table Pagination

Finding tables send paging, search, filter, and multi-column sort state to the
API. The backend applies those operations to the complete matching result set
before returning one page. The frontend query cache reuses an unchanged result
and invalidates affected entries after finding or filter mutations.

## 5. Temporal Standards

- **Durable Storage**: All timestamps are stored in UTC (ISO-8601).
- **Client Visualization**: The UI renders absolute timestamps in the
  deployment's configured `LOCAL_TIME_ZONE`. Relative labels are calculated from
  the same UTC instant.

## 6. Center-Configurable UI Metadata

### VCF Filter Flag Metadata

VCF caller/filter badges are described in `api/config/center/filter_flag_metadata.yaml`.
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
