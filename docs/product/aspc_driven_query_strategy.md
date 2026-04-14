# Assay Configuration and Dynamic Query Orchestration

The platform's analytic engine is driven by the Assay-Specific Panel Configuration (ASPC) system—a strictly versioned runtime strategy contract that governs finding retrieval, filtering logic, and clinical review behavior.

## Systematic Logic Hierarchy

The resolution of analytic strategies follows a deterministic inheritance model to ensure consistency across varying center requirements:

1. **ASPC Resolution**: The system derives the primary configuration identity (`aspc_id`) from the sample-level `assay` and `profile` (environment) attributes.
2. **Initial Filter Seeding**: If a sample has no `filters` document, the resolved ASPC provides the initial threshold and reporting defaults.
3. **Sample-Level Truth**: Once persisted, `samples.filters` is the filter state used for findings and reports until explicitly reset.
4. **Query Execution**: The finalized sample filter set is merged with domain-specific MongoDB query JSON to orchestrate precise retrieval for SNVs, CNVs, Fusions, and Translocations.

## Configuration Domain Interplay

Analytic execution relies on the synchronization of three core architectural pillars:

- **Assay-Specific Panels (ASP)**: Defines assay metadata and the physical set of covered genes or regions.
- **Assay-Specific Panel Configuration (ASPC)**: The environment-specific operational strategy governing filtered evidence and reporting constraints.
- **In-Silico Gene Lists (ISGL)**: Managed gene cohorts that dynamically restrict the interpretation scope during clinical review.

The **Effective Gene Scope** is target-specific:

- **SNV**: Active SNV genelists and ad-hoc genes define the optional SNV gene restriction. If no SNV genelist is selected, the SNV query is not gene-restricted.
- **CNV**: Active CNV genelists and ad-hoc genes define the CNV scope. If no CNV genelist is selected, CNV workflows fall back to ASP covered genes.
- **RNA fusion**: Fusion list selection and ad-hoc fusion genes govern RNA fusion scope.

## DNA Variant Resolution Framework

The SNV analytics engine utilizes a standardized dual-branch resolver architecture to ensure core algorithmic stability:

- **Germline Branch (`generic_germline`)**: Orchestrates germline-specific filtering logic and dedicated hotspot escape protocols.
- **Somatic Branch (`generic_somatic`)**: Manages somatic-driven thresholds including case/control comparisons and biological consequence prioritization.

Assay groups (e.g., Hematology, Myeloid) utilize these branches either in isolation or through unified logical unions to enforce specific center policies.

## Administrative Configuration Protocol

The administrative interface controls query behavior through validated JSON-based schema editing:

- **Parameter Envelopes**: Core thresholds (depth, frequency, etc.) are managed through structured form interfaces synced to backend Pydantic models.
- **Dynamic Policy Injections**: Direct MongoDB Query JSON enables complex logic overrides for specific assay types without requiring software modifications.
- **Query Operators**: The system permits all standard MongoDB operational syntax (e.g., `$or`, `$and`, `$nor`) allowing for highly nuanced finding prioritization.
- **Gene List Defaults**: ASPC may seed initial defaults when a sample is created or reset, but active sample-level list selection is stored on `samples.filters`.

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
