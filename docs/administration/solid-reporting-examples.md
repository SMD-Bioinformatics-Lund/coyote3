# Solid-tumour reporting: Base and diagnosis examples

This walkthrough creates Swedish DNA narrative rules for `solid_gmsv3`, first
for Base and then for a named diagnosis/subpanel `breast`. Use the actual assay
and diagnosis IDs registered at your center if they differ. Identifiers are
lowercase; display names and report wording can use normal capitalization.

The examples explain software configuration. The illustrated gene/tier/VAF
combinations are synthetic, not automatic classification rules or new clinical
thresholds. Use reviewed classifications, eligible findings and approved wording.

## Choose the scope before writing conditions

| Resource | Base example | Diagnosis example |
| --- | --- | --- |
| Biological group | `solid` | `solid` |
| Physical assay | `solid_gmsv3` | `solid_gmsv3` |
| Diagnosis/subpanel | `base` | `breast` |
| Rule-set identity | `solid_gmsv3__base__sv` | `solid_gmsv3__breast__sv` |
| Analyte and language | DNA, `sv` | DNA, `sv` |
| Applicable configuration | Base and the sample's environment | Breast and the sample's environment |

The rule scope uses the physical assay and diagnosis, not just the biological
group. In the current sample schema, the diagnosis/subpanel value is
`diagnosis_id`. Do not add a separate `subpanel` field to new rule definitions.

Base needs no separately registered diagnosis. A named diagnosis must be created
and associated with this assay before it is selected for authoring. Use
[diagnosis definitions and assay associations](assay-diagnoses.md) to prepare that
relationship. Having a breast diagnosis elsewhere does not associate it with
every solid-tumour assay.

## Example A: solid Base

### A1. Prepare the configuration and create the draft

Check the assay's display name, covered genes, accreditation and actual method.
Select the intended SNV gene lists in the applicable configuration/sample
settings. A gene list merely associated with the assay is not automatically
selected for every report.

For this example, the configuration includes SNV as a report section with
reportable tiers I, II and III. These choices determine the prepared report
findings. Wording rules do not replace query filters, restore excluded findings
or assign a clinical tier to a gene.

Open **Administration → Reporting Rule Sets → New rule set → Build in UI**:

| Field | Value |
| --- | --- |
| Assay | `solid_gmsv3` |
| Diagnosis | Base (`base`) |
| Analyte | DNA, derived from the assay |
| Language | `sv` |
| Name | For example, `Solid Base - Swedish DNA report` |

Choose **Create draft**. In **Report analyses**, choose **SNV → Generate text**.
For every other analysis selected in the configuration's report sections,
explicitly choose **Generate text** or **No narrative**. Do not leave a configured
analysis undeclared. **No narrative** concerns rule-generated prose; it does not
by itself remove that analysis's results table.

### A2. Write a dynamic introduction

Choose **Start a section → General introduction**. Keep **Whole report**,
**Once per report**, **All matches**, and heading off. The starter's rules are
disabled until reviewed. Enable only the intended reviewed rules.

For the unconditional assay/method rule, write one sentence using inline values:

```text
DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i {{asp.covered_genes_count}} gener som inkluderas i {{asp.display_name}} sekvenseringspanel.
```

Use **Insert value at cursor** for the gene count and display name. Substitute
`{{asp.name}}` only when the assay's short name is configured and that is the
intended wording. The count is the unique genes in the assay's covered-gene
definition; it is not a count of detected variants. The literal method sentence
must reflect the validated panel workflow; metadata alone does not prove the
claimed method or exon coverage.

Keep paired and unpaired control statements in separate conditional rules:

| Rule | Fact / operator / value | Example generic sentence |
| --- | --- | --- |
| Paired control | Paired analysis / is / Yes | `Analysen har utförts med ett parat kontrollprov.` |
| Unpaired control | Paired analysis / is / No | `Analysen har utförts utan parat kontrollprov.` |

Use **Continue previous sentence** for both. They are alternatives, so one may
contribute wording in a given report. Leave either rule disabled when no such
sentence is intended. Do not assert skin biopsy or another control tissue solely
from the paired flag. Do not copy hematology-specific CEBPA wording into solid
rules without a separate approved reason and matching data.

For selected-list wording, require **SNV selected lists: unique gene count is
greater than 0** and compose:

```text
Valda genlistor: {{gene_lists.snv.names}}. Analysen omfattar {{gene_lists.snv.gene_count}} unika gener.
```

The names come from the selected lists' short names. Use advanced list formatting
to set conjunction `samt`; choose full names or identifiers instead if required.
Overlapping genes count once. The generic plural wording avoids falsely implying
that only one list was selected. The [hematology example](hematology-base-reporting.md#rule-c-the-gene-lists-actually-selected)
explains singular/plural alternatives and the historical 20-gene list/count split.

### A3. Create the SNV section

Choose **Start a section → Variant text**, then set:

Alternatively choose **SNV summary: findings / no findings** to create the two
aggregate conditions directly, with missing Swedish wording supplied for review.
Open **Section settings** to inspect the settings below. Review and enable both
rules; they start disabled. Use the manual Variant text route when you need a
different pattern.

| Section setting | Value |
| --- | --- |
| Output destination | Report summary |
| Section | `Kliniskt relevanta SNVs och små INDELs` |
| Section identifier | For example, `solid_gmsv3_base_snv` |
| Analysis | SNV |
| Evaluate | Once per report |
| Match behavior | Exactly one |
| Show section heading | On, or deliberately off |

The starter initially evaluates per finding. Change that mode, remove its
Finding type condition, and create the two aggregate rules below. Their boolean
conditions are complements, so **Exactly one** verifies one branch matched for
each report where this SNV block is evaluated.

### A4. Positive SNV rule

| Rule setting | Value |
| --- | --- |
| Clinical rule name | `Reportable SNVs present` |
| Rule identifier | For example, `solid_base_snv_positive` |
| Include this rule | Enabled after review |
| Fact | Has tiered SNVs |
| Operator | is |
| Value | Yes |
| Text placement | New paragraph |

```json
{
  "type": "predicate",
  "fact": "aggregates.has_tiered_snvs",
  "operator": "eq",
  "value": true
}
```

Choose **Use grouped SNV sentences** above the sentence editor. This replaces
the starter text with grouped prose and adds missing Swedish wording for review.
It does not create a table or change the configured report tables. This groups eligible variants
by their already assigned tier and gene, with case-VAF labels. It does not infer
significance from the gene's name or introduce a VAF threshold.

The renderer requires `terminology.tier_summary`. The insertion action supplies
it when missing; existing wording is preserved. If the renderer was already
added through advanced parts, choose **Add Swedish sentence wording** under
**Edit tier summary wording**, or use a reviewed assay template. The
[complete Swedish terminology example](hematology-base-reporting.md#tier-summary-terminology-example)
documents the export format; it is not a complete rule-set export itself.
Review **Edit tier summary wording** before enabling the rule.

For a synthetic EGFR finding already assigned tier II at 23% case VAF, that
terminology produces:

> Vid analysen finner man en mutation av potentiell klinisk signifikans (Tier II) i EGFR (i 23% av läsningarna).

This sentence appears because the reviewed finding is eligible and tiered, not
because this rule assigns every EGFR finding to tier II.

### A5. Negative SNV rule

Choose **Add rule** in the same section:

| Rule setting | Value |
| --- | --- |
| Clinical rule name | `No reportable tiered SNVs` |
| Rule identifier | For example, `solid_base_snv_negative` |
| Include this rule | Enabled after review |
| Fact | Has tiered SNVs |
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

In **Report sentence**, enter the reviewed negative wording, for example:

```text
Vid analysen har inga somatiskt förvärvade mutationer i undersökta gener påvisats.
```

Keep the positive and negative rules conditional. An unconditional negative
rule would overlap positive results and fail **Exactly one** evaluation.

Do not replace the negative condition with **SNV count is zero**: unclassified
findings can exist without a reportable tier group. A tier-IV-only result also
does not create a positive I–III summary when tier IV is not reportable. The
negative sentence concerns the examined analysis scope; no findings alone is
not evidence that a measurement was performed successfully.

### A6. Optional per-finding wording instead of the grouped renderer

To write one sentence or bullet per variant, use **For each finding** and a
**Match all** condition:

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

Write:

```text
I {{finding.gene}} påvisas {{finding.hgvsp}} med variantallelfrekvens {{finding.case_vaf_percent}}.
```

Case VAF inserted through the picker uses percentage formatting. Do not multiply
it by 100 or append a second percent sign. For example, a prepared 23-percent
value should render once as `23%`. Set a reviewed precision under advanced
Number formatting. Use HGVS.c or an explicit alternate rule if HGVS.p is missing;
silently omitting it can leave a misleading or incomplete sentence.

Choose **Bullet point**, **New paragraph** or **Continue previous sentence** for
the intended placement. Keep the negative rule in a separate **Once per report**
SNV block: an empty collection supplies no per-finding candidates. If the blocks
share a section name, use the same heading choice and distinct identifiers.
Disable the grouped positive renderer when adopting this alternative unless
duplicate descriptions are intentional.

### A7. Closing and other analyses

Add **Closing text**, with **Whole report**, **Once per report**, **All matches**
and heading off. Use an unconditional reviewed closing sentence, plus a separate
**Accredited is No** rule for the accreditation disclaimer. Both may match an
unaccredited assay; **Exactly one** would be wrong for those independent additions.

CNV, DNA-fusion and biomarker narrative require their own explicit analysis
declarations and reviewed blocks. The [hematology walkthrough](hematology-base-reporting.md#4-add-cnv-and-dna-fusion-text-when-the-assay-reports-them)
describes the current facts and the limits of reproducing older numerical
summaries. Do not add HRD/MSI thresholds merely because the biological group is solid.

## Example B: the same assay with a breast diagnosis/subpanel

### B1. Register the diagnosis and its analysis scope

Create diagnosis ID `breast` with the intended display name and associate it with
`solid_gmsv3`. Prepare the breast configuration for each required environment,
including SNV report sections, reportable tiers and actual selected gene lists.
A list ID such as `breast-snv` is illustrative; select a registered list containing
the reviewed gene scope for this assay rather than assuming that ID exists.

At report preparation, the sample should have `asp_id: solid_gmsv3` and
`diagnosis_id: breast`. Report-language selection comes from the applicable
configuration. The physical panel count still describes the assay's covered
genes; the selected SNV count describes the breast sample's effective gene scope.
Changing the narrative does not select those lists or change query filtering.

### B2. Create a complete diagnosis draft

Use **New rule set → Use template** to copy a reviewed published rule set from
the same assay, selecting `solid_gmsv3` and diagnosis `breast`. A published Base
version is a suitable starting point. If Base is still a draft, use its complete
**Export JSON → Import JSON**, selecting the breast target scope. A blank draft
is also possible but needs all intended sections, terminology and cases authored.

| Field | Value |
| --- | --- |
| Assay | `solid_gmsv3` |
| Diagnosis | `breast` |
| Language | `sv` |
| Name | For example, `Solid breast - Swedish DNA report` |
| Resulting identity | `solid_gmsv3__breast__sv` |

Review the imported scope and name before creation. Import/copy creates a draft;
it does not change the source Base publication or publish the new diagnosis.
Review every copied section, including closing text, analysis declarations and
terminology. Remove or replace statements that do not apply to the breast workflow.

### B3. Keep the positive and negative SNV pattern

Use the same **Once per report**, **SNV**, **Exactly one** section settings and
the two complementary **Has tiered SNVs** predicates from A4/A5. The rule IDs can
be named `solid_breast_snv_positive` and `solid_breast_snv_negative`. If copied
rule IDs are renamed, update the embedded cases' expected IDs too. IDs must be
unique within the new rule set; copying does not require inventing new clinical
conditions.

No additional `sample.diagnosis_id is breast` predicate is needed merely to
restrict this rule set: runtime selection already chooses the breast scope.
The positive renderer sees findings prepared for that sample's breast
configuration and effective selections, rather than every variant associated
with the solid biological group.

For a synthetic PIK3CA finding already assigned tier I at 18% case VAF:

> Vid analysen finner man en mutation av stark klinisk signifikans (Tier I) i PIK3CA (i 18% av läsningarna).

For no eligible reportable tier groups, the negative rule emits the reviewed
negative sentence instead. Do not retain a second unconditional negative
sentence from a copied introduction.

### B4. Add diagnosis-specific wording when required

For an introduction specific to this scope, add a reviewed sentence such as:

```text
Analysen avser den valda genlistan för brösttumörer: {{gene_lists.snv.names}}, omfattande {{gene_lists.snv.gene_count}} unika gener.
```

Require a nonempty selected SNV scope, and use **Continue previous sentence** or
**New paragraph** as intended. Replace the generic selected-list sentence if the
two statements would duplicate each other. Keep names and counts dynamic.
`{{sample.diagnosis_id}}` inserts `breast`, the identifier; it is not a full
diagnosis display-name fact. Use reviewed literal diagnosis wording or selected
list display names rather than inventing an unsupported placeholder.

If a separately approved diagnosis-specific statement concerns an individual
finding, use **For each finding** and combine its predicates on that finding:

```json
{
  "type": "all",
  "children": [
    {"type": "predicate", "fact": "finding.kind", "operator": "eq", "value": "snv"},
    {"type": "predicate", "fact": "finding.gene", "operator": "eq", "value": "PIK3CA"},
    {"type": "predicate", "fact": "finding.tier", "operator": "eq", "value": 1}
  ]
}
```

This is an example of matching an already classified finding, not a recommendation
to assign every PIK3CA variant to tier I or to emit a particular treatment statement.
For whole-report conclusions use a collection condition with the same predicates
inside a single item match; separate existential predicates can match different
findings. See [advanced same-finding conditions](hematology-base-reporting.md#require-the-same-finding-to-satisfy-every-predicate).

If this specific sentence belongs alongside a general per-finding description,
use separate blocks or deliberately choose **All matches**. If both are in one
**At most one** block and both conditions match, evaluation fails. Assign a
conflict group only when the conclusions are intended to be mutually exclusive.

## Which publication is used?

For the same assay, DNA analyte and `sv` language:

| Sample diagnosis | Active published documents | Selected source |
| --- | --- | --- |
| `base` | Base and breast | Base |
| `breast` | Base only; breast is absent or still a draft | Base |
| `breast` | Base and breast | Breast only |
| `breast` | Breast only | Breast |
| `crc` | Base and breast, but no CRC publication | Base |
| `breast` | Neither compatible publication exists | Report available without automatic summary, with a UI warning |
| `breast` | Breast publication exists but fails integrity/schema validation | Preparation fails; invalid exact content does not silently fall back |

Base and diagnosis publications are not automatically concatenated. A breast
publication is a complete selected source: a missing closing or SNV block is
not filled from Base. Editing Base later does not update a previously copied
breast rule set. Review shared wording changes in both versions where applicable.
Configured clinical-rule profiles are a separate composition mechanism; do not
confuse them with Base-versus-diagnosis publication selection.

If the only difference is a short diagnosis sentence, you can instead keep one
Base publication with a conditional once-per-report rule:

```json
{
  "type": "predicate",
  "fact": "sample.diagnosis_id",
  "operator": "eq",
  "value": "breast"
}
```

That rule can add reviewed breast wording when Base is actually selected for a
breast sample. It will not run alongside a separately selected breast publication.
Choose one approach deliberately: a complete diagnosis publication for distinct
governed content, or a small conditional addition in a shared Base source.

## Test Base and diagnosis behavior before publication

Use **Preview sample** in the complete-summary panel to resolve all matching
rules with actual authorized data. Base defaults to assay-wide sample matching;
use the diagnosis matching control when comparing scopes. **Test rules** provides
the execution trace. Its explicit diagnostic selection does not publish or change
normal runtime source selection.

| Case | What to verify |
| --- | --- |
| Base sample with an eligible tier-II finding | Base positive rule; correct tier/gene/VAF; no negative sentence |
| Base sample with no tiered findings | Base negative rule only |
| Breast sample before breast publication | Base fallback and breast sample's actual selected-list names/count |
| Breast sample after breast publication | Breast source only; no duplicate Base introduction or closing |
| Breast sample with an eligible synthetic PIK3CA tier-I finding | Diagnosis positive rule; extra finding statement only if explicitly authored |
| Breast sample with no reportable tier groups | Diagnosis negative rule only |
| CRC sample after breast publication | Breast source is not selected for CRC |
| Unclassified-only or excluded tier-IV results | No invented tier; negative branch where no eligible tier group remains |
| Overlapping selected lists | Unique gene count; correct effective list names |
| Paired versus unpaired samples | Exactly the intended control-material wording |
| Per-finding output with missing HGVS.p | Required-value error or the deliberate alternate wording |
| More than one matching alternative in a strict block | Evaluation failure, not silently selected conflicting prose |
| Another reporting language | No silent cross-language fallback |

Retain synthetic embedded cases with exact expected rule IDs and section text
for both Base and breast drafts. Updating a copied scope requires changing the
case facts to the correct assay/diagnosis/configuration identities. Recheck
counts, matched rules, formatting and full output after any wording or placement
change. Live sample preview does not create embedded cases; see the
[embedded-case prerequisite](hematology-base-reporting.md#publication-prerequisite-embedded-cases).

Validate, assign an independent clinical reviewer, submit, obtain approval, and
publish with the permitted publisher account. Check a normal report preview for
each target scope afterward. New publications affect newly prepared reports;
saved reports retain their original wording and provenance.
