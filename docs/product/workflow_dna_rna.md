# Clinical Data Architecture and Workflow Integration

Coyote3 utilizes a dual-layer data architecture that enforces absolute synchronization between enterprise configuration and individualized sample findings to deliver a consistent clinical interpretation experience.

## Architectural Layers

The platform's operational reliability is built upon two distinct yet synchronized data domains:

1. **Strategic Configuration Tier**: Composed of Assay Panels (ASP), Configurations (ASPC), Gene Lists (ISGL), and associated RBAC policies. This layer defines the platform's interpretive boundaries and reporting logic.
2. **Operational Sample Tier**: Composed of persistent Sample metadata and specific downstream findings (Variants, CNVs, Fusions, Coverage). This layer manages the active interpretive state for individual diagnostic cases.

Structural alignment between these tiers is mandatory; configuration drift results in fragmented interpretation gene scopes, incorrect filtering thresholds, and unstable reporting output.

## Core Relationship Framework

### Managed Lifecycle Configuration

The relationship between configuration resources is strictly governed by assay identifier resolution:

```text
Assay Configuration (asp_configs)
  - Key Mapping: aspc_id = "<assay>:<environment>"
  - Authorities: Default filter thresholds, analysis scopes, and report schemas.
            ↓
Assay Panels (assay_specific_panels)
  - Key Mapping: asp_id (Maps to sample.assay)
  - Authorities: Physical gene universe coverage and germline definitions.
            ↓
In-Silico Gene Lists (insilico_genelists)
  - Key Mapping: isgl_id
  - Authorities: Curated clinical gene cohorts for targeted interpretation.
```

### Transactional Sample Orchestration

Upon sample ingestion, the platform establishes a persistent Sample anchor with explicit foreign-key links to finding collections:

| Originating Event | Persistence Action | Structural Link |
|---|---|---|
| **Bundle Ingest** | Creation of parent `samples` document | Primary system anchor |
| **Finding Persistence** | Writing to `variants`, `cnvs`, `fusions`, etc. | Keyed by `SAMPLE_ID` |
| **Logic Resolution** | Dynamic yield of ASPC, ASP, and ISGL metadata | Resolved by `assay` + `profile` |

## Resolution of Interpretive Gene Scopes

For DNA and RNA workflows, the platform dynamically computes **effective gene scope** per data type:

1. **SNV**:
   - Active `sample.filters.genelists` and SNV ad-hoc genes define the SNV gene restriction.
   - If no SNV genelist is selected, SNV findings are not gene-restricted.
2. **CNV**:
   - Active `sample.filters.cnv_genelists` and CNV ad-hoc genes define the CNV gene restriction.
   - If no CNV genelist is selected, CNV workflows fall back to ASP `covered_genes`.
3. **RNA Fusion**:
   - Active fusion lists and ad-hoc fusion genes define fusion scope.

## Platform Execution Sequence

The diagnostic lifecycle follows a standardized operational flow from initial ingestion to finalized reporting:

1. **Ingest Verification**: Input payloads are parsed and validated against strict Pydantic JSON contracts.
2. **Atomic Ingestion**: The system persists the sample anchor and dependent evidence documents as a synchronized bundle.
3. **Data Assembly**: Upon document access, the API dynamically merges sample evidence with environment configurations.
4. **Interpretation**: Functional finding flags (Classification, Comments, Actions) are committed to live annotation stores.
5. **Report Finalization**: The system reads the joined interpretation context and persists an immutable report snapshot in `reported_variants`.
   - DNA SNV report inclusion follows reportable-variant filtering after consequence resolution using `sample.vep_version`.
   - DNA CNV report inclusion requires both report-level inclusion (`interesting`) and the active CNV sample filters. A CNV outside the selected CNV genelist is not included in the report.

## Functional Domain Catalog

| Collection | Operational Responsibility | Primary Relational Mapping |
|---|---|---|
| **asp_configs** | Runtime environment orchestration | `sample.assay` + `sample.profile` |
| **assay_specific_panels** | Panel-level gene universe definition | `sample.assay` (ASP ID) |
| **insilico_genelists** | Clinical cohort management | `isgl_id` via `sample.filters` |
| **samples** | Parent clinical entity and user filter state | Core system root for all case findings |
| **findings** | Genomic evidence (Variants/CNV/Fusions) | Linked strictly by `SAMPLE_ID` |
| **reported_variants** | Immutable report-time audit snapshots | Linked to finalized clinical reports |

## Operational Integrity Standards

To ensure optimal platform performance, system administrators must adhere to the following standards:

- **Identifier Synchronization**: Maintain exact nomenclature across `samples.assay`, `asp.asp_id`, and `aspc.assay_name`.
- **Environment Integrity**: Every sample `profile` must map to a valid `production`, `development`, or `validation` environment within the configuration tier.
- **Relational Atomic Behavior**: Treat `samples` as the non-negotiable parent record for all findings; orphaned finding documents without a valid `SAMPLE_ID` relationship are prohibited.
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
