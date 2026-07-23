# Clinical Reporting Rules

Coyote3 generates report text from repository-authored YAML rule sets. Each
rule set belongs to one exact assay and one exact subpanel. The engine receives
the already filtered report result and produces deterministic clinical text; it
does not decide which findings are reportable.

!!! info
    YAML is the only editable source of reporting rules. MongoDB stores
    immutable published releases so running API instances use identical
    content and saved reports remain reproducible.

## 1. Reporting Boundary

The report workflow completes the following operations before rule evaluation:

1. Resolve the sample, ASP, and active ASPC.
2. Load the sample's current filter state.
3. Resolve selected ISGLs and effective genes.
4. Query the analysis collections enabled by the ASPC.
5. Apply analytical thresholds and gene-list scope.
6. Apply false-positive, irrelevant, blacklist, and report-state decisions.
7. Resolve selected transcripts and current classifications.
8. Prepare normalized SNVs, CNVs, fusions, translocations, biomarkers, ASP
   metadata, ASPC metadata, and applied gene-list metadata.
9. Pass the resulting read-only `PreparedReportContext` to the rules engine.

The rule engine therefore receives the same report candidates shown in the
temporary report snapshot. It does not query MongoDB, repeat filtration, select
transcripts, classify findings, call knowledgebases, or mutate clinical data.

The engine may:

- match registered facts using allowlisted operators;
- select rules in deterministic priority order;
- render approved values into exact clinical wording;
- compose sections from multiple analysis domains;
- return a complete evaluation trace.

!!! caution
    A clinical phrase in a workbook is not a machine-readable condition.
    Before such a phrase can become executable, the application must provide a
    typed fact with a defined source, unit, allowed values, and missing-value
    behavior.

## 2. Rule-Set Identity

### 2.1 Directory structure

Rule files use this exact layout:

```text
clinical_reporting_rules/
  <asp_id>/
    <subpanel_id>.draft.yaml
    <subpanel_id>.yaml
```

Examples:

```text
clinical_reporting_rules/
  hema_GMSv1/
    base.draft.yaml
  solid_GMSv3/
    base.draft.yaml
    endometrie.draft.yaml
  fusion/
    base.draft.yaml
```

The directory name is the ASP `asp_id`. The filename stem is the ASPC
`subpanel_id`. `base` is the assay-wide configuration used when no specific
subpanel is selected.

The compiler rejects:

- a source outside the two-level assay/subpanel layout;
- a directory that differs from `scope.assay_id`;
- a filename stem that differs from `scope.subpanel_id`;
- a `rule_set_id` other than `<assay_id>__<subpanel_id>`.

### 2.2 Complete files, not overlays

Every file is a complete rule set for its exact assay/subpanel identity. A
subpanel file does not inherit hidden clauses from `base`, and `base` is not
silently merged into a specific subpanel.

This keeps clinical review explicit:

- reviewers can inspect one file and see the complete executable behavior;
- rule priority is local to one file;
- a published release has one unambiguous scope;
- changes to one subpanel cannot alter another subpanel.

If two assay/subpanel configurations use identical approved wording, each
still has its own file. The text may be the same, but the release identities
remain separate.

### 2.3 Environment is not rule identity

Clinical wording is selected by assay and subpanel, not by deployment
environment. Development, validation, and production ASPCs may bind the same
approved immutable release.

Environment-specific YAML variants are not supported. Deployment promotion is
performed by binding the approved release to the appropriate ASPC version.

### 2.4 Current authored inventory

| Assay | Subpanel | File | Current wording authority |
|---|---|---|---|
| `hema_GMSv1` | `base` | `hema_GMSv1/base.draft.yaml` | Previously validated hematology implementation |
| `myeloid_GMSv1` | `base` | `myeloid_GMSv1/base.draft.yaml` | Previously used myeloid implementation |
| `solid_GMSv3` | `base` | `solid_GMSv3/base.draft.yaml` | Previously used solid-tumor implementation |
| `solid_GMSv3` | `endometrie` | `solid_GMSv3/endometrie.draft.yaml` | Endometrial clinical workbook |
| `fusion` | `base` | `fusion/base.draft.yaml` | Previously used WTS fusion implementation |
| `RNA_fusion` | `base` | `RNA_fusion/base.draft.yaml` | Previously used 160-gene RNA fusion implementation |
| `solidRNA_GMSv5` | `base` | `solidRNA_GMSv5/base.draft.yaml` | Previously used targeted solid RNA implementation |
| `tumwgs_hema` | `base` | `tumwgs_hema/base.draft.yaml` | Previously used TumWGS implementation |
| `tumwgs_solid` | `base` | `tumwgs_solid/base.draft.yaml` | Previously used TumWGS implementation |

Historical code and controlled workbooks are provenance sources only. Their
names are not used as runtime identities, rule-set IDs, or file names.

## 3. YAML Contract

Every source uses schema version 3:

```yaml
schema_version: 3
rule_set:
  rule_set_id: solid_GMSv3__endometrie
  version: "0.2.0-draft"
  title: Endometrial cancer DNA reporting wording
  status: draft
  language: sv
  scope:
    analyte: dna
    assay_id: solid_GMSv3
    subpanel_id: endometrie
  provenance:
    authority: clinical_workbook
    reference: .design/endometrierapport to Ram.xlsx
    revision: workbook-2026-07-23
    content_sha256: <sha256>
    text_policy: verbatim
  validation:
    approval_status: pending
    approval_reference:
    golden_case_ids:
      - endometrial-tp53
  required_facts:
    - sample.subpanel_id
  notes: Optional author guidance.
rules: []
deferred_rules: []
```

### 3.1 Metadata fields

| Field | Requirement |
|---|---|
| `schema_version` | Must be `3` |
| `rule_set_id` | Must be `<assay_id>__<subpanel_id>` |
| `version` | Increment for every executable condition or wording change |
| `status` | `draft`, `active`, or `retired` |
| `language` | Language of rendered clinical text |
| `scope.analyte` | `dna` or `rna`; must match the ASPC category |
| `scope.assay_id` | Exact ASP identifier |
| `scope.subpanel_id` | Exact ASPC subpanel identifier; use `base` when applicable |
| `provenance.authority` | Controlled category of the wording authority |
| `provenance.reference` | Exact source artifact used for transcription |
| `provenance.revision` | Immutable source revision |
| `provenance.content_sha256` | SHA-256 of the authoritative source artifact |
| `provenance.text_policy` | Must be `verbatim` |
| `validation.approval_status` | `pending`, `inherited`, or `approved` |
| `validation.approval_reference` | Review record or inherited validation reference |
| `validation.golden_case_ids` | Exact-output tests required for publication |
| `required_facts` | Facts that must exist before any rule is evaluated |

Clinical wording copied from an existing validated implementation is retained
exactly. Source corrections, spelling changes, punctuation changes, and
translations are clinical changes and require a new version and review.

### 3.2 Executable rules

```yaml
- rule_id: solid_GMSv3_tiered_snv_summary
  family: result_text
  section: Kliniskt relevanta SNVs och små INDELs
  priority: 90
  description: Tier-ordered SNV composition.
  source_locator: <controlled-source-location>
  when:
    - fact: aggregates.has_tiered_snvs
      operator: eq
      value: true
  template: |-
    <exact approved text and placeholders>
  heading: true
  stop: true
```

| Field | Meaning |
|---|---|
| `rule_id` | Stable unique identifier used in traces and report provenance |
| `family` | Evaluation phase |
| `section` | Destination report section |
| `priority` | Lower values run first within the family |
| `description` | Human-readable clinical intent |
| `source_locator` | Exact function, line range, workbook sheet, or controlled section |
| `when` | AND-combined typed predicates |
| `template` | Exact clinical wording rendered by restricted Jinja |
| `heading` | Whether the composer emits the section heading |
| `stop` | Whether a successful match blocks lower-priority rules for that candidate |

Rule IDs and priorities cannot repeat within their required scope. Use YAML
literal blocks (`|-`) for clinical text. Folded blocks can alter line breaks
and are unsuitable for exact-output validation.

### 3.3 Deferred rules

`deferred_rules` preserve exact wording that cannot yet be activated safely:

```yaml
deferred_rules:
  - rule_id: endometrial_msi_high
    description: Approved statement for an interpreted MSI-H result.
    source_locator: <controlled-source-location>
    template: |-
      <exact source wording>
    required_fact_contract:
      - interpreted MSI state with an approved enum
      - authoritative method and validation state
    activation_note: >-
      Numeric MSI values must not be translated into MSI-H until the clinical
      interpretation contract has been approved.
```

Deferred rules are validated and included in the release hash, but are never
executed. To activate one:

1. Define the authoritative source.
2. Add a typed Pydantic field with units or allowed values.
3. Populate the fact before report preparation.
4. Register the fact path.
5. Move the rule to `rules`.
6. Add positive, negative, boundary, and missing-value tests.
7. Obtain clinical approval and increment the rule-set version.

## 4. Prepared Report Facts

### 4.1 Configuration facts

| Fact | Source |
|---|---|
| `sample.*` | Sample anchor and current report context |
| `asp.*` | Exact assay definition |
| `aspc.*` | Exact assay configuration used to prepare the report |
| `aspc.reporting.analysis` | Enabled report analysis domains |
| `aspc.reporting.report_sections` | Configured report sections |
| `applied_gene_lists` | Exact selected ISGL documents and versions |

`applied_gene_lists` includes `selected_for`, which records whether each list
was applied to SNV, CNV, fusion, or another supported analysis domain. A rule
must not infer list selection merely because a finding gene belongs to a list.

### 4.2 Finding facts

| Fact | Meaning |
|---|---|
| `finding.kind` | `snv`, `cnv`, `fusion`, or `translocation` |
| `finding.gene` / `finding.genes` | Selected gene or all represented genes |
| `finding.tier` | Current resolved classification |
| `finding.exon` / `finding.intron` | Selected-transcript location |
| `finding.hgvsc` / `finding.hgvsp` | Selected-transcript HGVS |
| `finding.consequence` | Selected-transcript consequence |
| `finding.case_vaf` / `finding.control_vaf` | Decimal allele fractions |
| `finding.case_vaf_percent` / `finding.control_vaf_percent` | Prepared percentages |
| `finding.variant_type` | Normalized variant type |
| `finding.cnv_effect` | Prepared gain/loss interpretation |
| `finding.fusion_gene_1/2` | Structural finding partners |

Transcript selection and HGNC normalization are completed before report-rule
evaluation. Rules cannot choose another transcript.

### 4.3 Aggregate and biomarker facts

Prepared aggregates include:

- finding and analysis-domain counts;
- Tier I, II, and III counts;
- ordered tier summaries grouped by gene;
- reportable-finding and tiered-SNV booleans.

The complete prepared biomarker list is available to templates. A biomarker
condition becomes executable only after its interpretation is represented by a
registered typed fact. Raw numeric values are not converted into clinical
categories inside YAML.

## 5. Evaluation Protocol

Families run in this order:

1. `finding_text`, once per prepared finding;
2. `result_text`, once for the complete report result;
3. `summary_text`, once after result text.

Within a family:

1. Sort by ascending priority.
2. Evaluate every `when` condition using AND semantics.
3. Record matched, rejected, and missing facts in the trace.
4. Render a matched template in the sandboxed Jinja environment.
5. Stop lower-priority rules for the same candidate when `stop: true`.
6. Append rendered text to its configured section.

Supported operators are:

| Operator | Behavior |
|---|---|
| `eq` / `ne` | Equality or inequality |
| `in` / `not_in` | Scalar membership |
| `contains` | Collection or text contains a value |
| `overlaps` | Two collections share a value |
| `exists` | Fact presence or absence |
| `gt` / `gte` | Ordered greater-than comparison |
| `lt` / `lte` | Ordered less-than comparison |

Arbitrary Python, database expressions, regular expressions, and unregistered
document paths are not accepted.

Templates run with strict undefined values and only these roots:

```text
sample
asp
aspc
applied_gene_lists
finding
biomarkers
aggregates
```

The template environment cannot import modules, call repositories, use
application globals, or mutate data.

## 6. MongoDB Releases

The `clinical_rule_sets` collection stores immutable compiled releases:

| Field | Meaning |
|---|---|
| `_id` | Immutable release identity |
| `rule_set_id` | Exact assay/subpanel logical identity |
| `version` | Author-assigned version |
| `schema_version` | Validated source schema |
| `content_hash` | SHA-256 of canonical compiled content |
| `source_path` | Repository path used for publication |
| `source` | Complete validated source |
| `status` | Release lifecycle |
| `published_by` / `published_on` | Publication audit metadata |

Unique indexes protect `(rule_set_id, version)` and `content_hash`. A lookup
index covers assay, subpanel, and status.

MongoDB is not an editing interface. It is the immutable runtime artifact
store. Publishing identical canonical content is idempotent; reusing a version
with different content is rejected.

## 7. Publication And ASPC Binding

### 7.1 Promote and publish

After clinical approval:

1. Increment the authored version.
2. Set `status: active`.
3. Set approval status and approval reference.
4. Add complete golden case IDs.
5. Rename `<subpanel>.draft.yaml` to `<subpanel>.yaml`.
6. Publish explicitly:

```bash
python3 scripts/publish_clinical_rules.py \
  clinical_reporting_rules/solid_GMSv3/endometrie.yaml \
  --published-by <username>
```

Publication is not performed during API startup. Restarting an application
must not silently change clinical configuration.

### 7.2 Bind to an ASPC

Bind the published release through the authenticated admin API:

```bash
curl --request PUT \
  --header "Authorization: Bearer <access-token>" \
  --header "Content-Type: application/json" \
  --data '{"release_id": "<published-release-object-id>"}' \
  "https://<host>/<script-name>/api/v1/resources/aspc/<aspc-id>/clinical-rule-release"
```

The API:

1. resolves the active ASPC;
2. resolves the immutable release;
3. verifies release status and integrity;
4. requires exact analyte, ASP ID, and subpanel ID equality;
5. derives the complete release reference;
6. rotates the ASPC through the governed version workflow.

The request accepts only `release_id`. Clients cannot submit a conflicting
rule-set ID, version, or hash.

An ASPC without a bound release does not guess a rule set from assay group,
environment, filenames, or the newest database record.

## 8. Preview, Save, And Reproducibility

Preview rebuilds the filtered report result, verifies the ASPC-bound release,
evaluates it, and returns temporary text plus the evaluation trace. Preview
does not write report history.

Save repeats preparation and evaluation on the server. Client-provided HTML or
generated clinical text is not trusted.

The saved report records:

```yaml
clinical_rule_release:
  release:
    release_id: ...
    rule_set_id: ...
    version: ...
    content_hash: ...
  matched_rule_ids:
    - solid_GMSv3_tiered_snv_summary
```

This provenance is stored with the filter snapshot, ASPC snapshot, finding
snapshots, report artifacts, author, and UTC timestamp. Historical reports
remain tied to their original immutable release after later YAML changes.

## 9. Adding An Assay Or Subpanel

Follow this protocol:

1. Confirm the exact active `asp_id`.
2. Confirm the exact ASPC `subpanel_id`; use `base` only for the base ASPC.
3. Inventory all report sections enabled by `aspc.reporting.analysis`.
4. Identify the controlled wording authority for every section.
5. Map each condition only to facts already present in
   `PreparedReportContext`.
6. Create `<asp_id>/<subpanel_id>.draft.yaml`.
7. Copy clinical wording exactly; do not paraphrase it.
8. Put unsupported conditions and their exact text in `deferred_rules`.
9. Add positive, negative, boundary, missing-fact, priority, and exact-output
   tests.
10. Review the generated complete report with clinical stakeholders.
11. Approve, promote, publish, and bind the immutable release.

When a new requirement cannot be expressed:

1. define a clinical data contract;
2. identify its authoritative source and units;
3. add it to ingestion or an audited interpretation workflow;
4. expose it through the prepared report context;
5. register the fact;
6. test it independently;
7. then activate the corresponding rule.

This sequence prevents human shorthand such as “POLE exonuclease domain” or
“MSI high” from becoming guessed document keys or hidden Python logic.

## 10. Endometrial Rule Set

`clinical_reporting_rules/solid_GMSv3/endometrie.draft.yaml` is scoped to the
exact `solid_GMSv3`/`endometrie` configuration. It currently maps workbook
wording only where an existing typed fact supports the condition, including:

- POLE selected-transcript exons 9 through 14;
- POLE findings outside those exons;
- TP53;
- the configured mismatch-repair genes;
- explicitly listed supporting genes.

MSI interpretation, tumor-cell fraction decisions, and interpreted CNV-profile
states remain deferred because the current application does not yet provide
their approved typed interpretation contracts. The workbook text is retained
without inventing runtime fields.

## 11. Validation Requirements

Every release requires:

- Pydantic schema validation;
- repository path and scope validation;
- fact-registry validation;
- restricted-template validation;
- deterministic content hashing;
- exact assay/subpanel binding tests;
- positive and negative rule tests;
- priority and stop tests;
- missing-required-fact failure tests;
- exact-output golden tests;
- preview no-write verification;
- saved provenance verification;
- clinical approval.

Draft files may compile and run in tests, but cannot be published until their
approval metadata and golden evidence are complete.
