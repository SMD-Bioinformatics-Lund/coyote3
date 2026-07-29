# Assay Configuration and Dynamic Query Orchestration

The platform's analytic engine is driven by the Assay-Specific Panel Configuration (ASPC) system—a strictly versioned runtime strategy contract that governs finding retrieval, filtering logic, and clinical review behavior.

## Systematic Logic Hierarchy

The resolution of analytic strategies follows a deterministic inheritance model to ensure consistency across varying center requirements:

1. **ASPC Resolution**: The system resolves an active configuration from
   `assay`, `subpanel_id`, and `profile` (environment). A specific subpanel is
   preferred; `base` is the controlled fallback. The resolved ObjectId,
   business ID, and version are persisted on the sample.
2. **Initial Filter Seeding**: If a sample has no `filters` document, the resolved ASPC provides the initial threshold and reporting defaults.
3. **Sample-Level Truth**: Once persisted, `samples.filters` is the filter state used for findings and reports until explicitly reset.
4. **Query Execution**: Domain services convert the finalized typed filter set
   into repository queries for SNVs, CNVs, fusions, translocations, and quality
   data.

## Configuration Domain Interplay

Analytic execution relies on the synchronization of three core architectural pillars:

- **Assay-Specific Panels (ASP)**: Defines assay metadata and the physical set of covered genes or regions.
- **Assay-Specific Panel Configuration (ASPC)**: The
  assay/subpanel/environment-specific operational strategy governing filtered
  evidence and reporting constraints.
- **In-Silico Gene Lists (ISGL)**: Managed gene cohorts that dynamically restrict the interpretation scope during clinical review.

The **Effective Gene Scope** is target-specific:

- **SNV**: Active SNV genelists and ad-hoc genes define the optional SNV gene restriction. If no SNV genelist is selected, the SNV query is not gene-restricted.
- **CNV**: Active CNV genelists and ad-hoc genes define the CNV scope. If no CNV genelist is selected, CNV workflows fall back to ASP covered genes.
- **RNA fusion**: Fusion list selection and ad-hoc fusion genes govern RNA fusion scope.

## DNA Variant Resolution Framework

The SNV analytics engine applies fixed group-specific query policy. The
hematology-like groups (`myeloid`, `hematology`, `fusion`, and `tumwgs`)
combine the validated somatic and germline rescue branches. `solid` uses the
solid-tumour branch. The policy is code-owned because it determines clinical
query semantics; threshold values and selected gene lists remain
ASPC/sample configuration.

### SNV Consequence Semantics

SNV retrieval uses transcript-aware consequence matching. A consequence filter matches a variant when either of the following is true:

- `INFO.selected_CSQ.Consequence` is in the resolved consequence terms.
- Any transcript entry in `INFO.CSQ` has `Consequence` in the resolved consequence terms.

This is broader than filtering only on the transcript displayed in the UI. It avoids dropping variants where another clinically relevant transcript carries the selected consequence class. The UI may therefore display a selected transcript consequence that is not itself one of the checked consequence groups, because the row was admitted by another `INFO.CSQ` transcript.

Assay-group rescue branches are part of the fixed clinical query policy:

- Hematology-like groups include germline rescue branches for `INFO.MYELOID_GERMLINE`,
  CEBPA `GERMLINE`, and the validated chromosome 1 position interval.
- `solid` retains the direct `GERMLINE` rescue branch and the
  TERT/NFKBIE regulatory rescue branch.

Future changes to selected-transcript-only filtering must be treated as a clinical/product behavior change. Such a change should update this section, include count comparisons against the current validated behavior, and explicitly state how rows admitted only by non-selected `INFO.CSQ` transcripts are handled.

## Administrative Configuration Protocol

The administrative interface controls query behavior through validated managed forms backed by Pydantic contracts:

- **Parameter Envelopes**: Core thresholds (depth, frequency, etc.) are managed through structured form interfaces synced to backend Pydantic models.
- **Typed Filter Sections**: SNV, CNV, fusion, coverage, and reporting behavior are expressed as typed ASPC fields instead of arbitrary MongoDB query JSON.
- **Versioned Clinical Configuration**: Changes to ASPC behavior are represented as versioned center configuration, making count changes and report behavior auditable.
- **Gene List Defaults**: ASPC may seed initial defaults when a sample is created or reset, but active sample-level list selection is stored on `samples.filters`.

The report query workflow produces a prepared report context containing only
already filtered and annotation-enriched findings. Report-text composition
consumes that context and does not reapply analytical filters. See
[Clinical data preparation and reporting flow](../architecture/clinical_data_and_reporting_flow.md).

## Analytic Threshold Specifications

### Baseline DNA Thresholds
The platform enforces strict numeric bounds for primary sequencing metrics including:
- `min_freq` / `max_freq`: Allele frequency boundaries.
- `min_depth` / `min_alt_reads`: Sequencing coverage and evidence reliability.
- `max_popfreq`: Population frequency gate.
- `min_cnv_size` / `cnv_cutoff`: Copy-number structural thresholds.

### RNA Fusion Thresholds
RNA-specific analytics prioritize evidence-based detection parameters:
- `min_spanning_reads` / `min_spanning_pairs`: Supporting evidence thresholds.
- `fusion_callers` / `fusion_effects`: Tool-specific and biological impact filter sets.

## Automated Clinical Context Matching

The platform provides sophisticated diagnosis-driven list allocation. When the `use_diagnosis_genelist` protocol is active, the system can resolve and attach ISGL gene cohorts where the genelist's clinical definition aligns with the sample's sub-panel context, ensuring immediate diagnostic relevance upon sample initialization or reset.
