# Clinical Data Architecture and Workflow Integration

Coyote3 uses two connected data layers: configuration data and sample-specific findings. The system works correctly only when those layers stay aligned.

## Data Layers

The platform depends on two connected data domains:

1. **Configuration Layer**: Assay Panels (ASP), Configurations (ASPC), Gene Lists (ISGL), and RBAC policy documents. This layer defines filtering, reporting, and access behavior.
2. **Sample Layer**: Sample metadata and downstream findings such as variants, CNVs, fusions, and coverage. This layer holds the case-specific state.

If these layers drift apart, gene scope, filtering, and reports can become wrong.

## Core Relationship Framework

### Configuration Relationships

Configuration resources are linked by assay identifiers and runtime filter state:

```text
[ASP: assay_specific_panels]
  key: asp_id
  maps to: sample.assay
  defines: assay metadata, covered_genes, germline_genes, expected_files
      |
      +--> [ASPC: asp_configs]
      |      key: aspc_id = "<assay>:<environment>"
      |      maps to: sample.assay + sample.profile
      |      defines: default filters, analysis types, reporting settings
      |
      -?> [ISGL: insilico_genelists]
             key: isgl_id
             linked by: assays[] and assay_groups[]
             defines: optional curated gene subsets
```

Interpretation notes:

- ASP is the assay anchor used by both ingest and read paths.
- ASPC is the assay-plus-environment strategy contract.
- ISGL is optional and becomes active only when selected into `sample.filters`.

### Sample-to-configuration relationship

```text
[sample]
  assay   -------> [ASP.asp_id]
  profile -------> (environment)
                      |
                      v
                  [ASPC.aspc_id = "<assay>:<profile>"]

[sample.filters]
  genelists     -?> [ISGL.isgl_id]
  cnv_genelists -?> [ISGL.isgl_id]
  fusionlists   -?> [ISGL.isgl_id]
```

### Sample Persistence Flow

During ingest, the system creates a sample anchor and then links finding collections back to it:

| Originating Event | Persistence Action | Structural Link |
|---|---|---|
| **Bundle Ingest** | Creation of parent `samples` document | Primary system anchor |
| **Finding Persistence** | Writing to `variants`, `cnvs`, `fusions`, etc. | Keyed by `SAMPLE_ID` |
| **Logic Resolution** | Resolve ASPC, ASP, and ISGL metadata | Resolved by `assay` + `profile` |

### Parent-child persistence model

```text
[sample]
  _id
  assay
  profile
  filters
  ingest_status
      |
      +--> [variants]         by SAMPLE_ID
      +--> [cnvs]             by SAMPLE_ID
      +--> [panel_coverage]   by SAMPLE_ID
      +--> [fusions]          by SAMPLE_ID
      +--> [translocations]   by SAMPLE_ID
      +--> [biomarkers]       by SAMPLE_ID
      +--> [rna_expression]   by SAMPLE_ID
      +--> [rna_qc]           by SAMPLE_ID
      +--> [rna_classification] by SAMPLE_ID
```

## Effective Gene Scope

For DNA and RNA workflows, the platform dynamically computes **effective gene scope** per data type:

1. **SNV**:
   - Active `sample.filters.genelists` and SNV ad-hoc genes define the SNV gene restriction.
   - If no SNV genelist is selected, SNV findings are not gene-restricted.
2. **CNV**:
   - Active `sample.filters.cnv_genelists` and CNV ad-hoc genes define the CNV gene restriction.
   - If no CNV genelist is selected, CNV workflows fall back to ASP `covered_genes`.
3. **RNA Fusion**:
   - Active fusion lists and ad-hoc fusion genes define fusion scope.

### Gene-scope dependency diagram

```text
SNV scope
  ASP.covered_genes
  + optional selected SNV ISGLs
  + optional SNV ad hoc genes
  -> if no list/adhoc selected: SNVs stay unfiltered by genes

CNV scope
  ASP.covered_genes
  + optional selected CNV ISGLs
  + optional CNV ad hoc genes
  -> if no list/adhoc selected: use ASP.covered_genes

Fusion scope
  ASP assay context
  + optional selected fusion ISGLs
  + optional fusion ad hoc genes
```

## Execution Sequence

The usual flow from ingest to reporting is:

1. **Ingest Verification**: input payloads are parsed and validated against backend contracts.
2. **Atomic Ingestion**: The system stages the sample anchor as `loading`, persists dependent evidence documents, and only then marks the sample `ready`. On failure, the create flow rolls back staged evidence and removes the sample anchor; when Mongo transaction support is available, the same flow also runs inside a transaction boundary.
3. **Data Assembly**: on read, the API combines sample evidence with the matching environment configuration.
4. **Interpretation**: classifications, comments, and actions are written to the live annotation stores.
5. **Report Finalization**: The system reads the joined interpretation context and persists an immutable report snapshot in `reported_variants`.
   - DNA SNV report inclusion follows reportable-variant filtering after consequence resolution using `sample.vep_version`.
   - DNA CNV report inclusion requires both report-level inclusion (`interesting`) and the active CNV sample filters. A CNV outside the selected CNV genelist is not included in the report.

### Ingest and read sequence diagram

```text
Ingest
  payload
    -> validate sample contract
    -> resolve ASP for file policy
    -> seed sample.filters from ASPC if missing
    -> create sample with ingest_status="loading"
    -> write dependent findings with SAMPLE_ID
    -> mark sample ingest_status="ready"

Read / clinical review
  sample
    -> resolve ASPC by assay + profile
    -> resolve ASP by assay
    -> resolve selected ISGLs from sample.filters
    -> compute effective genes per target
    -> load filtered findings
    -> render review / reporting context
```

## Main Collections

| Collection | Operational Responsibility | Primary Relational Mapping |
|---|---|---|
| **asp_configs** | Environment-specific assay configuration | `sample.assay` + `sample.profile` |
| **assay_specific_panels** | Panel-level gene universe definition | `sample.assay` (ASP ID) |
| **insilico_genelists** | Curated gene lists | `isgl_id` via `sample.filters` |
| **samples** | Parent clinical entity and user filter state | Core system root for all case findings |
| **findings** | Genomic evidence (Variants/CNV/Fusions) | Linked strictly by `SAMPLE_ID` |
| **reported_variants** | Immutable report-time audit snapshots | Linked to finalized clinical reports |

## Integrity Rules

The following rules matter for correct behavior:

- **Identifier Synchronization**: keep `samples.assay`, `asp.asp_id`, and `aspc.assay_name` aligned.
- **Environment Integrity**: Every sample `profile` must map to a valid `production`, `development`, or `validation` environment within the configuration tier.
- **Relational Atomic Behavior**: Treat `samples` as the parent record for all findings; orphaned finding documents without a valid `SAMPLE_ID` are not allowed.
- **Metadata Alignment**: `vep_version` in the sample must match the relevant `vep_metadata` entry.
- **Reporting Alignment**: `sample.vep_version` is mandatory for DNA report generation because consequence-group resolution and variant-class translations are version-specific.

## Diagnostic Input Specifications

Complete DNA ingest artifacts typically include:
- Normalized VCF (Variants)
- Structural CNV definitions
- Sequencing Coverage metrics
- (Optional) Biomarkers and Structural Translocations

RNA ingest artifacts typically include:
- Transcription-level Fusion findings
- Gene Expression datasets
- Functional RNA Classifications
- Quality Control (QC) metrics

*Detailed payload structures and YAML specifications are documented in the [API / Sample YAML Guide](../api/sample_yaml.md).*

See also:

- [System Relationships](../architecture/system_relationships.md)
