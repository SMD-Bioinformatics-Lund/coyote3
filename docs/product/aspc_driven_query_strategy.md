# Assay Configuration and Dynamic Query Orchestration

The platform's analytic engine is driven by the Assay-Specific Panel
Configuration (ASPC) system. An ASPC is the current operational strategy for
one assay, subpanel, and environment scope. It governs finding retrieval,
filtering logic, and clinical review behavior. Configuration mutations are
audited, while saved reports preserve immutable configuration, filter,
finding, and rule snapshots for reproducibility.

![Sample analysis and query resolution](../assets/diagrams/sample_analysis_resolution.svg)

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

## Analysis Availability and Tab Dispatch

The sample workspace does not infer available analyses from a file name alone.
The ASPC revision recorded on the sample is the source of truth for which
analytical workflows are enabled. A tab is rendered only when all of the following are true:

1. The recorded ASPC revision's `analysis_types` includes the relevant analysis type.
2. The sample has the matching declared and ingested resource, represented by a
   `files` entry or an analysis count.
3. The sample modality supports the workflow.
4. Where applicable, the sample has the required analysis intent.

| Workspace tab | ASPC analysis type | Sample modality and data requirement | Additional condition | Endpoint requested only after opening the tab |
| --- | --- | --- | --- | --- |
| Somatic SNVs | `SNV` | DNA sample with `files.vcf_files` or an SNV count | `analysis_intents` contains `somatic` | `GET /samples/{sample_name}/small-variants?intent=somatic` |
| Germline SNVs | `SNV` | DNA sample with `files.vcf_files` or an SNV count | `analysis_intents` contains `germline` | `GET /samples/{sample_name}/small-variants?intent=germline` |
| CNVs | `CNV` | DNA sample with `files.cnv` or a CNV count | Somatic CNV is the currently supported intent | `GET /samples/{sample_name}/cnvs` |
| Translocations | `TRANSLOCATION` | DNA sample with `files.transloc` or a translocation count | DNA structural-variant workflow | `GET /samples/{sample_name}/translocations` |
| Coverage | `COVERAGE` | DNA sample with `files.cov` or coverage state | Quality workflow, not a variant intent | `GET /samples/{sample_name}/coverage` |
| Fusions | `FUSION` | RNA sample with `files.fusion_files` or a fusion count | RNA fusion workflow | `GET /samples/{sample_name}/fusions` |
| Expression | `EXPRESSION` | RNA sample with `files.expression_path` or expression state | Appears in the shared **Expression & Classification** tab | `GET /samples/{sample_name}/rna-analysis` |
| Classification | `CLASSIFICATION` | RNA sample with `files.classification_path` or classification state | Appears in the shared **Expression & Classification** tab | `GET /samples/{sample_name}/rna-analysis` |
| RNA quality | `QC` | RNA sample with an RNA quality resource or quality state | Returned with the shared RNA-analysis payload; it has no separate workspace tab | `GET /samples/{sample_name}/rna-analysis` when the shared tab is available |
| PGX | `PGX` | Not applicable to the current sample-review workspace | PGX configuration can be recorded, but a PGX review tab, query workflow, and report section are not implemented | No sample-workspace endpoint is requested |

`Overview` and `Reports` are workspace tabs rather than analysis-type tabs.
They remain available as part of the sample workflow. A DNA sample never
exposes the RNA fusion tab. The RNA fusion API also validates the modality and
returns a client-visible configuration error if it is called for a non-RNA
sample; it does not attempt to interpret DNA filter profiles as RNA filters.

!!! important
    Hidden tabs are not mounted in the React tree. This prevents background
    requests for analyses that are unavailable for the sample. A sample page
    opened on the overview tab therefore does not query SNVs, CNVs,
    translocations, coverage, fusions, expression, classification, or RNA
    quality until the user opens the relevant available tab.

!!! info "RNA expression and classification share one workspace"
    The shared RNA tab is shown when either `EXPRESSION` or `CLASSIFICATION`
    is enabled and the corresponding result is present. It can therefore show
    expression only, classification only, or both. A missing tab means the
    sample does not have an enabled and ingested RNA analysis; it does not mean
    that an enabled analysis returned zero rows.

!!! note "PGX is not yet a sample-review workflow"
    `PGX` is a valid configuration analysis type, but it currently has no
    sample-detail tab, filter form, table query, or report renderer. Enabling
    it in an ASPC does not cause the client to request a PGX endpoint. This is
    deliberately explicit so configuration does not imply an implemented
    clinical workflow.

### Intent-specific SNV review

Somatic and germline SNVs use the same underlying VCF-derived collection but
are separate analytical views. Their filter profiles, result queries, table
state, comment suggestions, and report contexts are intent-specific:

```text
filters.somatic.snv  -> somatic SNV tab and report section
filters.germline.snv -> germline SNV tab and report section
```

Germline SNVs are displayed only after the ASPC enables germline intent and
the sample persists that intent. The application never manufactures a
germline profile from somatic thresholds. This prevents a UI label from
implying that germline interpretation was configured when it was not.

## Configuration Domain Interplay

Analytic execution relies on the synchronization of three core architectural pillars:

- **Assay-Specific Panels (ASP)**: Defines assay metadata and the physical set of covered genes or regions.
- **Assay-Specific Panel Configuration (ASPC)**: The
  assay/subpanel/environment-specific operational strategy governing filtered
  evidence and reporting constraints.
- **In-Silico Gene Lists (ISGL)**: Managed gene cohorts that dynamically restrict the interpretation scope during clinical review.

The **Effective Gene Scope** is target-specific:

- **SNV**: only IDs selected in `snv.snvlists`, plus SNV ad-hoc genes, can narrow the SNV scope.
- **CNV**: only IDs selected in `cnv.cnvlists`, plus CNV ad-hoc genes, can narrow the CNV scope.
- **RNA fusion**: only IDs selected in `fusion.fusionlists`, plus fusion ad-hoc genes, can narrow the fusion scope.

An ISGL may declare more than one `list_type`. For example,
`["snv", "cnv", "fusion"]` makes the same curated list available in all three
selectors. It does not apply the list to all three analyses. Application is
controlled exclusively by the ID saved in the corresponding target-specific
selection field.

When an analysis has no selected ISGL or ad-hoc genes, the query uses
`ASP.covered_genes` as its physical assay scope. If `covered_genes` is empty,
the query has no gene predicate and therefore includes all genes. This is the
intended representation for broad WGS and WTS designs.

## Clinical Query Policy

The application separates **configuration** from **clinical query policy**.
This is intentional. An ASPC gives a sample its approved thresholds, enabled
analysis sections, intent profiles, and default gene-list selections. It does
not accept arbitrary MongoDB query fragments. The domain query builder owns
the fixed predicate shape and the limited set of validated clinical exceptions.

For SNV, the ordinary query is built from the resolved sample filters and the
selected `paired`, `case_only`, or `exception_only` evidence model. CNV, DNA
translocation, and RNA fusion each retain their own ordinary ASPC-driven query
and consume only the exceptions in their matching policy namespace. PGX also
has a separate typed namespace, reserved for its future persisted finding
query. Rules never cross analysis boundaries.

| Concern | Source | Purpose |
| --- | --- | --- |
| Basic SNV filter values | `samples.filters.<intent>.snv`, initially seeded from the recorded ASPC revision | Supplies VAF, depth, alternate-read, control-frequency, population-frequency, consequence, ISGL, and ad-hoc gene values for this sample. |
| Baseline evidence model | `[snv]` and optional `[snv.assay_group_policies]` | Determines whether the basic values are evaluated as `paired`, `case_only`, or `exception_only` evidence. |
| Additional clinical rules | `[[snv.exceptions]]` | Extends a consequence route, admits a specifically approved finding under an exception-only policy, or excludes a precisely matched finding. |
| CNV exceptions | `[[cnv.exceptions]]` | Adds a typed CNV admission or exclusion using CNV genes, callers, effects, chromosome, or size. |
| DNA translocation exceptions | `[[translocation.exceptions]]` | Extends or excludes the DNA translocation gene scope using genes, pairs, structural types, or chromosomes. |
| RNA fusion exceptions | `[[fusion.exceptions]]` | Adds or removes RNA fusions using partners, callers, effects, or evidence-description tokens. |
| PGX policy boundary | `[pgx]` | Prevents PGX rules from being encoded as SNV rules; execution begins only with a released persisted PGX finding workflow. |

Therefore, most findings are governed entirely by the basic SNV filters. A
query-policy exception affects a finding only when its intent, assay scope,
and every configured match condition apply.

| Layer | Source | Controls | Does not control |
| --- | --- | --- | --- |
| Assay identity | ASP and sample | `asp_id`, assay group, omics layer, covered scope | MongoDB operators or ad-hoc exceptions |
| Review configuration | Sample's recorded ASPC revision | enabled analysis types, somatic/germline filter defaults, reporting sections | arbitrary data-store predicates |
| Per-sample review state | `samples.filters` | reviewer-selected ISGLs, ad-hoc genes, and permitted threshold changes | assay-group policy |
| Versioned annotation metadata | VEP metadata referenced by `sample.database_versions.vep` | expansion of UI consequence groups to VEP terms | query threshold values |
| Clinical query policy | `api/config/center/clinical_query_policy.toml` plus domain-core Python | released SNV evidence models and analysis-specific typed exceptions | raw MongoDB fields, operators, arbitrary query fragments, or cross-analysis keys |

This design prevents an administrative form from broadening a clinical query by
storing raw operators in MongoDB. A change to query semantics requires code
review, unit tests, documented expected result changes, and a released
application version.

### SNV Query Inputs

For every small-variant request, the application loads the sample's recorded
ASPC revision and its persisted filter profile without overwriting a reviewer's
saved filters. The resulting inputs are shown below.

| Input | Source | Effect on the query |
| --- | --- | --- |
| `intent` | selected workspace tab | selects `somatic` or `germline` SNV profile; germline is accepted only if the sample declares it |
| `min_freq`, `max_freq` | `filters.<intent>.snv` | case allele-frequency bounds for somatic and case-only policies |
| `min_depth`, `min_alt_reads` | `filters.<intent>.snv` | minimum evidence for accepted case genotypes |
| `max_control_freq` | `filters.somatic.snv` | maximum paired-control allele frequency; absence of a control genotype is allowed |
| `max_popfreq` | `filters.somatic.snv` | maximum numeric value across each configured population-frequency source; string, null, and absent source values remain eligible because they are not safely comparable numeric values |
| `vep_consequences` | selected profile plus versioned VEP metadata | UI groups are expanded to stored VEP consequence terms |
| selected SNV ISGLs and ad-hoc genes | `filters.<intent>.snv` | optional gene or explicit-position scope |
| `fp`, `irrelevant` | request-level review controls | further restrict results to the requested review status |

### Review Visibility and Report Eligibility

Clinical review and report preparation have different purposes. A reviewer
must be able to inspect findings previously marked false positive or
irrelevant, including the reason for that decision. A clinical report must not
silently include either class of finding.

| Finding state | Clinical-analysis tables | Report preparation |
| --- | --- | --- |
| `fp = true` | Visible by default. Selecting the false-positive review control adds an explicit status predicate; clearing it returns the normal review set. | Excluded before report rows, summaries, and reporting-text rules are prepared. |
| `irrelevant = true` | Visible by default. Selecting the irrelevant review control adds an explicit status predicate; clearing it returns the normal review set. | Excluded before report rows, summaries, and reporting-text rules are prepared. |
| Neither state | Visible when it satisfies the analytical query. | Remains eligible for the report only when it also meets that report workflow's classification, tier, blacklist, and section rules. |

This separation is intentional: `fp` and `irrelevant` are review states, not
default analytical exclusion predicates. The report workflow applies its
exclusion before invoking the reporting rules engine, so a YAML template never
receives false-positive or irrelevant findings as reportable evidence.

### SNV Baseline Semantics

The somatic baseline requires all of the following:

1. A `case` genotype with allele frequency within the configured range,
   depth at or above `min_depth`, and alternate reads at or above
   `min_alt_reads`.
2. A paired control at or below `max_control_freq` with sufficient depth, or
   no control genotype in the document.
3. Every configured numeric population-frequency source is at or below
   `max_popfreq`. A source value that is absent, null, or non-numeric remains
   eligible because it cannot be safely compared numerically.
4. A configured consequence term in `variants.consequence_terms`, the complete
   term union captured from all VEP transcript consequences during ingest.
5. Any selected gene, selected coordinate, false-positive, or irrelevant
   constraint requested by the reviewer.

The SNV query reads only `variants.consequence_terms`. Alternate transcript
annotations are held in the versioned VEP annotation collection and are used
for transcript inspection and explicit transcript selection, not as a hidden
second query source. The queryable consequence index is derived once from that
complete transcript set at ingest and stored on the compact variant row. This
keeps filtering independent of a reviewer changing the selected display
transcript.

### Released SNV policies and exceptions

`clinical_query_policy.toml` is a released clinical configuration asset. It is
reviewed and deployed with the application, but it is intentionally not stored
in ASPC and cannot contain arbitrary MongoDB syntax. The application supports
only the following baseline policies:

| Policy | Required evidence | Population frequencies | Control evidence | Intended use |
| --- | --- | --- | --- | --- |
| `paired` | labelled case genotype, configured VAF/depth/alternate-read thresholds, and an indexed VEP consequence term | every configured source must pass | required when a control exists; absent control is allowed | default somatic policy |
| `case_only` | labelled or untyped case evidence and an indexed VEP consequence term | every configured source must pass | deliberately not evaluated | validated assays without a matched control |
| `exception_only` | a released `admit` exception | not implied | not implied | current germline admission policy |

| Rule ID | Scope | Mode | Admission condition |
| --- | --- | --- | --- |
| `flt3_svtype` | somatic hematology or myeloid | `extend_consequence` | selected gene `FLT3` and `INFO.SVTYPE` exists |
| `flt3_large_insertion` | somatic hematology or myeloid | `extend_consequence` | selected gene `FLT3` and ALT matches the released large-insertion pattern |
| `solid_regulatory_tert_nfkbie` | somatic solid | `extend_consequence` | selected gene `TERT` or `NFKBIE` with an indexed regulatory/TF-binding consequence |
| `germline_myeloid_marker` | germline DNA | `admit` | `INFO.MYELOID_GERMLINE = 1` |
| `germline_cebpa_filter` | germline DNA | `admit` | selected gene `CEBPA` and `FILTER` contains `GERMLINE` |
| `germline_chr1_interval` | germline DNA | `admit` | chromosome 1 with position in the released interval |

`extend_consequence` retains the complete baseline evidence model and adds a
clinically approved alternative to the indexed consequence branch. `admit` is
used only by an `exception_only` policy. `exclude` uses the same typed match
conditions but removes the matching subset after baseline and admission rules
are applied. A scope with no matching `admit` rule produces an intentionally
empty result set; it never falls back to an unfiltered query.

#### Adding a scoped exception

An exception can be limited to one or more `assay_groups`, `asp_ids`, or
`subpanel_ids`, and can target a gene, indexed consequence term, VCF filter value,
chromosome/position interval, exact `simple_id`, declared `INFO` field, or ALT
pattern. All supplied match fields are combined with AND. The configuration
author selects `extend_consequence` only when the standard evidence gates must
remain in force; use `admit` only for an explicitly approved alternative
admission policy.

```toml
[[snv.exceptions]]
id = "endometrial_specific_variant"
mode = "extend_consequence"
intents = ["somatic"]
asp_ids = ["solid_gmsv3"]
subpanel_ids = ["endometrie"]
simple_ids = ["17_7674220_C_T"]
consequence_terms = ["missense_variant"]
```

The example does not bypass VAF, depth, control, or population-frequency
checks. It only adds the listed consequence-term admission branch for the
released ASP/subpanel scope.

Exception entries are evaluated as additive query branches. Their order has no
effect on the returned findings, so query-policy exceptions intentionally do
not use a `priority` field. TOML order is only for human readability and
diagnostic output, not clinical or query behavior. This differs from
reporting-text rules, where priority determines which matching template is
rendered first.

### Worked query examples

These examples describe the resulting query behavior. They use the released
typed policy vocabulary; no example represents raw MongoDB syntax.

| Scenario | Configuration and request state | Result |
| --- | --- | --- |
| Standard paired somatic SNV review | The resolved policy is `paired`; the sample has a case genotype, a passing paired control when one is stored, and numeric configured population frequencies at or below `max_popfreq`. | The finding is eligible only when its depth, alternate reads, case VAF, population frequencies, and indexed consequence term all pass. |
| Approved alternative consequence | A somatic `solid` sample matches an `extend_consequence` exception for `TERT` with `regulatory_region_variant`. | The added consequence term is accepted, but all ordinary case, control, depth, VAF, and population-frequency gates still apply. |
| Germline exception-only review | The requested intent is `germline`; the policy is `exception_only`; an `admit` exception matches `INFO.MYELOID_GERMLINE = 1`. | The matching finding is admitted through the released germline rule. Findings without a matching `admit` rule are not returned. |
| Reviewed exclusion | A finding first meets the baseline or an admission branch, then matches an `exclude` exception such as a scoped `LOWQUAL` rule. | The finding is removed after the inclusion branches are combined. Other findings remain eligible. |
| No selected list | The target-specific ISGL selector and ad-hoc genes are empty. | The query uses `ASP.covered_genes`; when that field is empty, no gene predicate is added. |
| Selected CNV or fusion list | A compatible ISGL ID is persisted in `filters.somatic.cnv.cnvlists` or `filters.somatic.fusion.fusionlists`. | Only that target-specific list narrows the result. An SNV list never narrows CNV or fusion results. |

### Analysis-specific query-policy blocks

The only authorable clinical query-policy document is
`api/config/center/clinical_query_policy.toml`. It does **not** contain sample
documents, ASPC filters, selected ISGLs, UI tabs, or request parameters. Those
values are persisted and resolved at runtime. The policy file supplies the SNV
evidence model and narrowly typed, analysis-specific exception branches under
`snv`, `cnv`, `translocation`, `fusion`, and `pgx`. A rule written under one
namespace cannot affect another analysis.

!!! important "Use the configuration reference when editing this file"

    This strategy guide explains how the query policy affects retrieval. The
    authoritative authoring contract is the
    [Center Configuration Reference](../operations/center_configuration_files.md#clinical_query_policytoml).
    Consult that reference before changing the TOML file. It defines every
    permitted block heading and key, required fields, allowed values, bracket
    syntax, condition-combination rules, compatible policy and exception
    modes, validation failures, complete examples, and the safe release
    protocol.

TOML block punctuation is part of the contract. `[snv]` and
`[snv.assay_group_policies]` are single named tables. Each
`[[snv.exceptions]]` declaration appends one independent exception to an
array, which is why it uses double brackets. A following
`[snv.exceptions.info_equals]` table is a single nested mapping attached to
that exception; it must appear before the next `[[snv.exceptions]]` entry.

Within an exception, separate scope and match keys are combined with AND.
Most arrays mean OR within that field, such as either listed gene or either
listed consequence. `info_fields_present` is intentionally stricter: every
listed INFO field must exist. Every entry in `info_equals` must also match.
Separate inclusion exceptions are additive OR branches, while a match against
any applicable `exclude` exception removes the finding last.

The following is a complete, valid policy shape. The exception identifiers and
clinical scopes are examples; they must be replaced with clinically approved
content before release.

```toml
[snv]
default_somatic_policy = "paired"
default_germline_policy = "exception_only"
population_frequency_fields = [
  "gnomad_frequency",
  "gnomad_max",
  "exac_frequency",
  "thousandG_frequency",
]

[cnv]

[translocation]

[fusion]

[pgx]

# Extends only the consequence branch. Baseline case, control, and population
# evidence still applies.
[[snv.exceptions]]
id = "hematology_flt3_svtype"
mode = "extend_consequence"
intents = ["somatic"]
assay_groups = ["hematology", "myeloid"]
genes = ["FLT3"]
info_fields_present = ["SVTYPE"]

# Alternative admission for the exception-only germline policy.
[[snv.exceptions]]
id = "germline_myeloid_marker"
mode = "admit"
intents = ["germline"]

[snv.exceptions.info_equals]
MYELOID_GERMLINE = 1

# Final exclusion after baseline and admission branches have been combined.
[[snv.exceptions]]
id = "solid_lowqual_exclusion"
mode = "exclude"
intents = ["somatic"]
assay_groups = ["solid"]
filter_values = ["LOWQUAL"]
```

An assay-group override is optional and is written as a separate table. The
following demonstrates the syntax; add such an override only when the assay
group has a reviewed evidence model that differs from the default:

```toml
[snv.assay_group_policies]
solid = "case_only"
```

This example changes only how somatic SNV evidence is combined for the
`solid` assay group. It does not create thresholds and does not alter CNV,
fusion, translocation, expression, classification, coverage, or reporting
queries. CNV, translocation, and fusion exceptions must be declared in their
own namespaces as documented in the center configuration reference.

| Policy block | What it authorizes | Resulting query behavior |
| --- | --- | --- |
| `[snv]` | The baseline somatic and germline policies plus stored population-frequency fields. | A somatic request uses `paired` unless an assay-group override applies. A germline request has no results unless an `admit` branch matches, because its policy is `exception_only`. |
| `[snv.assay_group_policies]` | A different baseline for one normalized, software-defined assay group. | A `case_only` override omits paired-control evaluation for that group's somatic SNVs; case evidence, population-frequency, consequence, and gene-scope gates still apply. When the table is absent, every somatic assay group uses `default_somatic_policy`. |
| `mode = "extend_consequence"` | One additional clinically approved consequence route. | The FLT3 branch accepts its approved condition in the consequence part of the baseline without relaxing VAF, depth, alternate-read, control, or population-frequency checks. |
| `mode = "admit"` | An explicit alternative inclusion route. | The germline marker is included only when `INFO.MYELOID_GERMLINE` equals `1`. It is not a fallback to an unfiltered germline query. |
| `mode = "exclude"` | A final, scoped removal rule. | A solid somatic finding with `LOWQUAL` is removed even when it previously matched the baseline or an `admit` branch. |

The exception mode must match the resolved baseline policy. `paired` and
`case_only` use `extend_consequence`; `exception_only` uses `admit`; all three
use `exclude`. An `admit` entry under a paired or case-only request, or an
`extend_consequence` entry under an exception-only request, is valid TOML but
does not participate in that query. The configuration review must therefore
verify both syntax and policy compatibility.

At evaluation time, `paired` and `case_only` policies evaluate their baseline
evidence model and may add matching `extend_consequence` branches to its
consequence gate. An `exception_only` policy evaluates only its matching
`admit` branches. Any matching `exclude` branch is subtracted last. This
ordering is fixed in code; TOML order never changes which findings are
returned.

!!! important "Policy exceptions do not replace ASPC configuration"

    ASPC `analysis_types` determine which sample workspace tabs are available.
    `samples.filters` determines thresholds, selected ISGLs, ad-hoc genes, and
    review-state controls for an individual sample. The query-policy file can
    add only the documented typed admissions and exclusions for SNV, CNV, DNA
    translocation, and RNA fusion. It cannot enable an analysis, define an ASPC
    threshold, select a gene list, configure expression, classification, or
    coverage retrieval, or supply raw MongoDB predicates. The `pgx` namespace
    is validated but remains non-executable until the application has a
    persisted PGX finding workflow.

For configuration changes, use the linked center reference as the source of
truth rather than deriving syntax from the abbreviated examples on this page.

!!! caution "Clinical review requirement"

    An exception changes clinical finding visibility. Add a precise biological
    rationale, representative fixtures, before/after result counts, expected
    report impact, and unit tests. Do not encode query fragments in ASPC, ISGL,
    or the user interface.

### CNV, Translocation, and Fusion Queries

| Analysis | Filter and policy source | Retrieval behavior | Post-query processing |
| --- | --- | --- | --- |
| CNV | `filters.somatic.cnv`, selected CNV ISGLs, and `[[cnv.exceptions]]` | Uses two evidence branches. Ratio-based calls use strict loss/gain and minimum/maximum size boundaries; a ratio above `3` retains a high-level amplification beyond the size ceiling. Ratio-less structural calls are retained when `SR` or `PR` evidence is present, so callers such as Manta are not removed by segment-ratio rules. Optional CNV gene scope is applied independently of SNV lists. Targeted-panel review excludes `NORMAL` records; WGS/TumWGS review includes them. A scoped `admit` exception extends this ordinary query; a scoped `exclude` exception is subtracted last. | configured gain/loss effect selection, structural evidence retention, WGS normal-call scope, policy exclusions, and gene organisation are applied before search, sort, and pagination |
| DNA fusion/translocation | `filters.somatic.translocation`, independently selected fusion-compatible ISGLs, and `[[translocation.exceptions]]` | Retrieves records for the sample, then applies the resolved DNA structural gene scope. A selected list or ad-hoc scope is used first; otherwise the query falls back to `ASP.covered_genes`; an empty ASP coverage list leaves the result unrestricted. Admissions can add reviewed genes or exact partner pairs to a restricted scope; exclusions remove matching genes, pairs, structural types, or chromosomes. | gene and pair matching, policy exclusions, text search, multi-column sorting, pagination, annotation, and review-state enrichment |
| RNA fusion | `filters.somatic.fusion`, selected fusion ISGLs, and `[[fusion.exceptions]]` | RNA-only. Applies configured supporting-read/pair thresholds, selected effects, selected callers, known/Mitelman list markers, and optional fusion-gene scope. The Arriba caller intentionally has no spanning-pair predicate. Admissions extend the ordinary query with a typed partner, pair, caller, effect, or description rule; exclusions are subtracted last. | global annotation enrichment, policy exclusions, text search, multi-column sorting, pagination, and report summary preparation |

DNA translocation records do not currently have validated cross-caller numeric
thresholds equivalent to RNA spanning-read filters. The old production query
also retrieved these records by sample identity. The supported DNA filter is
therefore the typed, target-specific gene scope. If a future caller contract
introduces evidence thresholds, each threshold must be added to the typed ASPC
and sample schema, query implementation, UI schema, documentation, and tests
before it can affect finding visibility.

## Query Execution Protocol

Each table request follows the same ordered protocol. Sorting and pagination
operate on the complete filtered result set, not only on the rows already
visible in the browser.

1. Load the sample's recorded ASPC revision. New samples receive the active
   ASPC resolved from `asp_id`, `subpanel_id`, and `environment` at ingest;
   `base` is used only through the documented subpanel fallback. A reviewer may
   explicitly replace the recorded revision with the latest active revision.
2. Confirm that the requested analysis is enabled by the recorded ASPC revision, declared on the
   sample, and compatible with its omics layer.
3. Select the requested intent and canonical target filter section.
4. Use the persisted sample filter profile without replacing reviewer changes.
5. Resolve selected ISGLs and ad-hoc genes into the target-specific effective
   gene scope.
6. For SNVs, expand selected VEP consequence groups using the exact VEP
   version stored on the sample.
7. Build the fixed query policy from the typed inputs and the assay-group
   branch documented above.
8. Retrieve matching findings and enrich them with annotation, classification,
   and review state.
9. Apply submitted text search and all requested sort columns to the complete
   filtered result set.
10. Paginate the sorted results and return the page, total count, query state,
    and filter state.

The client serializes the relevant query state into the URL: page, page size,
text search, ordered sort columns, and SNV intent. React Query caches results
by this state. Revisiting an unchanged query uses cached data; changing a
filter, classification, flag, or selected gene list invalidates the affected
sample-domain query keys and requests fresh MongoDB results.

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

## Diagnosis-Based Gene-List Selection

When `use_diagnosis_genelist` is enabled, the application compares the sample
diagnosis and subpanel context with eligible ISGL definitions. Matching lists
can then be attached when the sample is initialized or its gene-list selection
is reset. The selected list identifiers are stored with the sample context so
that filtering and report generation use the same gene scope.
