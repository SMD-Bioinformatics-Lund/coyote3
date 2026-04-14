# Domain-Specific Application Reference

This document provides a comprehensive technical mapping of platform domains, focusing on the structural relationships between user interface identifiers, API request keys, and persistent backend data fields.

## 1. Primary Sample Domain

The `samples` document serves as the central anchor for the clinical platform. The majority of finding-level collections maintain relational integrity by referencing the Sample utilizing a standardized `SAMPLE_ID` attribute.

### Operational Component Mapping

| Identifier | Collection | Primary Key | Operational Scoping |
|---|---|---|---|
| **ASP** | `assay_specific_panels` | `asp_id` | Enforces the physical gene universe and assay metrics. |
| **ASPC** | `asp_configs` | `aspc_id` | Enforces environment-specific filtering and reporting strategies. |
| **ISGL** | `insilico_genelists` | `isgl_id` | Provides curated clinical gene cohorts for interpretation. |

### Resource Identification and Uniqueness

Administrative resources utilize immutable "Business IDs" for all routing and lookup operations, ensuring stable references across system versions.

| Resource Type | ID Attribute | Specification | Constraint |
|---|---|---|---|
| **User** | `username` | Lowercase alphanumeric login identifier. | Global Uniqueness |
| **Role** | `role_id` | Lowercase functional slug (e.g., `viewer`, `admin`). | Global Uniqueness |
| **Permission** | `permission_id` | Standardized functional key (e.g., `edit_sample`). | Global Uniqueness |
| **ASP** | `asp_id` | Assay identifier mapped to `sample.assay`. | Global Uniqueness |
| **ASPC** | `aspc_id` | Compound key: `<assay>:<environment>`. | Global Uniqueness |
| **ISGL** | `isgl_id` | Organizational genelist identifier. | Global Uniqueness |

**Validation Protocol**: Creation operations perform real-time uniqueness verification. Conflicts result in `409 Conflict` state, while missing required segments trigger `400 Bad Request` responses.

## 2. Findings and Interpretation Domains

The platform segments findings into four primary genomic domains, each linked strictly to the sample context via `SAMPLE_ID`.

| Interface Domain | Collection | Primary Intent |
|---|---|---|
| **SNV / Indel** | `variants` | Point mutations, transcript consequences, and clinical flags. |
| **CNV** | `cnvs` | Copy-number segment analysis and panel-gene impact. |
| **Translocation** | `translocations` | Genomic structural DNA events. |
| **RNA Fusion** | `fusions` | Fusion-call evidence and caller-specific metrics. |
| **Annotation** | `annotations` | Unified repository for interpretation text and classification history. |

## 3. Filter and Logic Domains

### Persistent DNA Filter Specifications

Sample-level filters are persisted within the `samples.filters` document. These values override base ASPC configurations to provide sample-specific review contexts.

| Attribute Key | Type | Functional Definition | Implementation |
|---|---|---|---|
| `min_alt_reads` | Integer | Minimum supporting alternate reads for SNV calls. | Query Gate |
| `min_depth` | Integer | Absolute minimum sequencing depth at position. | Query Gate |
| `min_freq` | Float | Minimum Allele Frequency (VAF) in target sample. | Query Gate |
| `max_popfreq` | Float | Upper-bound population frequency threshold. | Logic & UI |
| `min_cnv_size` | Integer | Minimum structural size for CNV consideration. | Query Gate |
| `cnv_loss_cutoff` | Float | Segment ratio threshold for designated loss events. | Query Gate |
| `vep_consequences`| List | Array of SO terms defining prioritized consequences. | Query Gate |
| `genelists` | List | Active ISGL identifiers restricting analysis scope. | Logic Gate |

### Persistent RNA Filter Specifications

| Attribute Key | Type | Functional Definition | Implementation |
|---|---|---|---|
| `min_spanning_reads` | Integer | Minimum supporting split/span read counts. | Query Gate |
| `fusion_callers` | List | Array of authorized or selected fusion callers. | Query Gate |
| `fusion_effects` | List | Functional effect classifications (e.g., in-frame). | Query Gate |

### Query Operators

The backend uses standard MongoDB operators to enforce analysis thresholds:
- **Range Constraints**: `$gte` / `$lte` for numeric metric boundaries.
- **Set Inclusion**: `$in` for list-based filtering (genes, callers, consequences).
- **Complex Objects**: `$elemMatch` for traversing nested array structures (Genotypes, VEP consequences).
- **Logical Unions**: `$or` / `$and` for multi-dimensional criteria consolidation.

## 4. Workload Pagination Strategy

The platform utilizes a dual pagination strategy to balance backend performance with interface responsiveness:

### Server-Side Pagination

Primary sample listings utilize independent server-side pagination for "Live" versus "Finalized" cohorts.
- **State Partitioning**: Navigating one dataset does not reset the cursor of the parallel list.
- **Metadata**: Response payloads provide `has_next` flags to control interface control visibility.

### Client-Side Pagination

Localized interpretation tables utilize in-page pagination to allow for rapid sorting and filtering after the initial data packet is delivered to the browser.

## 5. Temporal Standards

- **Durable Storage**: All timestamps are persisted using the UTC (ISO-8601) standard.
- **Client Visualization**: The interface dynamically renders temporal data according to the viewer's localized timezone configuration.
