# Create hematology Base reporting rules

Use this walkthrough to author Swedish DNA report wording for `hema_gmsv1` with
diagnosis `base`. Substitute the actual registered assay ID if it differs.
`hematology` is the biological group; it is not the rule set's assay ID.

Start with the [report authoring guide](report-rule-authoring.md) for the editor
controls. The [condition reference](../reference/clinical-reporting-rules.md#worked-condition-patterns)
covers nested conditions, missing values and conflicts.
For solid Base and a named diagnosis/subpanel on the same assay, see the
[solid reporting examples](solid-reporting-examples.md).

## What the default-branch composer actually does

The repository's default branch is `master`, not `main`. This comparison uses
[`BPCommonUtility` at commit `cabdbbfd`](https://github.com/SMD-Bioinformatics-Lund/coyote3/blob/cabdbbfd91e807552f5983a2524284ce9f3bc898/coyote/blueprints/common/util.py).
It describes existing software behavior, not approval of clinical wording or
thresholds for a new assay.

| Part | Condition in that composer | Current authoring equivalent |
| --- | --- | --- |
| Method introduction | Start with `reporting.general_report_summary` from the assay configuration | Literal reviewed method wording plus dynamic assay name and panel gene count |
| Control sentence | Exactly two sample IDs were supplied | **Paired analysis is true** (`sample.paired`) |
| Selected lists | At least one list was selected | Selected SNV list identifiers/names and `gene_lists.snv.gene_count`; test the lists actually applied |
| Small selected scope | At most 20 selected genes | List `gene_lists.snv.genes` rather than a count |
| Large selected scope | More than 20 selected genes | Insert `gene_lists.snv.gene_count` |
| Constitutional investigation | Paired analysis, selected lists and an intersection with the assay's germline genes | Paired analysis plus nonempty `gene_lists.snv.germline_genes` |
| SNV summary | An SNV section exists; summarize eligible tiers I, II and III by gene and case VAF | Declare SNV narrative; use the tier-summary renderer and the ASPC's reportable tiers |
| Negative SNV sentence | No tier-I, II or III group remains | **Has tiered SNVs is false** in a once-per-report SNV block, with reportable tiers restricted to I–III |
| CNV text | Nonempty CNV section; summarize interesting records | CNV block over prepared CNV findings |
| DNA fusion text | Nonempty translocation section; summarize interesting records | TRANSLOCATION block over prepared translocation findings |
| Other biomarkers | HRD sum greater than 42; MSI percentage greater than 15; MSIP preferred when both MSI methods are present in one source record | Optional HRD/MSI blocks with explicit method and measured-value predicates |
| Closing sentence | Always append the closing wording | Unconditional once-per-report rule |
| Accreditation sentence | Assay is not accredited | **Accredited is false** (`asp.accredited`) |

The old composer hardcodes skin-biopsy control wording. A paired sample alone
does not prove that tissue type. Author the control sentence for the verified
workflow; do not copy that assertion into a rule used for other control materials.

The old composer does not contain a separate hematology-specific set of report
conditions in this method. Its results depend on the assay configuration, selected
lists and prepared findings. Gene-specific finding-selection rules belong to
[query rules](query-rules.md), not this report-wording rule set.

## 1. Prepare the assay and create the draft

Confirm that the registered assay, or its saved setup draft, has:

- Assay ID `hema_gmsv1`, biological group `hematology`, and DNA modality.
- The intended full display name, optional short name, `covered_genes`,
  `germline_genes` and accreditation status.
- An applicable configuration for `base` and the sample's environment, with the
  intended SNV/CNV/DNA-fusion analyses and actual gene-list selections.

Base needs no separate diagnosis definition. A list associated with an assay is
not automatically selected for every sample: the report uses its effective
configuration and sample selections.

Open **Administration → Reporting Rule Sets → New rule set → Build in UI**:

| Field | Choose |
| --- | --- |
| Assay | The registered `hema_gmsv1` assay |
| Diagnosis | Base (`base`) |
| Analyte | DNA; derived from the assay |
| Language | `sv` |
| Name | A readable name such as `Hematology Base - Swedish DNA report` |

Choose **Create draft**. The stable scope identity is
`hema_gmsv1__base__sv`; the server manages content versions and revisions.
Base also serves a named diagnosis when no exact published rule set exists for
that diagnosis with the same assay, analyte and language.

In **Report analyses**, choose **Generate text** for SNV and any other analysis
whose narrative you are authoring. For each analysis in the ASPC's
`reporting.report_sections`, explicitly choose **Generate text** or **No narrative**.
**No narrative** suppresses rule-generated prose; it does not by itself remove
the analysis's results table. An undeclared report analysis can block evaluation.

## 2. Build the introduction from independent rules

Under **Start a section**, choose **General introduction**. Keep:

| Section setting | Value |
| --- | --- |
| Output destination | Report summary |
| Analysis | Whole report |
| Evaluate | Once per report |
| Match behavior | All matches |
| Show section heading | Off |

The starter adds five rules, including separate paired and unpaired wording,
initially disabled. Replace placeholder wording,
review the conditions below, then enable **Include this rule in generated report
text** for each intended rule. Preserve spaces between adjacent text/value parts.

### Rule A: method, assay name and panel size

Leave the condition empty, so the rule applies once to every report. Write the
complete sentence in **Report sentence**, using **Insert value at cursor** for
the dynamic parts below. The table shows their ordered content; separate large
text-part editors are available only under advanced formatting.

| Part | Content |
| --- | --- |
| Text | `DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i ` |
| Number | Assay covered gene count (`asp.covered_genes_count`), zero decimals |
| Text | ` gener som inkluderas i ` |
| Value | Assay full display name (`asp.display_name`), or configured short name (`asp.name`) |
| Text | ` sekvenseringspanel. ` |

If the assay has 385 covered genes and display name `GMS-HEM v1.1`, those values
appear automatically. The rule must not store 385 or that assay name as fixed
text. Choose **Require value** so missing assay metadata is visible during testing.

### Rule B: paired-control wording

Choose **Common condition → Paired case/control analysis**, equivalent to
`sample.paired is true`. Enter the center-reviewed control-material sentence.
For a workflow verified to use skin biopsy, the historical wording was:

> Analysen avser somatiska mutationer (hudbiopsi har använts som kontrollmaterial).

Keep a trailing space. This rule emits nothing for an unpaired sample. The starter
also supplies **Unpaired control wording**, conditioned on `sample.paired is false`,
with a generic sentence about analysis without a paired control. Enable it only
when that wording is intended; leave it disabled if the unpaired case needs no
sentence. Both starter sentences use **Continue previous sentence** placement.

### Rule C: the gene lists actually selected

Use **SNV selected lists: unique gene count is greater than 0**. Insert:

| Part | Content |
| --- | --- |
| Text | `Analysen omfattar genlistan: ` |
| List | SNV selected lists: short names (`gene_lists.snv.names`), conjunction `samt` |
| Text | ` som innefattar ` |
| Number | SNV selected lists: unique gene count (`gene_lists.snv.gene_count`) |
| Text | ` gener. ` |

For one selected list named `HEMATOLOGY_MYELOID` with 197 unique genes, this
produces the corresponding name and count. The list's short `name` can contain
uppercase display text even though its `isgl_id` is lowercase. Use **full names**
or **identifiers** if that is the intended report convention.

Overlapping selected lists count each gene once. If multiple lists can be selected,
change the wording to plural or use the count-based collection pattern below to
select singular/plural sentences. Do not leave the singular sentence in addition
to a new plural rule.

To retain the old 20-gene split, replace this rule with two mutually exclusive
rules: a nonempty selected scope with count at most 20 lists the selected genes;
a count greater than 20 emits the count. This is a wording choice, not a finding
filter. Use the same list-name output in both branches.

### Rule D: selected genes with constitutional investigation

Use **Match all** with:

1. Paired analysis **is** true.
2. **Exclude when → SNV selected lists: selected germline genes → is empty**.

Output `För `, list `gene_lists.snv.germline_genes` with conjunction `samt`,
and ` undersöks även konstitutionella mutationer. `.
CEBPA appears only when it belongs to both the selected SNV gene scope and the
assay's declared germline genes. Selecting an unrelated list must not produce
the CEBPA sentence.

## 3. Add positive and negative SNV text

The following grouped example follows the older report composer's tier/gene/VAF
structure. The gene and tier assignments below are synthetic examples, not rules
that classify a gene automatically. The sample must already have reviewed
classifications and report-eligible findings.

### 3A. Configure report eligibility first

In the applicable assay configuration, include SNV in the report sections and
choose SNV reportable tiers `1, 2, 3` for this example. In the rule set's
**Report analyses**, choose **SNV → Generate text**. Complete the declarations
for other configured report analyses as described above.

The report preparation workflow handles finding eligibility, blacklist overrides,
review selections and applicable gene scopes before rule evaluation. Do not
reimplement those filters in wording conditions. No extra gene-specific or VAF
threshold is needed merely because the assay is hematology.

### 3B. Create one section with complementary rules

Choose **Start a section → Variant text** and replace the starter settings:

For the guided route, choose **SNV summary: findings / no findings** instead.
It creates the complementary positive and negative rules and supplies missing
Swedish terminology for review. Open **Section settings** to inspect the settings
below; review the wording and enable both rules. The manual route below remains
available when you need different conditions or per-finding wording.

| Setting | Value |
| --- | --- |
| Output destination | Report summary |
| Section | `Kliniskt relevanta SNVs och små INDELs` |
| Section identifier | A unique identifier such as `hema_gmsv1_base_snv` |
| Analysis | SNV |
| Evaluate | Once per report |
| Match behavior | Exactly one |
| Show section heading | On, or deliberately off for heading-free wording |

The Variant text starter initially uses **For each finding**. Change it to
**Once per report**, remove its Finding type condition and enter the aggregate
conditions below. Finding-level facts are not valid in this once-per-report mode.

**Exactly one** is suitable because the positive and negative conditions are
complements over a prepared boolean. It verifies that one branch matched when
the SNV block is evaluated. **At most one** can be used instead if intentionally
allowing no output; it does not require a branch to match.

### 3C. Positive rule: eligible tiered findings exist

Rename the first rule and enable **Include this rule in generated report text**:

| Rule setting | Value |
| --- | --- |
| Clinical rule name | `Reportable SNVs present` |
| Rule identifier | `hema_base_snv_positive` |
| Condition fact | Has tiered SNVs |
| Operator | is |
| Value | Yes |
| Text placement | New paragraph |

The condition's JSON representation is:

```json
{
  "type": "predicate",
  "fact": "aggregates.has_tiered_snvs",
  "operator": "eq",
  "value": true
}
```

Choose **Use grouped SNV sentences** above the sentence editor. This explicitly
replaces this rule's output with the grouped sentence placeholder and supplies
missing Swedish wording for review. Existing shared wording is preserved. This
produces prose, not a table; the report's configured findings tables are separate.
Write surrounding sentences directly in **Report sentence** if needed.

The renderer groups prepared reportable SNVs by tier and gene, then lists the
ordered case-VAF labels. Inspect **Edit tier summary wording** before enabling
the rule. For a renderer already added through advanced parts without wording,
choose **Add Swedish sentence wording** there. Other languages require authored
wording; the editor does not silently use Swedish for them. The
[complete terminology example](#tier-summary-terminology-example) below also
documents the JSON format.

The insertion action sets `single_gene_always_read_context` to `true` when adding
missing wording. This matches the default branch's repeated single-gene phrasing:
both `BCOR (i 2% av läsningarna)` and a later `ROBO2 (i 16% av läsningarna)` retain
the read context. Existing terminology is not overwritten; enable **single gene
always read context** yourself if that is the approved wording for an existing draft.

For a synthetic TP53 finding already assigned tier I with case VAF 35%, the
terminology example below produces:

> Vid analysen finner man en mutation av stark klinisk signifikans (Tier I) i TP53 (i 35% av läsningarna).

Several findings in one gene contribute several VAF labels to the same gene
group. Findings in multiple genes or tiers produce the corresponding grouped
sentences. The renderer does not assign those tiers.

### 3D. Negative rule: no eligible tiered findings exist

Choose **Add rule** in the same section. Set:

| Rule setting | Value |
| --- | --- |
| Clinical rule name | `No reportable tiered SNVs` |
| Rule identifier | `hema_base_snv_negative` |
| Condition fact | Has tiered SNVs |
| Operator | is |
| Value | No |
| Text placement | New paragraph |

```json
{
  "type": "predicate",
  "fact": "aggregates.has_tiered_snvs",
  "operator": "eq",
  "value": false
}
```

Write the reviewed negative sentence in **Report sentence**:

```text
Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats.
```

Enable this rule too. Both rules may be enabled; their conditions decide which
wording is emitted. Do not leave either rule unconditional in this strict block.

**Has tiered SNVs is false** means no prepared reportable tier groups exist.
**SNV count is zero** checks a different fact: unclassified findings can remain
without contributing an eligible tiered group. With tiers I–III configured, a
tier-IV-only result does not produce a positive I–III summary. If tier IV is
explicitly reportable, the positive condition and renderer can include it.

The negative sentence describes the examined, eligible analysis scope; an empty
collection does not independently establish that testing was performed successfully.
When SNV is absent from the configured report analyses, the SNV block is skipped.

### 3E. Alternative: write a sentence for each finding

Use this alternative when you want your own per-variant wording instead of the
grouped renderer. Do not leave both positive styles enabled unless the duplication
is intended.

Create a section with **Analysis: SNV**, **Evaluate: For each finding**, and
**Match behavior: At most one** for a single sentence rule. Set **Match all**:

| Fact | Operator | Value |
| --- | --- | --- |
| Finding type | is | `snv` |
| Tier | is one of | `1, 2, 3` |

```json
{
  "type": "all",
  "children": [
    {"type": "predicate", "fact": "finding.kind", "operator": "eq", "value": "snv"},
    {"type": "predicate", "fact": "finding.tier", "operator": "in", "value": [1, 2, 3]}
  ]
}
```

In **Report sentence**, write:

```text
I {{finding.gene}} påvisas {{finding.hgvsp}} med variantallelfrekvens {{finding.case_vaf_percent}}.
```

Insert the Case VAF value through the picker or set its advanced Number output
to the `%` unit. The fact already uses percentage points; do not multiply it by
100 or append another `%` to a placeholder already formatted with that unit.
Use HGVS.c instead when required. Missing HGVS.p must have an intentional
missing-value policy or separate condition; silently omitting it can leave an
incomplete sentence.

Choose **Bullet point** for one finding per bullet, **New paragraph** for separate
paragraphs or **Continue previous sentence** for continuous wording. The negative
sentence must now live in a separate **Once per report** SNV block: a per-finding
block cannot produce text when there are no findings. If both blocks use the same
section name, keep their heading settings consistent and their identifiers unique.

### Tier-summary terminology example

This object contains the complete Swedish `tier_summary` phrase set used by the
software's standard reporting helper. It is an example for center review, not an
automatically approved publication. It can be used for hematology or solid
grouped summaries because the wording is driven by the prepared tiers and genes.

```json
{
  "tier_summary": {
    "first_prefix": "Vid analysen finner man ",
    "next_prefix": "Vidare ses ",
    "final_prefix": "Slutligen ses ",
    "number_gender": "n",
    "finding_singular": "mutation",
    "finding_plural_suffix": "er",
    "tier_labels": {
      "1": " av stark klinisk signifikans (Tier I)",
      "2": " av potentiell klinisk signifikans (Tier II)",
      "3": " av oklar klinisk signifikans (Tier III)",
      "4": " av benign/sannolikt benign (Tier IV)"
    },
    "single_gene_prefix": " i ",
    "multiple_gene_prefix": ": ",
    "gene_count_joiner": " i ",
    "value_open": " (",
    "value_close": ")",
    "read_context_prefix": "i ",
    "read_context_suffix": " av läsningarna",
    "multiple_gene_read_prefix_tiers": [1],
    "respectively": "respektive",
    "gene_joiner": "och",
    "sentence_suffix": ". ",
    "single_gene_always_read_context": false
  }
}
```

This is the value to merge into the exported rule set's `terminology` object,
not a complete rule-set export to upload by itself. Preserve other terminology
keys already present. Import the complete modified export as a draft and update
its embedded cases. Authoring it does not change an existing publication.

### 3F. Test the SNV branches before publication

| Synthetic scenario | Expected result |
| --- | --- |
| One eligible tier-I TP53 finding at 35% | Positive rule only; gene, tier and VAF appear |
| Two eligible findings in one gene | Positive rule only; grouped output contains both VAF labels |
| Eligible findings across tiers I, II and III | Ordered tier groups; no negative sentence |
| No prepared SNVs | Negative rule only when the SNV block is enabled for this report |
| Unclassified-only results | No invented classification; negative branch if no reportable tier group exists |
| Tier IV only with I–III configured | No positive I–III summary |
| Missing required nomenclature in the per-finding alternative | Visible error or the explicitly authored alternative |
| Disabled positive or negative rule in Exactly one mode | A matching scenario for the disabled branch fails rather than inventing text |

Use **Preview sample** for complete actual output, then **Test rules** for the
trace. Preserve synthetic embedded cases for both branches; live preview alone
does not satisfy the publication gate described below.

## 4. Add CNV and DNA-fusion text when the assay reports them

| Section | Evaluate | Match all conditions | Useful output values |
| --- | --- | --- | --- |
| CNV text | For each finding | Finding type is `cnv`; Copy-number effect is `gain` | Genes, chromosome, start, end and CNV recorded ratio; reviewed gain wording |
| CNV text, alternate rule | For each finding | Finding type is `cnv`; Copy-number effect is `loss` | The same facts; reviewed loss wording |
| DNA fusion text | For each finding | Finding type is `translocation` | First fusion gene, second fusion gene and available breakpoints |

Gain and loss rules can share an **At most one** block. Missing/unknown effect
requires a deliberate rule or omission, not an assumption of loss. Each-finding
blocks inspect all prepared candidates: include the Finding type condition.

Only report-prepared findings reach these rules. They cannot retrieve an excluded
CNV, restore a blacklisted SNV or change a query threshold.

Full numerical parity with `master` is not available from these output facts:
the older CNV composer calculates `2 * 2**ratio`, groups events, and uses PR/SR
evidence; its translocation composer groups gene pairs and reports PR/SR
percentages and unique-read counts. Those calculated/grouped CNV and DNA-fusion
evidence fields are not all registered in the current fact catalog. Do not label
the recorded ratio as copy number or substitute RNA spanning-read counts for
DNA PR/SR percentages. This walkthrough's CNV/fusion sentences describe the
available facts rather than claiming byte-for-byte output parity.

## 5. Add closing and accreditation wording

Choose **Start a section → Closing text**. Keep **Whole report**, **Once per
report**, **All matches**, and heading off. Use two rules:

- Unconditional closing rule: `För ytterligare information om utförd analys och
  beskrivning av somatiskt förvärvade mutationer, var god se bifogad rapport. `
- Accreditation rule: **Accredited is false**, then
  `Analysen omfattas inte av ackrediteringen.`

Both may match an unaccredited assay; this is why **All matches** is appropriate.
**At most one** would reject those two simultaneous matches.

## Advanced conditions

These examples extend the authoring patterns. They are not additional conditions
silently supplied by the old hematology composer.

### Require the same finding to satisfy every predicate

In a **Once per report** block, choose **Find in collection → Findings → At least
one**. Inside the collection condition, choose **Match all**:

```json
{
  "type": "collection_match",
  "collection": "findings",
  "quantifier": "any",
  "where": {
    "type": "all",
    "children": [
      {"type": "predicate", "fact": "item.kind", "operator": "eq", "value": "snv"},
      {"type": "predicate", "fact": "item.gene", "operator": "eq", "value": "TP53"},
      {"type": "predicate", "fact": "item.tier", "operator": "eq", "value": 1}
    ]
  }
}
```

This matches TP53 at tier I. Separate conditions for any TP53 finding and any
tier-I finding would also match TP53 at tier II plus another gene at tier I.
For a negative counterpart use the same inner predicate with quantifier `none`.

### Count only lists selected for SNV analysis

Use **Find in collection → Applied gene lists → A specific count**. Inside the
condition, require **Gene list selected analyses contains snv** (`item.selected_for`). Match
count equal to 1 for singular list wording, or greater than 1 for plural wording.
The collection includes selections for other analyses; counting it without that
inner predicate could include a CNV-only list in an SNV introduction.

### Optional biomarker conditions from the old composer

Do not add these sections just because the assay group is hematology. Add them
only when that assay performs and reports the corresponding measurement.

| Analysis | Evaluate / collection | Conditions combined with Match all |
| --- | --- | --- |
| HRD | For each collection item / HRD | Measurement method is `HRD`; Measured value is greater than `42` |
| MSI | For each collection item / MSI | Measurement method is the intended `MSIP` or `MSIS`; Measured value is greater than `15` |

These comparisons are strict: HRD 42 and MSI 15 do not match; values above them
do. Include Measured value and Measurement unit in the output; their units must
be verified in the prepared facts. The current measurement preparation retains
MSIP and MSIS as separate rows when both are supplied. A rule that accepts both
methods can therefore emit two sentences. To report one selected method, specify
that method explicitly. The old per-source-document MSIP/otherwise-MSIS preference
is not automatically reproduced by these per-item rules.

### Nested ranges, unknown values and conflicts

Use **Match all** to combine a lower inclusive bound and an upper exclusive bound,
such as Case VAF at least 5 and less than 10. Use a separate branch for Case VAF
at least 10. **Between** includes both endpoints, so adjacent ranges can overlap.
These numbers illustrate condition syntax, not an assay's clinical thresholds.

A present null needs **is unknown**; an absent path needs **is available → false**.
Negating an unavailable measurement does not prove the opposite clinical result.
Use **Exactly one** only when all expected candidates, including unknown data,
have one matching branch. Use a conflict group only for competing conclusions,
not for independent introduction sentences.

## Optional embedded cases

Embedded cases are not required or executed during validation, submission or
publication. You can complete this workflow entirely in the visual editor without
samples or test configuration. Existing `test_cases` data is preserved when saving,
but does not need to be maintained after wording changes. **Test rules** remains
an optional live-sample preview. See the
[validation and embedded-case reference](../reference/clinical-reporting-rules.md#validation-and-embedded-cases).

Existing case records have this shape:

| Key | Required content |
| --- | --- |
| `test_id`, `name` | Stable case identifier and readable scenario name |
| `facts` | Synthetic prepared context: sample, assay, configuration, selected lists, findings and aggregates |
| `expected_rule_ids` | Exact ordered rule identifiers expected to match |
| `expected_sections` | Exact output section names mapped to ordered lists of rendered strings |

Copy the authored rule IDs, not rule names, into the expected sequence. Facts
must describe a consistent scenario: empty findings need empty tier summaries
and false `has_tiered_snvs`; selected-list counts and germline intersections must
agree with the synthetic selections. Never use a patient's identity or exported
clinical text as reusable example facts. One trivial passing case does not cover
the positive, negative and missing-data branches of a complete assay.

## 6. Test, review and publish

Choose an authorized **Preview sample** in the combined summary panel to resolve
actual values for all matched rules after saving. Without a sample, the panel
shows the composition and labels conditional alternatives. **Text placement**
controls paragraph, continuation, line and list formatting for each matching rule.

Use **Validate**. When authorized samples are available, optionally use **Test rules**. Inspect matched
rule IDs, prepared facts, section text and traces. The bracketed composition view
does not execute sample conditions.

| Test case | Expected behavior |
| --- | --- |
| Paired versus unpaired | Control sentence appears only for paired analysis |
| One selected list versus multiple overlapping lists | Correct names and singular/plural wording; unique gene count |
| 20 versus 21 selected genes, if using the historical split | Gene list at 20; count at 21 |
| CEBPA selected versus excluded, paired versus unpaired | Constitutional sentence only for the selected germline intersection in paired analysis |
| Eligible tier I–III SNVs | Grouped or per-finding positive text, without the negative sentence |
| No eligible tiered SNVs, including unclassified-only results | Negative sentence, without a positive tier summary |
| No CNV/translocation findings | No per-finding CNV/DNA-fusion sentence |
| Accredited versus unaccredited | Accreditation disclaimer only when unaccredited |
| Missing assay display name or required measurement | Visible evaluation failure or explicitly authored missing-data branch |
| HRD/MSI boundaries, if those sections are used | Exact boundary does not satisfy the strict greater-than condition |
| Named diagnosis without an exact publication | Base fallback for the same assay, analyte and language |

Assign an independent clinical reviewer and submit. After approval, a permitted
publisher publishes the version. Check a normal sample report preview afterward.
Publishing affects new report preparation; it does not rewrite saved reports.
Keep rationale and supporting references with the rules. A rule set missing
compatible publication leaves the report available without an automatic summary
and produces the documented UI warning.
