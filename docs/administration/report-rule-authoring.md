# Build report wording from assay and sample data

Open **Administration → Reporting Rule Sets** and create or open a draft scoped
to an assay, diagnosis and language. A diagnosis of `base` means the base scope;
it does not stand for every named diagnosis. Published versions retain their
review history. Editing a draft does not change a published report snapshot.

Reporting rules are optional during assay setup. Until compatible rules are
published, reports remain available without an automatically generated summary;
assay setup and report preview show a warning. Published rules must pass validation
before they can supply report wording.

## Start with named sections

Use **Start a section** to add General introduction, Variant text, CNV text,
DNA/RNA fusion text, HRD/MSI/TMB text or Closing text. Available analyses depend
on DNA/RNA scope. Section identifiers derive from the assay, diagnosis and section
type, with a suffix for duplicates. These identifiers are internal references;
the editable section name is the report heading.

Starters are editable and their rules are disabled until reviewed. Introduction
and closing sections default to **Show section heading** off. Any summary section
can omit its heading while keeping its text. **Add section** creates a custom
section. Header suffix and clinical question remain separate output destinations.
Use **Move section up/down** to arrange introduction, analysis text and closing
wording in report order; moving a section preserves its identifiers and rules.

## Compose the introduction without fixed names or counts

Under **Report text**, expand **Insert dynamic value**. Search by name, count,
diagnosis, VAF or another value. Select a value to append it, then use the move
buttons to place it between text parts. Text parts contain the surrounding
wording, spaces and punctuation. Values are resolved from prepared report data,
not by evaluating arbitrary expressions or querying the database from the rule.

For the Swedish introduction, compose:

| Text or value | Source / control |
| --- | --- |
| `DNA har extraherats från insänt prov och analyserats med massivt parallell sekvensering (MPS, även kallat NGS). Sekvensanalysen omfattar exoner i ` | Text; enter center-reviewed method wording |
| Panel gene count, such as `385` | **Assay covered gene count** (`asp.covered_genes_count`) |
| ` gener som inkluderas i ` | Text |
| `GMS-HEM v1.1` | **Assay full display name**, or **Assay short name** if configured |
| ` sekvenseringspanel. ` | Text |
| Paired-control sentence | Separate rule using **Paired case/control analysis**; enter the reviewed tissue wording |
| `Analysen omfattar genlistan: ` | Text in the selected-list rule |
| Selected list label | **SNV selected lists: short names**, full names, or identifiers |
| ` som innefattar ` + count + ` gener. ` | **SNV selected lists: unique gene count** |
| Constitutional investigation wording | Separate paired rule with **SNV selected lists: selected germline genes** |

The assay's optional **Short name** is edited in assay identity. Existing assays
without one do not silently substitute their identifier. Gene-list **name** is the
short name and **displayname** is the full name. They are read from the exact
gene-list revision released with the applied configuration, not a newly edited
list elsewhere in administration.

The panel count and selected-list count have different meanings. Panel count is
the unique genes in the assay's `covered_genes`. The selected SNV count is the
union of genes in lists actually selected for SNV analysis; overlapping genes
count once. CNV, fusion and other analyses have separate selections and counts.
Neither count is the number of detected variants. A diagnosis identifier can be
inserted from **Diagnosis**, but diagnosis alone is not a gene list and has no
independent gene count. Use the selected lists for that diagnosis's configuration.

Do not assert that the control is a skin biopsy merely because analysis is paired.
The control-material sentence must reflect the center's reviewed workflow. The
starter leaves that wording for the author. Missing required scalar values fail
evaluation; **Omit if missing** must be an intentional authoring choice.

## Conditions and analysis-specific text

**Common condition** supplies paired/unpaired, no SNV/CNV findings and
non-accredited assay starting points. **Add condition** opens the full editor:

- **Match all / Match any / Exclude when** combine or negate conditions.
- For per-finding sections, choose gene, tier, consequence, exon/intron, case/control
  VAF, CNV gain/loss or fusion fields. VAF facts labelled percent use percentage
  points. Do not enter a fraction where a percentage is expected.
- **Find in collection → Applied gene lists** can match a list identifier, name,
  selection domain or gene membership. This tests whether a list was actually
  applied; association with the assay alone is insufficient.
- HRD/MSI/TMB sections use **For each collection item** and the corresponding
  measurement collection. Method, value, unit and available components are facts;
  clinical thresholds and wording belong in reviewed rules.

Introduction and closing starters use **All matches**, allowing independent
sentences to be added. Alternative mutually exclusive wording should use **At most
one** or **Exactly one** where appropriate. **First match** depends on rule order;
**All matches** may deliberately produce several sentences.

Use a separate **Once per report** rule for a negative finding sentence. A rule
evaluated **For each finding** cannot emit text when there are no findings. Review
the difference between no findings and no reportable tiered findings before
choosing a count condition.

## Preview and validate

The live preview displays bracketed value labels; it is a composition preview,
not a sample evaluation. **Test rules** resolves values and conditions against an
authorized sample. Include paired/unpaired, empty/positive findings, overlapping
gene lists, missing names and relevant diagnosis scopes in clinical acceptance.
Then validate, assign the independent clinical reviewer and submit. Section
starters do not install approved clinical thresholds or publish a rule set.

When a rule uses a **Structured summary**, expand **Edit … wording** below its
output to edit the configured sentence fragments, tier labels, number settings
and separators. Changes affect every use of that renderer in the draft. A renderer
without configured terminology is not ready to use: copy a reviewed rule-set
template with its terminology, or compose explicit text and dynamic values.
Avoid adding both a complete literal introduction and a structured introduction
unless the combined text is intentional.

## Relationship to the previous report composer

The default branch (`master`) composes introduction, tiered SNVs, CNVs, DNA
fusions, biomarkers and closing accreditation wording in
`coyote/blueprints/common/util.py`. The current editor separates those decisions
into conditions, output values and ordered sections. Existing named structured
renderers retain their governed terminology and behavior; adding the new dynamic
facts does not rewrite published rule wording. See the
[rule contract and evaluator reference](../reference/clinical-reporting-rules.md)
for supported facts, renderers and validation rules.
