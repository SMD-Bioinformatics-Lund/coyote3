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
  maps to: sample.asp_id
      defines: assay metadata, covered_genes, germline_genes, expected_files
      |
      +--> [ASPC: asp_configs]
      |      key: aspc_id generated from asp_id + subpanel_id + environment
      |      maps to: sample.asp_id + sample.environment + selected/base subpanel
      |      defines: default filters, analysis types, reporting settings
      |
      -?> [ISGL: insilico_genelists]
             key: isgl_id
             linked by: asp_ids[] and asp_groups[]
             tags: diagnosis[] contains one or more diagnosis/subpanel identifiers
             defines: optional curated SNV/CNV gene subsets and germline genes
```

Interpretation notes:

- ASP is the assay anchor used by both ingest and read paths.
- ASPC is the assay-plus-subpanel-plus-environment strategy contract. The base ASPC uses `subpanel_id=base`.
- ASPC `subpanel_id` is singular because one configuration resolves one reporting and filtering context. Its selectable non-base values come from the `diagnosis[]` tags on active ISGLs linked to that ASP.
- ISGL does not store `subpanel_id`. One gene list can be tagged to several diagnosis/subpanel contexts through `diagnosis[]`.
- ISGL is optional and becomes active only when selected into `sample.filters`.
- Fusion-compatible ISGLs contain one gene symbol per line. A fusion matches
  when either `gene1` or `gene2` belongs to the effective fusion gene scope.
  Selecting a list for SNV does not apply it to fusion analysis; each analysis
  stores and evaluates its own selection.

### Sample-to-configuration relationship

```text
[sample]
  assay   -------> [ASP.asp_id]
  profile -------> (environment)
                      |
                      v
                  [ASPC.asp_id + ASPC.subpanel_id + ASPC.environment]

[sample.filters]
  snv.snvlists         -?> [ISGL.isgl_id]
  cnv.cnvlists         -?> [ISGL.isgl_id]
  fusion.fusionlists   -?> [ISGL.isgl_id]
```

### Sample Persistence Flow

During ingest, the system creates a sample anchor and then links finding collections back to it:

| Originating Event | Persistence Action | Structural Link |
|---|---|---|
| **Bundle Ingest** | Creation of parent `samples` document | Primary system anchor |
| **Finding Persistence** | Writing to `variants`, `cnvs`, `fusions`, etc. | Keyed by `SAMPLE_ID` |
| **Logic Resolution** | Resolve ASPC, ASP, and ISGL metadata | Exact ASPC from stored identity/version; initial resolution by assay + subpanel + profile |

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
   - Active `sample.filters.somatic.snv.snvlists` and
     `sample.filters.somatic.snv.adhoc_genes` define the somatic SNV gene restriction.
   - If neither is selected, the SNV scope is `ASP.covered_genes`; an empty ASP
     coverage list means no gene restriction.
2. **CNV**:
   - Active `sample.filters.somatic.cnv.cnvlists` and
     `sample.filters.somatic.cnv.adhoc_genes` define the CNV gene restriction.
   - Only ISGLs typed as `cnv` or `adhoc_cnv` are accepted.
   - If neither is selected, the CNV scope is `ASP.covered_genes`; an empty ASP
     coverage list means no gene restriction.
   - The SNV selection never becomes a CNV filter, even when the selected ISGL
     also declares `cnv` in its `list_type`.
3. **RNA Fusion**:
   - Active `sample.filters.somatic.fusion.fusionlists` and ad-hoc fusion genes
     define fusion scope.
   - Only ISGLs typed as `fusion` or `adhoc_fusion` are accepted.
   - Without a fusion selection, the fusion scope is `ASP.covered_genes`; an
     empty ASP coverage list means no gene restriction.
   - Caller, effect, minimum spanning-pair, and minimum spanning-read criteria
     are read only from `sample.filters.somatic.fusion`.
   - Fusion filtering is not gated by a legacy assay-group name. Once an RNA
     ASPC enables fusion analysis, targeted RNA panels and WTS samples use the
     same filter contract. Assay group organizes the workflow but does not
     suppress configured caller, effect, support, or gene predicates.
   - The aggregator or upstream pipeline nominates exactly one selected call.
     Query eligibility is satisfied when one call in `fusions.calls` meets all
     configured caller, effect, evidence, and support predicates. The list,
     detail, classification identity, and reporting presentation use the call
     marked `selected`. The detail workflow can explicitly replace that
     selection while preserving every alternative in `fusions.calls`.
   - Fusion `effect` and `desc` are caller-owned values. They are not selected by
     the DNA MANE/RefSeq transcript protocol and are not stored in `anno_vep`.
   - A normalized effect equal to `in-frame` is presented as in-frame. Every
     other non-empty effect is presented as out-of-frame. This is a display and
     review convention for caller output, not a VEP consequence calculation.
     The effect filter uses the same categories: **In-frame** matches exact
     `in-frame`, while **Out-of-frame** matches every non-empty caller effect
     other than `in-frame`, including truncated UTR/CDS descriptions.
   - Description terms are split on commas and rendered using the exact
     importance groups configured in
     `api/config/center/clinical_vocabulary.toml`. Important cancer-reference
     terms are green, not-important or artifact-associated terms are red, and
     contextual terms are gray. Unknown terms remain visible with neutral
     styling so upstream vocabulary changes are not hidden.
   - Selected description terms are query predicates as well as display
     metadata. Terms selected within the description group are alternatives.
     The description group is combined with caller, effect, and read-support
     groups using AND, and one call must satisfy every active call-level group.
     Matching is case-insensitive and respects comma-delimited token
     boundaries.
4. **Translocation**:
   - Active `sample.filters.somatic.translocation.fusionlists` and ad-hoc
     translocation genes define the DNA fusion/translocation scope.
   - Fusion-compatible ISGLs are accepted because DNA translocations and RNA
     fusions share gene-list membership semantics, but the saved selections
     remain independent.
   - Without a translocation selection, the scope is `ASP.covered_genes`; an
     empty ASP coverage list means no gene restriction.

`ISGL.list_type` controls selector availability, not automatic application. A
single ISGL may be available for SNV, CNV, and fusion, while each analysis
retains an independent saved selection and independent query.

### Gene-scope dependency diagram

```text
SNV scope
  ASP.covered_genes
  + optional selected SNV ISGLs
  + optional SNV ad hoc genes
  -> if no list/adhoc selected: use ASP.covered_genes
  -> if ASP.covered_genes is empty: no gene restriction

CNV scope
  ASP.covered_genes
  + optional selected CNV ISGLs
  + optional CNV ad hoc genes
  -> if no list/adhoc selected: use ASP.covered_genes
  -> if ASP.covered_genes is empty: no gene restriction

Fusion scope
  ASP.covered_genes
  + optional selected fusion ISGLs
  + optional fusion ad hoc genes
  -> if no list/adhoc selected: use ASP.covered_genes
  -> if ASP.covered_genes is empty: no gene restriction

DNA fusion/translocation scope
  ASP.covered_genes
  + optional selected fusion-compatible ISGLs
  + optional translocation ad hoc genes
  -> if no list/adhoc selected: use ASP.covered_genes
  -> if ASP.covered_genes is empty: no gene restriction
```

## Execution Sequence

The usual flow from ingest to reporting is:

1. **Ingest Verification**: input payloads are parsed and validated against backend contracts.
2. **Atomic Ingestion**: The system stages the sample anchor as `loading`, persists dependent evidence documents, and only then marks the sample `ready`. On failure, the create flow rolls back staged evidence and removes the sample anchor; when Mongo transaction support is available, the same flow also runs inside a transaction boundary.
3. **Data Assembly**: on read, the API combines sample evidence with the matching environment configuration.
4. **Interpretation**: classifications, comments, and actions are written to the live annotation stores.
5. **Report Finalization**: The system reads the joined interpretation context and persists an immutable report snapshot in `reported_variants`.
   - DNA SNV report inclusion follows reportable-variant filtering after consequence resolution using `sample.database_versions.vep`.
   - DNA CNV report inclusion requires both report-level inclusion (`interesting`) and the active CNV sample filters. A CNV outside the selected CNV genelist is not included in the report.
   - RNA fusion report inclusion requires Tier 1, Tier 2, or Tier 3 and excludes false-positive, irrelevant, and blacklisted findings. The fusion `interesting` flag is a review marker only and is not a report-inclusion condition.

### Ingest and read sequence diagram

```text
Ingest
  payload
    -> validate sample contract
    -> resolve ASP for file policy
    -> resolve ASPC by assay + subpanel + profile
    -> persist current ASPC identity/version
    -> seed sample.filters from ASPC if missing
    -> create sample with ingest_status="loading"
    -> write dependent findings with SAMPLE_ID
    -> mark sample ingest_status="ready"

Read / clinical review
  sample
    -> resolve active ASPC by assay + subpanel + profile
    -> resolve ASP by assay
    -> resolve selected ISGLs from sample.filters
    -> compute effective genes per target
    -> load filtered findings
    -> render review / reporting context
```

## Main Collections

| Collection | Operational Responsibility | Primary Relational Mapping |
|---|---|---|
| **asp_configs** | Assay/subpanel/environment configuration | `sample.current_aspc_id` and version |
| **assay_specific_panels** | Panel-level gene universe definition | `sample.asp_id` (ASP ID) |
| **insilico_genelists** | Curated gene lists | `isgl_id` via `sample.filters` |
| **samples** | Parent clinical entity and user filter state | Core system root for all case findings |
| **findings** | Genomic evidence (Variants/CNV/Fusions) | Linked strictly by `SAMPLE_ID` |
| **reported_variants** | Immutable report-time audit snapshots | Linked to finalized clinical reports |

### RNA fusion reporting contract

RNA report preparation first loads the sample's filtered fusion findings and
joins their current classification and visible global annotations. It then
removes false-positive, irrelevant, blacklisted, Tier IV, and unclassified
findings. This single reportable set is used for all three outputs:

1. the RNA snapshot table (`fusion`, breakpoints, effect, read support, tier,
   and reviewed annotation);
2. the YAML-driven clinical conclusion, where `findings | fusion_summary`
   inserts reviewed finding paragraphs between the assay-specific introduction
   and closing text; and
3. the rendered report's `Fusion / Klassificering` result table and detailed
   fusion sections.

The active ASPC provides the report header, method, and analysis description.
The static rule source provides the approved assay/subpanel wording. Fusion
caller selection and filtering occur before rule evaluation, so report rules
cannot silently select a different call or reintroduce an excluded fusion.

RNA reporting does not read the former application-level `REPORT_CONFIG`,
reconstruct `gene1` and `gene2` from legacy combined strings, or select the
first call when no call is marked selected. Each reportable fusion must contain
canonical `gene1` and `gene2` values and exactly one `calls[].selected = 1`
entry. The active ASPC must contain non-empty `reporting.report_header`,
`reporting.report_method`, `reporting.report_description`, and
`reporting.report_folder` values. A missing requirement stops preview or save
with a validation response; it is never replaced by legacy configuration or
placeholder clinical data.

## Integrity Rules

The following rules matter for correct behavior:

- **Identifier Synchronization**: keep `samples.assay`, `asp.asp_id`, and `aspc.asp_id` aligned; ASPC uniqueness is `asp_id + subpanel_id + environment`.
- **Environment Integrity**: Every sample `profile` must map to a valid `production`, `development`, or `validation` environment within the configuration tier.
- **Relational Atomic Behavior**: Treat `samples` as the parent record for all findings; orphaned finding documents without a valid `SAMPLE_ID` are not allowed.
- **DNA Metadata Alignment**: For DNA small-variant analysis,
  `database_versions.vep` in the sample must match the relevant `vep_metadata`
  entry. RNA fusion findings do not use VEP and do not write `anno_vep` rows.
- **Reporting Alignment**: `sample.database_versions.vep` is mandatory for DNA report generation because consequence-group resolution and variant-class translations are version-specific.

## Diagnostic Input Specifications

Complete DNA ingest artifacts typically include:

- Normalized VCF (Variants)
- Structural CNV definitions
- Sequencing Coverage metrics
- (Optional) Biomarkers and Structural Translocations

RNA ingest artifacts depend on the ASPC analysis selection:

- Transcription-level Fusion findings
- Gene expression datasets for WTS only
- Functional RNA classifications for WTS only
- Quality-control metrics where enabled

Targeted RNA fusion panels do not expose expression or classification merely
because they are RNA assays. These analyses are available only to the `wts`
ASP family and only when enabled by the resolved ASPC.

The complete report-facing preparation and annotation protocol is documented
in
[Clinical Data Preparation And Reporting Flow](../architecture/clinical_data_and_reporting_flow.md).

*Detailed payload structures and YAML specifications are documented in the [API / Sample YAML Guide](../api/sample_yaml.md).*

## Sample Deletion Lifecycle

Deleting a sample is a coordinated ownership operation, not a deletion of only
the `samples` row. Coyote3 removes the sample document and all Coyote-owned
children keyed by its sample identifier: small variants, CNVs, coverage,
translocations, fusions, biomarkers, RNA expression, RNA classification, RNA
quality control, sample comments, reports, and reported-finding snapshots.

Shared knowledgebase cache entries are retained. The deleted sample identifier
and name are removed from their `sample_ids` and `sample_names` reference
arrays. Global annotations, HGNC/VEP/reference collections, audit events, and
records owned by the external BAM service are also retained because they are
shared reference or traceability data rather than sample-owned Coyote records.

See also:

- [System Relationships](../architecture/system_relationships.md)
