# Clinical Data Architecture and Workflow Integration

Coyote3 uses two connected data layers: configuration data and sample-specific findings. The system works correctly only when those layers stay aligned.

## Data Layers

The platform depends on two distinct but connected data domains:

1. **Configuration Layer**: Assay Panels (ASP), Configurations (ASPC), Gene Lists (ISGL), and RBAC policy documents. This layer defines filtering, reporting, and access behavior.
2. **Sample Layer**: Sample metadata and downstream findings such as variants, CNVs, fusions, and coverage. This layer holds the case-specific state.

If these layers drift apart, the result is wrong gene scope resolution, incorrect filtering thresholds, and unstable report output.

## Core Relationship Framework

### Configuration Relationships

Configuration resources are linked by assay identifiers:

```text
Assay Configuration (asp_configs)
  - Key Mapping: aspc_id = "<assay>:<environment>"
  - Defines: default filters, analysis scopes, and report settings.
            ↓
Assay Panels (assay_specific_panels)
  - Key Mapping: asp_id (Maps to sample.assay)
  - Defines: covered genes and germline genes.
            ↓
In-Silico Gene Lists (insilico_genelists)
  - Key Mapping: isgl_id
  - Defines: curated gene subsets for targeted interpretation.
```

### Sample Persistence Flow

During ingest, the system creates a sample anchor and then links finding collections back to it:

| Originating Event | Persistence Action | Structural Link |
|---|---|---|
| **Bundle Ingest** | Creation of parent `samples` document | Primary system anchor |
| **Finding Persistence** | Writing to `variants`, `cnvs`, `fusions`, etc. | Keyed by `SAMPLE_ID` |
| **Logic Resolution** | Resolve ASPC, ASP, and ISGL metadata | Resolved by `assay` + `profile` |

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

## Execution Sequence

The usual flow from ingest to reporting is:

1. **Ingest Verification**: Input payloads are parsed and validated against strict Pydantic JSON contracts.
2. **Atomic Ingestion**: The system stages the sample anchor as `loading`, persists dependent evidence documents, and only then marks the sample `ready`. On failure, the create flow rolls back staged evidence and removes the sample anchor; when Mongo transaction support is available, the same flow also runs inside a transaction boundary.
3. **Data Assembly**: On read, the API combines sample evidence with the matching environment configuration.
4. **Interpretation**: Functional finding flags (Classification, Comments, Actions) are committed to live annotation stores.
5. **Report Finalization**: The system reads the joined interpretation context and persists an immutable report snapshot in `reported_variants`.
   - DNA SNV report inclusion follows reportable-variant filtering after consequence resolution using `sample.vep_version`.
   - DNA CNV report inclusion requires both report-level inclusion (`interesting`) and the active CNV sample filters. A CNV outside the selected CNV genelist is not included in the report.

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

- **Identifier Synchronization**: Maintain exact nomenclature across `samples.assay`, `asp.asp_id`, and `aspc.assay_name`.
- **Environment Integrity**: Every sample `profile` must map to a valid `production`, `development`, or `validation` environment within the configuration tier.
- **Relational Atomic Behavior**: Treat `samples` as the parent record for all findings; orphaned finding documents without a valid `SAMPLE_ID` are not allowed.
- **Metadata Alignment**: The `vep_version` specified during sample ingestion must precisely track the required knowledgebase versions stored within the auxiliary `vep_metadata` collections.
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
