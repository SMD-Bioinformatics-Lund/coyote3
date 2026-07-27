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

## YAML Field Reference

This section is the normative authoring reference. Every executable rule must
use the keys below. No unlisted top-level keys, rule keys, condition keys, or
deferred-rule keys are accepted by the schema.

### File-Level Keys

| Key | Required | Format and allowed values | How Coyote3 uses it | Authoring guidance |
| --- | --- | --- | --- | --- |
| `rule_set` | Yes | Mapping containing `analyte`, `assay_id`, `subpanel_id`, and `version`. | Declares exactly which ASPC scope may bind this release. | Use the business identifiers from ASP and ASPC, never a display name from a worksheet. |
| `rule_set.analyte` | Yes | `dna` or `rna`. | Must equal the sample omics layer and the selected ASPC category. | Choose `dna` for DNA assay configurations and `rna` for RNA configurations. |
| `rule_set.assay_id` | Yes | Existing ASP `asp_id`, as an exact string. | Forms the immutable rule-set scope and runtime identity. | Copy the exact ASP ID shown in the ASP administration view. |
| `rule_set.subpanel_id` | Yes | Existing ASPC `subpanel_id`; use `base` when there is no subpanel-specific configuration. | Limits the release to the matching ASPC subpanel. | A subpanel file is complete on its own; it does not inherit rules from `base.yaml`. |
| `rule_set.version` | Yes | Non-empty string, normally an incrementing value such as `"1"`, `"2"`, or `"2026.1"`. | Becomes part of the immutable release reference saved in the ASPC and report. | Increment whenever approved text, conditions, priorities, or executable rule structure changes. |
| `rules` | Yes | Non-empty YAML list of executable rule mappings. | Evaluated to render report content. | Use `deferred_rules` rather than creating a rule for unavailable or untyped data. |
| `deferred_rules` | No | YAML list; use `[]` when none are required. | Retains approved future wording without evaluating it. | A deferred rule is documentation of a pending data contract, not a fallback path. |

### Executable Rule Keys

| Key | Required | Format and allowed values | Runtime behavior |
| --- | --- | --- | --- |
| `rule_id` | Yes | Non-empty stable identifier. The recommended format is `<assay>_<purpose>`, using lowercase letters, digits, and underscores. | Appears in publication metadata, evaluation traces, tests, and audit investigation. It must be unique across both `rules` and `deferred_rules` in one file. |
| `family` | Yes | One of `finding_text`, `result_text`, or `summary_text`. | Determines when and how often the rule is evaluated; see the family table below. |
| `section` | Yes | Non-empty human-readable report section title, for example `Kliniskt relevanta SNVs och små INDELs` or `Report conclusion`. | Matching content is appended to this section in rule order. Rules using the same section must use the same `heading` value. |
| `priority` | Yes | Integer from `1` through `100000`; lower values run first. | Ordering is unique within a family. A duplicate family/priority pair is rejected at publication. |
| `when` | No | YAML list of zero or more condition mappings; defaults to `[]`. | All conditions are AND-combined. `when: []` always matches. |
| `template` | Yes | Non-empty text or a YAML block scalar (`|-`) containing approved report wording and optional restricted Jinja expressions. | Rendered only after all `when` conditions match. A blank rendered result adds no content. |
| `heading` | No | Boolean; defaults to `true`. | `true` writes the section title once as a report heading. `false` appends text without a heading, for example introductory prose or a conclusion. |
| `stop` | No | Boolean; defaults to `true`. | `true` stops evaluation of lower-priority rules in the same family for the same candidate after a match. `false` allows later rules to add further text. |

### Rule Family Options

| `family` value | Candidate evaluated | Typical use | Example |
| --- | --- | --- | --- |
| `finding_text` | Each prepared reportable finding independently. | Gene-, tier-, exon-, CNV-effect-, fusion-, or translocation-specific wording. | A POLE exon 9-14 finding adds endometrial classification text. |
| `result_text` | Once for the complete prepared report result. | Report introduction, aggregate Tier summaries, or a no-findings statement. | `aggregates.has_tiered_snvs` selects either the Tier summary or the no-somatic-mutations text. |
| `summary_text` | Once after `result_text`. | Conclusion, accreditation statement, limitations, or final report wording. | `asp.accredited` selects the accredited or non-accredited conclusion. |

### `when` Condition Keys

Each item under `when` has exactly three keys:

| Key | Required | Format | Meaning |
| --- | --- | --- | --- |
| `fact` | Yes | One of the registered fact paths in the fact catalogue below. | Reads one prepared, typed value. It cannot read raw MongoDB fields or arbitrary YAML/database paths. |
| `operator` | No | One of the operator values below; defaults to `eq`. | Defines how the fact is compared to `value`. |
| `value` | Yes | Scalar, list, or boolean according to the chosen operator. | The expected value for comparison. It must use the same semantic type as the prepared fact. |

### Operator Options And `value` Format

| Operator | Expected `value` | Match rule | Example |
| --- | --- | --- | --- |
| `eq` | Scalar: string, number, or boolean. | Fact equals `value`. | `fact: asp.accredited`, `value: true`. |
| `ne` | Scalar. | Fact does not equal `value`. | `fact: sample.profile`, `value: research`. |
| `in` | YAML list. | The scalar fact occurs in `value`. | `fact: finding.gene`, `value: [MLH1, MSH2, MSH6, PMS2]`. |
| `not_in` | YAML list. | The scalar fact does not occur in `value`. | `fact: finding.kind`, `value: [fusion, translocation]`. |
| `contains` | Scalar. | The string or collection fact contains `value`. | `fact: finding.consequence`, `value: missense_variant`. |
| `overlaps` | YAML list. | The collection fact and `value` share at least one item. | `fact: finding.exon`, `value: ["9", "10", "11", "12", "13", "14"]`. |
| `exists` | Boolean only: `true` or `false`. | `true` checks that the fact path exists; `false` checks that it is absent. It does not test whether a present value is truthy. | `fact: finding.hgvsp`, `operator: exists`, `value: true`. |
| `gt` | Number or a value compatible with the fact type. | Fact is greater than `value`. | `fact: finding.case_vaf_percent`, `value: 10`. |
| `gte` | Number or compatible value. | Fact is greater than or equal to `value`. | `fact: aggregates.tier_1_count`, `value: 1`. |
| `lt` | Number or compatible value. | Fact is less than `value`. | `fact: finding.control_vaf_percent`, `value: 1`. |
| `lte` | Number or compatible value. | Fact is less than or equal to `value`. | `fact: aggregates.finding_count`, `value: 5`. |

!!! warning "Choose the operator from the fact shape"

    Use `in` when the **fact is one scalar** and the YAML value is a list.
    Use `overlaps` when **both the fact and the YAML value are lists**. For
    example, `finding.gene` uses `in`; `finding.exon` uses `overlaps`.
    Incorrect types do not match and are visible in the evaluation trace.

### Example Explained Line by Line

The following rule produces the accredited conclusion only when the configured
ASP has `accredited: true`.

```yaml
- rule_id: hema_GMSv1_accredited_conclusion
  family: summary_text
  section: Report conclusion
  priority: 200
  when:
    - fact: asp.accredited
      operator: eq
      value: true
  template: "För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport.\\x20"
  heading: false
  stop: true
```

| YAML line | Interpretation |
| --- | --- |
| `rule_id` | Stable trace and test identity. It does not appear in the clinical report. |
| `family: summary_text` | Runs once after result text; it is not run once per variant, CNV, or fusion. |
| `section: Report conclusion` | Appends the wording to the report conclusion section. |
| `priority: 200` | Is evaluated after lower-numbered summary rules. The non-accredited conclusion at priority `100` does not match when `asp.accredited` is true. |
| `fact: asp.accredited` | Reads the boolean accreditation status from the ASP definition. |
| `operator: eq`, `value: true` | Requires the status to be exactly boolean `true`. |
| `template` | Is the exact approved Swedish conclusion text. `\\x20` is a literal trailing space escape retained in the existing approved source; normal new wording should use a block scalar where practical. |
| `heading: false` | Does not generate a Markdown/HTML heading for this conclusion text. |
| `stop: true` | Once matched, stops other later summary rules for this report candidate. |

### `deferred_rules` Keys

| Key | Required | Format and behavior |
| --- | --- | --- |
| `rule_id` | Yes | Stable identifier, unique across the entire YAML file. |
| `template` | Yes | Exact approved text that must not run yet. |
| `required_fact_contract` | Yes | Non-empty list describing the typed facts, source, units/enumerations, and validation state needed before the rule can become executable. |

Deferred rules do not have `family`, `section`, `priority`, `when`, `heading`, or
`stop` because they are not part of runtime evaluation. When the prerequisite
data contract exists, move the text into `rules` and add all executable keys.

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

The report-preparation service provides only the allowlisted fact paths below.
They are available to conditions and templates. A path not listed here is
rejected during publication; rule authors must not reference raw collection
keys or infer values from an assay name.

### Registered Fact Catalogue

| Fact path | Value type | Available in | Meaning and valid values |
| --- | --- | --- | --- |
| `sample.name` | String | All rule families | Human-readable sample name. |
| `sample.assay` | String | All | Sample ASP ID. |
| `sample.subpanel_id` | String | All | Effective sample subpanel, normally an ASPC `subpanel_id` or `base`. |
| `sample.profile` | String | All | Sample environment/profile. |
| `sample.omics_layer` | `dna` or `rna` | All | Sample molecular layer. |
| `sample.paired` | Boolean | All | Whether a paired control is available. |
| `sample.genome_build` | Integer, string, or null | All | Genome build recorded for the sample. |
| `asp.asp_id` | String | All | Stable ASP identifier. |
| `asp.asp_group` | String or null | All | Configured assay group. |
| `asp.asp_category` | `dna`, `rna`, or null | All | Configured assay category. |
| `asp.accredited` | Boolean | All | ASP accreditation status. Use this for approved accreditation wording. |
| `asp.germline_genes` | List of gene symbols | All | Assay-level genes for which germline evaluation is configured. |
| `aspc.aspc_id` | String | All | Effective ASPC business identifier. |
| `aspc.asp_id` | String | All | ASP ID in the effective ASPC. |
| `aspc.asp_group` | String or null | All | ASP group in the effective ASPC. |
| `aspc.asp_category` | `dna`, `rna`, or null | All | ASP category in the effective ASPC. |
| `aspc.subpanel_id` | String | All | Effective ASPC subpanel. |
| `aspc.environment` | String | All | Effective ASPC environment. |
| `aspc.reporting.analysis` | List of analysis types | All | Enabled reporting analyses. Options are controlled by the ASPC category. |
| `aspc.reporting.report_sections` | List of analysis types | All | Configured report sections, each enabled in reporting analysis. |
| `aspc.reporting.general_report_summary` | String | All | Approved report introduction text from ASPC. |
| `applied_gene_lists` | List of selected ISGL objects | All | Exact selected ISGL scope. Each item includes `isgl_id`, `version`, `list_type`, `selected_for`, `genes`, `germline_genes`, and `adhoc`. |
| `finding.kind` | `snv`, `cnv`, `fusion`, or `translocation` | `finding_text` | The reportable finding domain. |
| `finding.gene` | Gene symbol or null | `finding_text` | Primary displayed HGNC-normalized gene symbol. |
| `finding.genes` | List of gene symbols | `finding_text` | All genes associated with the finding. |
| `finding.tier` | Integer `1`-`4` or null | `finding_text` | Persisted clinical tier. |
| `finding.exon` | List of exon strings | `finding_text` | Selected transcript exon value(s); use `overlaps` for exon-domain conditions. |
| `finding.intron` | List of intron strings | `finding_text` | Selected transcript intron value(s). |
| `finding.case_vaf` | Decimal fraction or null | `finding_text` | Case VAF in the `0`-`1` range. |
| `finding.case_vaf_percent` | Percentage number or null | `finding_text` | Case VAF represented as `0`-`100`. |
| `finding.control_vaf` | Decimal fraction or null | `finding_text` | Control VAF in the `0`-`1` range. |
| `finding.control_vaf_percent` | Percentage number or null | `finding_text` | Control VAF represented as `0`-`100`. |
| `finding.consequence` | List of VEP consequence terms | `finding_text` | Consequence terms retained after transcript selection. |
| `finding.hgvsc` | String or null | `finding_text` | Selected transcript HGVS coding notation. |
| `finding.hgvsp` | String or null | `finding_text` | Selected transcript HGVS protein notation. |
| `finding.variant_type` | String or null | `finding_text` | Variant type prepared from the source result. |
| `finding.cnv_effect` | String or null | `finding_text` | CNV effect, for example `gain` or `loss`, when available. |
| `finding.fusion_gene_1` | String or null | `finding_text` | First fusion partner, when available. |
| `finding.fusion_gene_2` | String or null | `finding_text` | Second fusion partner, when available. |
| `biomarkers` | List of prepared biomarker records | `result_text`, `summary_text` | Prepared biomarker data. No stable sub-fields are currently registered for condition matching; introduce a typed biomarker fact before creating a biomarker-specific executable rule. |
| `aggregates.finding_count` | Integer | `result_text`, `summary_text` | Total prepared reportable findings. |
| `aggregates.snv_count` | Integer | `result_text`, `summary_text` | Prepared SNV/small-indel finding count. |
| `aggregates.cnv_count` | Integer | `result_text`, `summary_text` | Prepared CNV finding count. |
| `aggregates.fusion_count` | Integer | `result_text`, `summary_text` | Prepared fusion finding count. |
| `aggregates.translocation_count` | Integer | `result_text`, `summary_text` | Prepared translocation finding count. |
| `aggregates.biomarker_count` | Integer | `result_text`, `summary_text` | Prepared biomarker record count. |
| `aggregates.tier_1_count` | Integer | `result_text`, `summary_text` | Prepared Tier I finding count. |
| `aggregates.tier_2_count` | Integer | `result_text`, `summary_text` | Prepared Tier II finding count. |
| `aggregates.tier_3_count` | Integer | `result_text`, `summary_text` | Prepared Tier III finding count. |
| `aggregates.tier_summaries` | Ordered Tier-summary list | `result_text`, `summary_text` | Prepared grouped Tier summary. Use with the `tier_summary` template filter. |
| `aggregates.has_tiered_snvs` | Boolean | `result_text`, `summary_text` | `true` when prepared SNV/small-indel findings have a clinical tier. |
| `aggregates.has_reportable_findings` | Boolean | `result_text`, `summary_text` | `true` when one or more reportable findings exist in any supported domain. |

Transcript selection and HGNC normalization are complete before a finding
reaches this engine. YAML rules do not select transcripts, rename genes, query
MongoDB, or call a knowledgebase.

The shared `dna_report_intro` formatter renders
`aspc.reporting.general_report_summary`, the paired-control statement, selected
SNV ISGL identifiers, effective SNV gene count, and germline statement from
prepared facts. For example, a selected `hematology_myeloid` list is rendered
as `HEMATOLOGY_MYELOID`; the formatter does not infer a list from assay or
subpanel identity.

Templates run in a restricted Jinja environment. They can only read the roots
listed above. They cannot execute Python, access MongoDB, call external
services, or change report data.

### Template Expressions And Filters

| Capability | Available options | Purpose |
| --- | --- | --- |
| Fact roots | `sample`, `asp`, `aspc`, `applied_gene_lists`, `finding`, `biomarkers`, `aggregates` | Read the prepared values described in the fact catalogue. |
| Standard Jinja filters | `default`, `join`, `length`, `lower`, `round`, `upper` | Simple presentation-only operations. |
| `tier_summary` | `{{ aggregates.tier_summaries \| tier_summary }}` | Renders the shared approved Swedish Tier grammar using `mutation`/`mutationer`. No wording configuration is duplicated in YAML. |
| `dna_report_intro` | `{{ aspc.reporting.general_report_summary \| dna_report_intro(sample, asp, applied_gene_lists) }}` | Renders the approved DNA introduction together with paired-control, selected SNV ISGL, effective gene count, and configured germline information. |

`StrictUndefined` is enabled. A template that refers to a missing fact fails
validation or rendering rather than silently inserting an empty value. Use a
deferred rule when a required clinical fact does not yet have a typed contract.

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

## Worked Examples: YAML To Clinical Text

The following examples show the complete chain: prepared facts, the matching
YAML, the generic runtime behavior, and the final text. They use the
Hematology GMSv1 base rule file because it contains the approved wording used
by the current clinical workflow. Names and values below are explanatory; the
same process applies to every assay and subpanel rule file.

### Example 1: DNA Introduction With the Applied Gene List

The Hematology GMSv1 rule is deliberately short:

```yaml
- rule_id: hema_GMSv1_report_introduction
  family: result_text
  section: Report introduction
  priority: 10
  when: []
  template: "{{ aspc.reporting.general_report_summary | dna_report_intro(sample, asp, applied_gene_lists) }}"
  heading: false
  stop: false
```

An empty `when` list means this rule always matches once the selected ASPC is
confirmed to be `hema_GMSv1/base`. The text is not assembled by assay-specific
`if`/`else` code. The generic `dna_report_intro` template filter receives only
these prepared facts:

| Prepared fact | Example value | Contribution to text |
| --- | --- | --- |
| `aspc.reporting.general_report_summary` | `DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i 385 gener som inkluderas i GMS-HEM v1.1 sekvenseringspanel. ` | Approved assay-method introduction authored in the ASPC. |
| `sample.paired` | `true` | Adds the paired-control sentence. |
| `applied_gene_lists[].isgl_id` | `HEMATOLOGY_MYELOID` | Names the selected SNV list. |
| `applied_gene_lists[].selected_for` | `['snv']` | Limits this introduction to SNV-selected lists; CNV-only or fusion-only lists are not named here. |
| `applied_gene_lists[].genes` | 197 genes | Adds the selected-gene count. |
| `asp.germline_genes` | includes `CEBPA` | Adds the constitutional-testing sentence only when that gene is also selected. |

The runtime flow is:

1. `DNAWorkflowService.build_report_payload()` prepares the report context.
2. `ClinicalRuleService` resolves the immutable release bound to the ASPC.
3. `ClinicalRuleEvaluator` evaluates this `result_text` rule.
4. The sandboxed template invokes the generic `dna_report_intro` filter.
5. The rendered value is appended to **Report introduction** without a heading.

For the facts above, the final report text is:

> DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i 385 gener som inkluderas i GMS-HEM v1.1 sekvenseringspanel. Analysen avser somatiska mutationer (hudbiopsi har använts som kontrollmaterial). Analysen omfattar genlistan: HEMATOLOGY_MYELOID som innefattar 197 gener. För CEBPA undersöks även konstitutionella mutationer.

This is why applying an SNV ISGL changes the introduction immediately. The
rule does not contain a hardcoded list name or gene count; it renders the
selected ISGL facts prepared for that report.

### Example 2: No Reportable Somatic Small Mutations

The same rule set chooses the negative-result wording only when report
preparation has already established that no tiered SNV/indel is reportable:

```yaml
- rule_id: hema_GMSv1_no_somatic_snv
  family: result_text
  section: Kliniskt relevanta SNVs och små INDELs
  priority: 100
  when:
    - fact: aggregates.has_tiered_snvs
      operator: eq
      value: false
  template: |-
    Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats.
  heading: true
  stop: false
```

| Evaluation input | Value | Result |
| --- | --- | --- |
| `aggregates.has_tiered_snvs` | `false` | The `eq false` predicate matches. |
| `aggregates.tier_summaries` | `[]` | The Tier-summary rule at priority 90 does not match because it requires `has_tiered_snvs: true`. |
| `section` | `Kliniskt relevanta SNVs och små INDELs` | The renderer creates this section and writes its heading. |
| `template` | Exact YAML text | Final clinical wording is `Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats.` |

The evaluation trace records both decisions: the Tier-summary rule as
`matched: false` and `hema_GMSv1_no_somatic_snv` as `matched: true` with the
rendered text. The trace is part of report-preview/save provenance, so a user
can explain why this wording appeared without re-running filtering.

### Example 3: Accredited And Non-Accredited Conclusions

Two summary rules express mutually exclusive conclusions using the same ASP
fact. The lower priority value is checked first; `stop: true` prevents a
second conclusion once one matches.

```yaml
- rule_id: hema_GMSv1_unaccredited_conclusion
  family: summary_text
  section: Report conclusion
  priority: 100
  when:
    - fact: asp.accredited
      operator: eq
      value: false
  template: |-
    För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport. Analysen omfattas inte av ackrediteringen.
  heading: false
  stop: true

- rule_id: hema_GMSv1_accredited_conclusion
  family: summary_text
  section: Report conclusion
  priority: 200
  when:
    - fact: asp.accredited
      operator: eq
      value: true
  template: "För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport.\\x20"
  heading: false
  stop: true
```

| `asp.accredited` | Matched rule | Final conclusion |
| --- | --- | --- |
| `false` | `hema_GMSv1_unaccredited_conclusion` | `För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport. Analysen omfattas inte av ackrediteringen.` |
| `true` | `hema_GMSv1_accredited_conclusion` | `För ytterligare information om utförd analys och beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport.` |

No later summary rule can render for the same candidate after either match.
This makes the conclusion deterministic and prevents contradictory wording.

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
