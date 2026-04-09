# Assay Configuration and Dynamic Query Orchestration

The platform's analytic engine is driven by the Assay-Specific Panel Configuration (ASPC) system—a strictly versioned runtime strategy contract that governs finding retrieval, filtering logic, and clinical review behavior.

## Systematic Logic Hierarchy

The resolution of analytic strategies follows a deterministic inheritance model to ensure consistency across varying center requirements:

1. **ASPC Resolution**: The system derives the primary configuration identity (`aspc_id`) from the sample-level `assay` and `profile` (environment) attributes.
2. **Default Thresholding**: The resolved ASPC provides the baseline analytic thresholds and guardrails (e.g., minimum depth, population frequency limits).
3. **Sample-Level Override**: Specific samples maintain an isolated filter state that can override baseline ASPC defaults while preserving the original configuration integrity.
4. **Query Execution**: The finalized filter set is merged with domain-specific MongoDB query JSON to orchestrate precise retrieval for SNVs, CNVs, Fusions, and Translocations.

## Configuration Domain Interplay

Analytic execution relies on the synchronization of three core architectural pillars:

- **Assay-Specific Panels (ASP)**: Defines the primary assay metadata and the comprehensive physical "universe" of covered genetic regions.
- **Assay-Specific Panel Configuration (ASPC)**: The environment-specific operational strategy governing filtered evidence and reporting constraints.
- **In-Silico Gene Lists (ISGL)**: Managed gene cohorts that dynamically restrict the interpretation scope during clinical review.

The **Effective Gene Scope** utilized across all interpretive views is dynamically computed as the union of ASP coverage, active ISGL selections, and ad-hoc sample-level gene inclusions.

## DNA Variant Resolution Framework

The SNV analytics engine utilizes a standardized dual-branch resolver architecture to ensure core algorithmic stability:

- **Germline Branch (`generic_germline`)**: Orchestrates germline-specific filtering logic and dedicated hotspot escape protocols.
- **Somatic Branch (`generic_somatic`)**: Manages somatic-driven thresholds including case/control comparisons and biological consequence prioritization.

Assay groups (e.g., Hematology, Myeloid) utilize these branches either in isolation or through unified logical unions to enforce specific center policies.

## Administrative Configuration Protocol

The administrative interface enables high-fidelity control over query behavior through validated JSON-based schema editing:

- **Parameter Envelopes**: Core thresholds (depth, frequency, etc.) are managed through structured form interfaces synced to backend Pydantic models.
- **Dynamic Policy Injections**: Direct MongoDB Query JSON enables complex logic overrides for specific assay types without requiring software modifications.
- **Query Operators**: The system permits all standard MongoDB operational syntax (e.g., `$or`, `$and`, `$nor`) allowing for highly nuanced finding prioritization.
- **Gene List Defaults**: ASPC governs the automatic allocation of default ISGL cohorts based on assay environment and clinical sub-panel/diagnosis matching.

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

The platform provides sophisticated diagnosis-driven list allocation. When the `use_diagnosis_genelist` protocol is active, the system automatically resolves and attaches ISGL gene cohorts where the genelist's clinical definition aligns with the sample's sub-panel context, ensuring immediate diagnostic relevance upon sample initialization.
