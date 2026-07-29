# Clinical Data Preparation And Reporting Flow

This guide defines how Coyote3 turns an ingested sample into reviewable
findings, a report preview, and an immutable saved report. It is the
authoritative technical description of the implemented data flow and the
boundary planned for configurable clinical report text.

The intended audience is:

- clinical scientists who need to understand why a finding appears;
- developers who maintain queries, contracts, and reporting;
- administrators who configure ASP, ASPC, and gene lists;
- operators who investigate incomplete ingest or report generation.

!!! info
    Coyote3 stores timestamps in UTC. The UI converts timestamps to the
    deployment's configured local timezone for display.

## 1. Responsibility Model

Reporting is divided into four stages:

| Stage | Owner | Responsibility |
|---|---|---|
| Configuration | ASP, ASPC, and ISGL administration | Defines assay scope, enabled analyses, defaults, report sections, and gene lists |
| Data preparation | Ingest and reporting application services | Validates source files, stores normalized findings, applies filters, resolves annotations, and builds reportable data |
| Text generation | Published clinical rules and report composer | Produces clinical text from the prepared report context |
| Persistence | Report service | Renders preview, writes HTML/PDF, stores report metadata and finding snapshots, and emits audit events |

The stages have strict boundaries. Text generation does not decide which raw
variants pass analytical filters. Persistence does not recompute clinical
interpretation from a saved artifact.

## 2. Configuration Sources

### 2.0 Canonical clinical scope identifiers

`asp_id`, `aspc_id`, `subpanel_id`, and `isgl_id` are persisted join keys. They
use lower-case letters, digits, underscores, and hyphens. The service lowers
case only: accepted separators retain their meaning, so the display label
`Hem-Snabb` has the stored identifier `hem-snabb`. Whitespace, dots, and all
other special characters are rejected rather than silently rewritten.

This convention applies consistently to ASP, ASPC, ISGL, samples, user scope,
static rule directories, and YAML manifests. It prevents a casing or separator
variant from making an otherwise valid ASPC or gene list unreachable.

### 2.1 ASP: physical assay definition

An Assay Specific Panel (ASP) describes the physical test.

| Field | Meaning | Reporting use |
|---|---|---|
| `asp_id` | Stable assay identifier | Links samples and ASPCs to the assay |
| `asp_group` | Clinical grouping | Selects assay-aware annotation context |
| `asp_family` | Panel, WGS, WTS, or related family | Determines physical coverage behavior |
| `asp_category` | `dna` or `rna` | Selects the analysis contract |
| `expected_files` | File types accepted for the assay | Validates declared YAML resources |
| `required_files` | File types always required | Blocks incomplete ingest |
| `covered_genes` | Physically covered genes | Bounds effective gene scope for targeted assays |
| `germline_genes` | Germline-capable genes | Supports germline-aware review and reporting |
| `accredited` | Accreditation status | Supports report metadata and conclusion wording |

ASP data is active configuration. It is updated in place and kept as the
single current first-version document for its `asp_id`; it does not contain
sample-specific results or report text selected for one case. Operational
change history belongs to the audit-event stream.

### 2.2 ASPC: analytical and reporting configuration

An Assay Specific Panel Configuration (ASPC) binds an ASP to one subpanel and
environment. One ASPC carries every enabled analytical intent for that scope;
it is not duplicated solely because the same physical assay supports both
somatic and germline review.

The logical identity is:

```text
ASP + subpanel + environment
```

The `base` subpanel is used when the assay has no specific subpanel
configuration.

| Field | Meaning |
|---|---|
| `aspc_id` | Stable logical configuration identifier |
| `asp_id` | Parent ASP |
| `subpanel_id` | Specific subpanel or `base` |
| `environment` | Production, validation, testing, or development |
| `analysis_types` | Analyses available for sample review |
| `analysis_intents` | `somatic` and, for DNA SNV where configured, `germline`. The value controls the available filter profiles, review tables, and reporting contexts. |
| `reporting.analysis` | Analyses eligible for report preparation |
| `reporting.report_sections` | Sections rendered in a report |
| `filters` | Default analytical filters |
| `reporting.report_header` | Report heading |
| `reporting.report_method` | Method description |
| `reporting.report_description` | Assay description |
| `reporting.general_report_summary` | Configured introductory text |
| Static rule source | Repository-owned YAML selected by `asp_id` and `subpanel_id`; the rendered report records the source identity and content hash. |
| `reporting.plots_path` | Approved source directory for report plots |
| `reporting.report_folder` | Approved report output directory |

`analysis_types`, `reporting.analysis`, and `report_sections` answer different
questions:

- **Available:** can the analysis be reviewed for this configuration?
- **Reportable domain:** may this analysis contribute to a report?
- **Rendered section:** should the report contain this section?

The saved report records the validated YAML source identity and deterministic
content hash together with the resolved ASPC and filter snapshot. This makes
the runtime lineage:

```text
reviewed repository YAML
  -> resolved active ASPC
  -> saved report context and provenance
```

!!! warning
    Current operational reads resolve the exact active ASPC by ASP, subpanel,
    and environment. When a legacy sample has no subpanel-specific ASPC, the
    active `base` ASPC is attached and `samples.aspc_resolution` records the
    requested and resolved subpanel IDs plus an explicit warning. The analysis
    and overview pages display that warning. A saved report preserves the
    resolved ASPC identity and filter snapshot.

### 2.3 ISGL: in-silico gene lists

ISGL documents provide named gene scope. Lists are typed by analysis domain,
for example SNV, CNV, fusion, expression, or PGX.

An applied list does not prove that every listed gene is physically covered.
For targeted assays, Coyote3 intersects the list with `ASP.covered_genes`.
WGS/WTS configurations can treat the list itself as the effective scope.

The prepared report context records:

- selected list identifiers;
- list versions;
- analysis domain in `selected_for`;
- ad-hoc genes;
- effective covered and uncovered genes.

This allows a reviewer to distinguish the requested clinical scope from the
physical assay scope.

DNA rule preparation carries selected SNV and CNV ISGLs. RNA rule preparation
carries selected fusion ISGLs. These are the lists used for that report
preparation, not every list configured for the assay.

## 3. Sample Ingest And Readiness

### 3.1 Manifest and file policy

The sample YAML identifies the sample, `asp_id`, `subpanel_id`, `environment`, pipeline,
case/control relationship, and declared files.

Ingest resolves the active ASP and ASPC before writing the sample. File policy
is evaluated as follows:

1. Every ASP `required_files` entry must be declared and readable.
2. An optional file may be absent from the YAML.
3. If an optional file is declared, it becomes required for that ingest.
4. Every declared file must parse and persist successfully.
5. Every analysis required by the resolved configuration must have the data
   needed by its ingest handler.
6. The sample anchor is made available only after all declared resources and
   required dependent data have completed successfully.

!!! caution
    A partially ingested sample must not appear as ready. Failure must preserve
    enough audit context to identify the sample name, declared resource, parser
    stage, and underlying error without exposing secrets.

### 3.2 Canonical sample anchor

The `samples` document is the operational anchor.

Key fields include:

| Field | Purpose |
|---|---|
| `name` | Human-facing sample identifier and route key |
| `asp_id` | ASP identifier |
| `subpanel_id` | Selected subpanel |
| `environment` | Environment |
| `current_aspc_id` | ASPC ObjectId resolved when sample state was established |
| `current_aspc_key` | ASPC logical identifier recorded on the sample |
| `current_aspc_version` | ASPC version recorded on the sample |
| `aspc_resolution` | Requested and resolved configuration scope. A base fallback sets `used_base_configuration=true` and carries the visible warning text. |
| `omics_layer` | DNA or RNA |
| `platform` | Sequencing platform inherited from the resolved ASP, such as `illumina` or `pacbio` |
| `read_mode` | Platform-supported read mode. It is currently applicable only to Illumina (`SE` or `PE`). |
| `read_technology` | Immutable derived value: `short_read` for Illumina/Ion Torrent and `long_read` for PacBio/Nanopore. It is never entered independently. |
| `paired` | Whether case/control data are present |
| `genome_build` | Reference genome build |
| `database_versions.vep` | VEP version used for annotation |
| `database_versions` | Curated source-version metadata, including the canonical `vep` key |
| `files` | Canonical file metadata by file type |
| `filters` | Current per-domain filter state |
| `case` / `control` | Sample identifiers and laboratory metadata |
| `reported` | Whether at least one report was saved |
| `latest_report_id` | Most recent saved report |
| `latest_report_on` | Most recent report timestamp |

Dependent collections use `sample_id` or `sample_oid` to link findings and
results to the sample anchor. Normal UI URLs use the sample name. Finding
detail routes may additionally use the finding ObjectId because it is the
unambiguous document identity.

### 3.3 File metadata

Each entry under `sample.files` uses:

```json
{
  "path": "/mounted/data/example.vcf",
  "checksum": "optional checksum",
  "size_bytes": 123456,
  "registered_on": "UTC datetime"
}
```

File availability shown in the UI is based on the canonical nested file
contract. A stored path is provenance; it is not a permanent guarantee that
the file still exists. Runtime operations that need the file must check the
mounted path at use time.

## 4. Filter Authority And Effective State

### 4.1 Default state

When no sample-specific filters exist, the application copies the complete
ASPC profile map to the sample. DNA uses the following canonical shape:

```yaml
filters:
  somatic:
    snv: {}
    cnv: {}
    coverage: {}
  germline:
    snv: {}
```

RNA uses:

```yaml
filters:
  somatic:
    fusion: {}
```

Only enabled profiles are stored. `germline` is currently available only for
DNA `SNV`; CNV, coverage, fusion, biomarkers, and RNA remain somatic-only.
The profile keys are a software contract: ASPC and sample documents may set
values, but they cannot add arbitrary filter fields.

### 4.2 Intent-specific review and reporting

The DNA review workspace presents separate tables for each enabled profile:
Somatic SNV and Germline SNV. A filter change updates only the selected
`filters.<intent>.snv` section. It does not overwrite the other intent.

Reporting prepares separate filtered finding sets for somatic and germline
SNVs. Each saved reported-finding snapshot records `analysis_intent`. Static
clinical YAML must contain an explicit `when` condition for
`sample.analysis_intent: germline` before it can produce germline wording.
This prevents a somatic sentence from being applied to germline findings. If
an ASPC enables germline review but the selected rule set provides no germline
text, the preview renders a visible red configuration warning rather than
silently omitting the result.

### 4.2 DNA filter namespaces

| Namespace | Supported settings |
|---|---|
| `filters.somatic.snv` | Depth, alternate reads, case VAF, control VAF, population frequency, VEP groups, SNV lists, ad-hoc genes |
| `filters.germline.snv` | Depth, alternate reads, case VAF, population frequency, VEP groups, SNV lists, ad-hoc genes |
| `filters.somatic.cnv` | Size bounds, gain/loss cutoffs, effects, CNV lists, ad-hoc genes |
| `filters.somatic.coverage` | Warning and error coverage thresholds |

### 4.3 RNA filter namespace

`filters.somatic.fusion` contains caller, effect, gene-list, spanning-pair,
spanning-read, and ad-hoc-gene settings.

### 4.4 Update and reset behavior

- **Apply** validates and persists the new sample filter state.
- A successful update invalidates cached query results for that sample/domain.
- The UI reloads the result set using the new filter state.
- **Reset** restores defaults from the active ASPC resolved for the sample's
  assay, subpanel, and environment.
- Saved reports retain their own filter snapshot and are not changed.

!!! tip
    The table search box filters the already returned table rows. Analytical
    filters in the sidebar change the backend query and therefore change the
    reportable data set.

## 5. Small-Variant Preparation

### 5.1 Query construction

The DNA reporting application builds the SNV query from:

- sample identity;
- case VAF minimum and maximum;
- control VAF maximum;
- depth and alternate-read minimums;
- population-frequency maximum;
- selected VEP consequence groups;
- selected SNV gene lists and ad-hoc genes;
- configured verification positions;
- false-positive and irrelevant exclusions.

VEP groups are resolved using the metadata document for
`sample.database_versions.vep`. A UI group such as `splicing` is expanded to concrete VEP
terms before the query is executed.

### 5.2 Transcript selection

The selected VEP consequence is established before report preparation.
Transcript selection follows the documented preference:

1. NCBI MANE Plus Clinical;
2. Ensembl MANE Plus Clinical;
3. NCBI MANE Select;
4. Ensembl MANE Select;
5. the deterministic configured fallback.

HGNC normalization links current symbols, previous symbols, and aliases to the
same HGNC identity. The original display symbol from the variant is retained;
the UI may indicate that a newer approved symbol exists.

Report-text generation receives the selected consequence. It does not choose a
different transcript.

### 5.3 Annotation identity and matching

The current annotation repository builds these candidate identities:

```text
protein: selected_CSQ.HGVSp
cDNA:    selected_CSQ.HGVSc
genomic: CHROM:POS:REF/ALT
gene:    selected_CSQ.SYMBOL
```

Matching order is:

1. If HGVSp exists, query the same gene for matching protein, cDNA, or genomic
   annotation rows.
2. Otherwise, if HGVSc exists, query the same gene for matching cDNA or genomic
   rows.
3. Otherwise, query the same gene and genomic identity.
4. For breakpoint findings, use the fusion identity
   `breakpoint1^breakpoint2`.

Matching rows are ordered by `time_created`. Iteration therefore leaves the
newest applicable row as the current classification.

### 5.4 Assay and subpanel context

Classification applicability is contextual:

- for the `solid` assay group, both annotation `assay` and `subpanel` must
  match;
- for other assay groups, annotation `assay` must match;
- classifications from other assay/subpanel contexts are retained separately
  for display but do not become the current classification.

Free-text annotations use the same assay/subpanel context. They are available
as global annotation history and as the current assay-specific text.

### 5.5 Reportability

After query and annotation enrichment:

1. blacklist metadata is attached;
2. global annotation and classification are attached;
3. hotspot metadata is hydrated;
4. selected report gene scope is enforced;
5. blacklisted findings are excluded;
6. findings without a classification are excluded;
7. Tier IV and class `999` are excluded;
8. assay-specific tier policy is applied;
9. remaining rows are simplified for report composition;
10. rows are ordered by class and case allele frequency.

The output of this stage is the prepared small-variant list. A report-text
engine must not repeat or override these decisions.

## 6. Other Prepared Data Domains

### 6.1 CNVs

CNVs are prepared only when the ASPC enables the CNV report section.

The application:

1. loads interesting CNVs for the sample;
2. applies configured gain/loss effects;
3. applies selected CNV gene scope;
4. organizes genes for presentation;
5. returns normalized report rows.

CNV classification and report action behavior remain separate from SNV tier
logic.

### 6.2 CNV profile

The CNV profile is an image artifact, not a CNV call and not coverage data.

- The review UI displays it beside the CNV table.
- The report application resolves `sample.files.cnvprofile`.
- The image is encoded and embedded when `CNV_PROFILE` is a report section.
- An image alone does not provide a structured result such as `normal` or
  `complex_abnormal`.

!!! warning
    Clinical text must not match on an interpreted CNV-profile status until a
    typed status, authoritative producer, allowed values, and provenance are
    implemented.

### 6.3 Fusions and translocations

Fusion and translocation rows are prepared from their dedicated collections.
Only sections enabled by ASPC are loaded. Interesting/reportable state and
annotation enrichment are resolved before text composition.

Fusion and translocation matching must use their own typed identities. They
must not be forced through SNV HGVSp/HGVSc matching.

### 6.4 Biomarkers

Biomarker documents provide structured assay results such as:

- MSI single-site and panel values;
- HRD components and summary values;
- other configured biomarker fields.

The report context can carry biomarker data when `BIOMARKER` is enabled.
Visible report text requires an explicit template or a validated clinical text
rule.

!!! caution
    Thresholds, units, and missing-value behavior must be defined before a
    biomarker can drive conditional clinical wording. A workbook label is not
    a machine-readable result.

### 6.5 Coverage

Coverage is DNA quality information. It can be available for review and can be
enabled in ASPC analysis/report settings. Coverage thresholds come from
`filters.coverage`.

Coverage data and CNV profile data are independent and must not share a status
or file key.

## 7. Prepared Report Context

The complete output of data preparation is a versioned report context. It
contains only normalized, report-facing data.

```yaml
context_version: 1

sample:
  oid: "<ObjectId>"
  name: "<sample name>"
  asp_id: "<ASP ID>"
  subpanel_id: "<subpanel or base>"
  environment: "<environment>"
  omics_layer: dna
  paired: true
  genome_build: 38
  database_versions:
    vep: "103"
  case: {}
  control: {}

asp:
  oid: "<ObjectId>"
  asp_id: "<ASP ID>"
  asp_group: "<group>"
  asp_family: "<family>"
  asp_category: dna
  accredited: true

aspc:
  oid: "<ObjectId>"
  aspc_id: "<ASPC ID>"
  version: 3
  analysis_types: [SNV, CNV, BIOMARKER]
  reporting_analysis: [SNV, CNV, BIOMARKER]
  report_sections: [SNV, CNV, BIOMARKER]

applied_gene_scope:
  snv_lists: []
  cnv_lists: []
  fusion_lists: []
  adhoc_genes: {}
  effective_genes:
    snv: []
    cnv: []
    fusion: []

findings:
  small_variants: []
  cnvs: []
  fusions: []
  translocations: []

results:
  biomarkers: []
  coverage: null
  cnv_profile: null

provenance:
  filters_snapshot: {}
  source_counts: {}
  database_versions: {}
  prepared_on: "<UTC datetime>"
```

### 7.1 Contract guarantees

The producer guarantees that:

- findings have passed the current analytical filters;
- gene-list scope has already been applied;
- selected transcripts are final;
- classifications are current for the sample assay/subpanel context;
- excluded clinical states have already been removed;
- enabled and missing domains are distinguishable;
- source and output counts are available for traceability;
- the context is read-only after construction.

### 7.2 Values that must remain distinct

The contract must distinguish:

- `missing`: no source value exists;
- `not_applicable`: the field does not apply;
- `indeterminate`: the assay produced no conclusive result;
- `normal`: a validated result is normal;
- `false`: an explicit boolean result;
- `0`: a measured numeric value.

These values must not be collapsed into an empty string.

## 8. Clinical Text Generation Boundary

Reporting composes report text from the prepared context, ASPC reporting
fields, and the immutable clinical-rule release explicitly bound to the ASPC.
YAML is the editable source; the database release is compiled runtime content.

The evaluator may:

- inspect prepared findings and results;
- calculate deterministic counts and groups;
- select a validated text rule;
- render approved variables into text;
- order text blocks;
- return a trace of matched rules.

The evaluator may not:

- query MongoDB;
- load ASP, ASPC, ISGL, or sample documents;
- apply analytical filters;
- select transcripts;
- normalize genes;
- assign tiers;
- decide false-positive, irrelevant, or blacklist state;
- call external knowledgebases;
- mutate source or report documents.

This separation prevents report wording from changing the clinical data set it
is supposed to describe.

## 9. Preview And Save

### 9.1 Preview

Preview:

1. resolves the active sample configuration by `asp_id`, `subpanel_id`, and
   environment;
2. builds the prepared report context from current filters;
3. composes report text and sections;
4. renders self-contained HTML;
5. optionally renders a review PDF;
6. returns temporary snapshot rows.

Preview does not create `reports` or `reported_variants`.

### 9.2 Save

Save is an explicit, permissioned action. The backend does not trust
client-supplied HTML.

Save:

1. rebuilds and validates the report context;
2. allocates the next report number;
3. verifies artifact paths do not conflict;
4. renders HTML;
5. renders PDF from the same HTML;
6. writes report metadata;
7. updates the sample's latest-report pointer;
8. writes immutable reported-finding snapshots;
9. emits an audit event.

### 9.3 Persisted provenance

A saved report preserves:

- sample and report identity;
- exact filters used;
- ASPC identity and version;
- report artifacts;
- author and UTC creation time;
- per-finding report snapshots;
- selected annotation references;
- data-version context available at creation time.

The report also preserves the static clinical-rule source identity, canonical
content hash, and matched rule IDs. Static YAML is selected by the effective
ASP and subpanel; it is not copied into an ASPC or stored as a MongoDB release.

## 10. Collection Relationships

```text
assay_specific_panels (ASP)
    |
    +-- asp_configs (ASPC)
    |       |
    |       +-- samples.current_aspc_id/version
    |
    +-- insilico_genelists (ISGL)

samples
    |
    +-- variants
    +-- cnvs
    +-- fusions
    +-- translocations
    +-- biomarkers
    +-- sample_comments
    +-- reports
            |
            +-- reported_variants

variants + annotation
    |
    +-- prepared report findings
```

`samples` is the current operational state. `reports` and
`reported_variants` preserve historical clinical output.

## 11. Traceability And Failure Semantics

### 11.1 Required trace data

For each preparation request, operational logs should identify:

- sample name;
- sample ObjectId in structured detail;
- ASP and resolved ASPC identity/version;
- active filter hash or snapshot;
- applied gene-list IDs;
- source and prepared counts by domain;
- omitted domains and reason;
- request ID.

### 11.2 Blocking failures

Report preparation must fail when:

- the sample cannot be resolved;
- the active ASPC cannot be resolved for the sample scope;
- ASP/ASPC/sample scope conflicts;
- a required report domain cannot be loaded;
- a declared critical value has the wrong type or unit;
- an output path is unavailable during save;
- artifact or database persistence fails.

### 11.3 Non-blocking absence

An optional section can be absent only when:

- ASPC does not require it; and
- no file or result was declared for it; and
- the report section contract permits omission.

Absence must remain visible in trace metadata rather than being converted to a
normal result.

## 12. Verification Checklist

Before changing a query, annotation matcher, or report context:

1. Identify the source collection and Pydantic contract.
2. Confirm the field path, type, unit, and missing-value semantics.
3. Confirm ASPC scope and sample filter authority.
4. Add positive, negative, boundary, and missing-input tests.
5. Verify source count, filtered count, and reportable count.
6. Verify preview writes no clinical history.
7. Verify save preserves filter and configuration provenance.
8. Verify historical reports remain unchanged.
9. Update this guide and the relevant user/API reference.

## 13. Related Documentation

- [System relationships](system_relationships.md)
- [Data contracts](data_contracts.md)
- [ASPC-driven query strategy](../product/aspc_driven_query_strategy.md)
- [Reporting workflow and snapshots](../product/reporting_workflow_and_variant_snapshots.md)
- [DNA and RNA workflow](../product/workflow_dna_rna.md)
- [Collection contracts](../api/collection_contracts.md)
- [Sample YAML](../api/sample_yaml.md)
