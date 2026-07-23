# Clinical Reporting Rules

Coyote3 produces clinical report wording from YAML rule sets. A rule set is a
complete definition for one assay and one subpanel. It receives the prepared
report result: filtered SNVs, CNVs, fusions, translocations, biomarkers, assay
definition, assay configuration, and the applied gene lists. It then selects
the matching text and renders it without changing the underlying result.

This keeps clinical wording and clinical conditions out of assay-specific
Python code. Python provides one generic evaluator; the YAML files define what
each assay and subpanel says.

!!! info
    The rule engine does not decide whether a finding is reportable. Filtering,
    transcript selection, classification, false-positive and blacklist state,
    selected gene lists, and report inclusion are resolved before rules run.

## Rule Files

Rule files have one fixed layout:

```text
clinical_reporting_rules/
  <asp_id>/
    <subpanel_id>.yaml
```

Examples:

```text
clinical_reporting_rules/
  hema_GMSv1/
    base.yaml
  solid_GMSv3/
    base.yaml
    endometrie.yaml
  fusion/
    base.yaml
```

The directory is the ASP `asp_id`. The filename is the ASPC `subpanel_id`.
`base` is used when an assay has no subpanel-specific configuration. A file is
complete for its own assay/subpanel; Coyote3 does not merge a base file into a
subpanel file. This makes a review of one file sufficient to understand the
report text for that configuration.

Rule files are not environment-specific. Development, test, and production
ASPCs may use the same immutable release when they require the same clinical
wording.

## Authored YAML Contract

Every rule file has only the fields needed to identify and evaluate clinical
rules:

```yaml
rule_set:
  analyte: dna
  assay_id: solid_GMSv3
  subpanel_id: endometrie
  version: "1"

rules:
  - rule_id: endometrie_tp53
    family: finding_text
    section: Molekylärgenetiska fynd
    priority: 20
    when:
      - fact: finding.gene
        operator: eq
        value: TP53
    template: |-
      <approved clinical text>
    heading: true
    stop: true

deferred_rules: []
```

| Field | Purpose |
|---|---|
| `analyte` | `dna` or `rna`; must match the sample and ASPC. |
| `assay_id` | Exact ASP identifier. |
| `subpanel_id` | Exact ASPC subpanel identifier, or `base`. |
| `version` | Increment when executable logic or clinical wording changes. |
| `rule_id` | Stable identifier for one rule. |
| `family` | Evaluation phase: `finding_text`, `result_text`, or `summary_text`. |
| `section` | Report section receiving the rendered text. |
| `priority` | Lower values are evaluated first within a family. |
| `when` | AND-combined conditions. An empty list always matches. |
| `template` | Exact clinical wording, rendered with the approved report facts. |
| `heading` | Controls whether the section heading is written. |
| `stop` | Stops lower-priority rules for the same candidate after a match. |

The shared Swedish Tier-summary grammar is implemented once in the reporting
formatter. Rules use `{{ aggregates.tier_summaries | tier_summary }}`. The
formatter uses the clinical wording `mutation` and `mutationer`; it does not
change reportable findings or classification, only the prepared Tier summary.

The runtime rule-set identity is derived internally as
`<assay_id>__<subpanel_id>`. It is not authored in YAML. Release hash,
publication time, publisher, database identifier, and lifecycle state are also
managed by the application rather than copied into every rule file.

!!! caution
    A change to a template, a condition, or the priority is a clinical rule
    change. Increment `version`, add exact-output tests, review the generated
    report, then publish a new release.

## Conditions And Report Facts

Every condition is an explicit predicate over a registered prepared fact:

```yaml
when:
  - fact: finding.tier
    operator: in
    value: [1, 2]
  - fact: finding.gene
    operator: eq
    value: TP53
```

All entries in `when` must match. Supported operators are:

| Operator | Meaning |
|---|---|
| `eq`, `ne` | Equal or not equal. |
| `in`, `not_in` | Value membership in a YAML list. |
| `contains` | A string or collection contains a value. |
| `overlaps` | Two collections have at least one shared value. |
| `exists` | A fact is present (`true`) or absent (`false`). |
| `gt`, `gte`, `lt`, `lte` | Numeric or ordered comparisons. |

The report-preparation service provides these fact roots to conditions and
templates:

| Root | Contents |
|---|---|
| `sample` | Sample identity, assay, subpanel, profile, and report context. |
| `asp` | Assay definition and assay-level metadata, including configured germline genes. |
| `aspc` | The active assay configuration used for this report, including its approved base report introduction. |
| `applied_gene_lists` | Exact selected ISGLs and their analysis-domain use. |
| `finding` | One normalized reportable SNV, CNV, fusion, or translocation. |
| `biomarkers` | Prepared biomarker result records. |
| `aggregates` | Counts, tier summaries, and report-level booleans. |

Relevant finding fields include `kind`, `gene`, `genes`, `tier`, `hgvsc`,
`hgvsp`, `consequence`, `exon`, `intron`, `case_vaf`, `case_vaf_percent`,
`control_vaf`, `control_vaf_percent`, `variant_type`, `cnv_effect`, and fusion
partners. Transcript selection and HGNC normalization are complete before a
finding reaches this engine; YAML rules do not select transcripts or rename
genes.

The shared `dna_report_intro` formatter renders
`aspc.reporting.general_report_summary`, the paired-control statement, selected
SNV ISGL identifiers, effective SNV gene count, and germline statement from
prepared facts. For example, a selected `hematology_myeloid` list is rendered
as `HEMATOLOGY_MYELOID`; the formatter does not infer a list from assay or
subpanel identity.

Templates run in a restricted Jinja environment. They can only read the roots
listed above. They cannot execute Python, access MongoDB, call external
services, or change report data.

## Evaluation Protocol

For a report preview or save operation, Coyote3 performs this sequence:

1. Resolve the sample, ASP, active ASPC, selected ISGLs, and enabled analyses.
2. Build filtered report candidates from SNVs, CNVs, fusions, translocations,
   and biomarkers.
3. Apply clinical state already persisted on each candidate, including tier,
   false-positive, blacklist, irrelevant, and report decisions.
4. Select the ASPC-bound immutable rule release.
5. Confirm that its analyte, assay, and subpanel match the prepared context.
6. Evaluate `finding_text` rules for each prepared finding.
7. Evaluate `result_text` rules once for the complete report result.
8. Evaluate `summary_text` rules after result text.
9. Within each family, evaluate priorities from low to high, render every
   matching rule, and honour `stop: true` for that candidate.
10. Return the rendered sections and a rule-evaluation trace to the preview or
    report-save workflow.

The same prepared context is used by preview and save. Saving a report stores
the filter snapshot, ASPC snapshot, reportable finding snapshots, and exact
rule release reference. Later changes to YAML do not alter an existing report.

## Deferred Clinical Text

`deferred_rules` is used only when exact wording is known but the application
does not yet expose a safe typed fact for its condition:

```yaml
deferred_rules:
  - rule_id: endometrie_msi_high
    template: |-
      <approved text>
    required_fact_contract:
      - Interpreted MSI result with an approved enumeration.
      - The validated method and result source.
```

Deferred rules are retained with the release but are never evaluated. To make
one executable, first add the missing clinical data contract and its source to
report preparation, then move the rule into `rules` with explicit conditions
and tests. This prevents human shorthand such as an informal interpretation of
MSI or a genomic region nickname from becoming an unreliable database key.

## Publishing And ASPC Binding

YAML is the editable source. MongoDB stores immutable compiled releases for
runtime use and historical reproducibility. Publishing is explicit; application
startup never silently changes a clinical rule release.

```bash
python3 scripts/publish_clinical_rules.py \
  clinical_reporting_rules/solid_GMSv3/endometrie.yaml \
  --published-by <username>
```

Publication validates the YAML contract, repository path, registered facts,
restricted templates, deterministic content hash, and rule uniqueness. The
resulting release is immutable. An administrator binds the release to the
matching ASPC through the governed ASPC version workflow. An ASPC without a
bound release does not guess a file or choose the newest database record.

### Administration Protocol

Clinical text is changed through a controlled sequence. The sequence keeps the
editable source, published release, active assay configuration, and saved report
separate so that each has one clear purpose.

1. **Define the clinical scope.** Confirm that the ASP exists and that its
   `asp_id`, analyte, supported files, covered genes, and germline genes are
   correct. Confirm that the ISGLs used by the assay identify the correct assay,
   assay group, subpanel, list type, and curated gene symbols.
2. **Define the executable report context.** Create or rotate the ASPC for the
   exact `(asp_id, subpanel_id, environment)` scope. Enable only analyses that
   the assay performs, then configure matching reporting analyses and report
   sections.
3. **Author the YAML source.** Create or update the one rule file for the
   assay/subpanel scope. The approved clinical wording stays in the YAML
   template. Conditions refer only to registered prepared facts.
4. **Validate the rule change.** Add exact-output examples for the intended
   positive, negative, priority, and missing-data cases. Review a rendered
   preview with the clinical owner.
5. **Publish the release.** Run the publishing command. It compiles the YAML,
   validates facts and templates, calculates a content hash, and stores one
   immutable release in `clinical_rule_sets`.
6. **Bind the release in the ASPC form.** In **Administration > Assay
   Configurations**, select the ASP, subpanel, and environment. The
   **Published Clinical Rule Release** field lists only active releases matching
   that analyte, ASP, and subpanel. Saving rotates the ASPC and persists the
   release ID, rule-set ID, version, and content hash together.
7. **Use the governed configuration.** A report preview resolves the exact
   release bound to the sample's effective ASPC. Saving the report snapshots
   that reference with the prepared result.

!!! warning "A release is selected, not copied"

    The ASPC does not contain a duplicate copy of all YAML rules. It stores a
    verified reference to one immutable published release. This prevents
    ambiguity, reduces repeated configuration data, and lets one release be
    used by more than one environment when the approved wording is identical.

### Report-Ready ASPC Fields

The ASPC is the runtime contract that joins analytical review and clinical
wording. An active ASPC is report-ready only when the following information is
present and mutually consistent.

| Area | Required information | Why it is required |
| --- | --- | --- |
| Scope | `asp_id`, `subpanel_id`, `environment`, `asp_group`, `asp_category` | Resolves the precise clinical configuration and corresponding rule scope. |
| Enabled analysis | `analysis_types` with at least one allowed analysis | Controls which review data and report candidates exist. |
| Reporting analysis | `reporting.analysis` equal to `analysis_types` | Prevents a report from silently omitting an enabled analysis. |
| Report sections | Non-empty `reporting.report_sections`, each included in reporting analysis | Defines which prepared result sections may be rendered. |
| Clinical text | `report_header`, `report_method`, `report_description`, `general_report_summary` | Supplies the approved report identity and introductory context. |
| Output locations | `plots_path` and `report_folder` | Defines the configured report artifact context. |
| Rule release | `reporting.clinical_rule_release` | Binds the exact immutable YAML release used for clinical text. |

The schema enforces these fields for an active ASPC. An ASPC cannot become
active until its reporting analysis matches its enabled analysis and a published
clinical rule release is selected.

### ASP, ASPC, And ISGL Responsibilities

The three configuration records deliberately do not overlap.

| Record | Owns | Does not own |
| --- | --- | --- |
| ASP | The physical/analytical assay: modality, platform, file policy, covered genes, germline genes, and stable assay identity. | Thresholds, reviewer filters, or prose rules. |
| ASPC | The assay/subpanel/environment behavior: enabled analyses, typed filters, report sections, approved report introduction, and immutable rule-release reference. | A duplicate of full YAML rule content or gene-list membership. |
| ISGL | Curated in-silico gene scope: list type, eligible assays/groups, subpanel association, curated genes, and optional germline subset. | Assay file policy, thresholds, or report wording. |

The administration UI follows the same separation. ASP forms show assay
identity, ingest contract, and clinical gene scope. ASPC forms separate
configuration scope, enabled analysis, analytical filters, clinical reporting,
public catalog metadata, and verification context. ISGL forms separate list
identity, clinical scope, curated gene content, availability, and record
history. ISGL list types are rendered as individual domain badges so a list with
multiple supported uses is visible without parsing a comma-separated value.

### YAML Authoring Checklist

Before a rule file is published, its author should be able to answer each item
below from the application contracts rather than from informal worksheet names.

| Question | Authoritative source |
| --- | --- |
| Which assay and subpanel does the wording apply to? | ASP `asp_id` and ASPC `subpanel_id`. |
| Is this DNA or RNA? | ASP/ASPC `asp_category`, represented as YAML `analyte`. |
| Which findings reach the rule? | Prepared report candidates after ASPC filters and persisted review state. |
| Which curated lists are active? | `applied_gene_lists` in the prepared context. |
| Which clinical condition selects the text? | `when` predicates over registered facts. |
| What exact wording must be rendered? | The YAML `template`, reviewed as approved clinical text. |
| Which section receives it and which rule wins? | `section`, `family`, `priority`, and `stop`. |
| What happens if a needed result is unavailable? | An explicit deferred rule plus a defined data-contract task; never an inferred condition. |

### Minimal Authoring Example

This example demonstrates the complete shape of an executable finding rule.
It is illustrative; production wording is owned by the relevant assay rule
file and approved through the centre's clinical process.

```yaml
rule_set:
  analyte: dna
  assay_id: example_panel
  subpanel_id: base
  version: "2"

rules:
  - rule_id: example_tp53_tier_1
    family: finding_text
    section: Molecular findings
    priority: 10
    when:
      - fact: finding.gene
        operator: eq
        value: TP53
      - fact: finding.tier
        operator: eq
        value: 1
    template: |-
      {{ finding.gene }} {{ finding.hgvsp }} is classified as Tier I.
    heading: true
    stop: true

deferred_rules: []
```

The engine evaluates this rule only after all upstream filtering, transcript
selection, HGNC normalization, classification, and report inclusion decisions
have completed. The template renders facts; it does not make clinical
classification decisions itself.

## Adding A New Assay Or Subpanel

1. Confirm the exact ASP `asp_id` and ASPC `subpanel_id`.
2. List the analyses and report sections enabled by that ASPC.
3. Create `clinical_reporting_rules/<asp_id>/<subpanel_id>.yaml`.
4. Populate the four `rule_set` identity fields.
5. Express each supported clinical condition using existing prepared facts.
6. Add the exact approved template text, without paraphrasing it.
7. Put text requiring data that does not yet exist in `deferred_rules`.
8. Add matching, non-matching, priority, missing-data, and exact-output tests.
9. Increment the version, publish the release, and bind it to the ASPC.

When a requested condition cannot be expressed with existing facts, add the
clinical data contract first. Define its authoritative data source, allowed
values or units, missing-value behavior, ingestion/preparation mapping, and
tests. Only then add the corresponding executable YAML rule.

## Current Rule Sets

| Assay | Subpanel | File |
|---|---|---|
| `hema_GMSv1` | `base` | `hema_GMSv1/base.yaml` |
| `myeloid_GMSv1` | `base` | `myeloid_GMSv1/base.yaml` |
| `solid_GMSv3` | `base` | `solid_GMSv3/base.yaml` |
| `solid_GMSv3` | `endometrie` | `solid_GMSv3/endometrie.yaml` |
| `fusion` | `base` | `fusion/base.yaml` |
| `RNA_fusion` | `base` | `RNA_fusion/base.yaml` |
| `solidRNA_GMSv5` | `base` | `solidRNA_GMSv5/base.yaml` |
| `tumwgs_hema` | `base` | `tumwgs_hema/base.yaml` |
| `tumwgs_solid` | `base` | `tumwgs_solid/base.yaml` |
