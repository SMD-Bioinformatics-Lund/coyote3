# Build report wording from assay and sample data

For a complete worked assay, follow [create hematology Base reporting rules](hematology-base-reporting.md).
It walks from draft creation and a simple introduction through positive/negative
findings, nested collection conditions, biomarker boundaries, review and publication,
with a comparison to the default-branch composer.
For the same SNV pattern in a solid assay, including a named breast subpanel and
the distinction between exact scope and Base fallback, follow
[solid Base and diagnosis reporting examples](solid-reporting-examples.md).

Open **Administration → Reporting Rule Sets** and create or open a draft scoped
to an assay, diagnosis and language. A diagnosis of `base` means the base scope;
it does not stand for every named diagnosis. Published versions retain their
review history. Editing a draft does not change a published report snapshot.

Reporting rules are optional during assay setup. Until compatible rules are
published, reports remain available without an automatically generated summary;
assay setup and report preview show a warning. Published rules must pass validation
before they can supply report wording.

## Author before the assay is registered

Enter a planned lowercase **Assay** ID when creating a draft, or keep the intended
ID from an imported JSON file. A missing assay does not block draft creation,
import, or content edits. Existing inactive assays and incompatible analytes are
still rejected. Choose DNA or RNA yourself when the assay is not registered yet.

Once the assay is available, open **Assay association** in the draft and select
**Link to assay**, **Link to diagnosis**, then **Link assay**. Only assays with the
same DNA/RNA analyte are offered. The server validates the active assay or saved
setup scope and its diagnosis association. Registering the originally planned ID
also makes that scope available without needing to change the ID.

Linking edits the same draft, retaining its document ID, creator and revision
history. A changed scope receives the next content version in the target scope.
Review embedded case facts, assay-ID conditions and diagnosis-specific wording
after reassociation; they are not rewritten automatically. Scope changes use the
same edit lease and revision checks as other edits. Submitted and released
versions cannot be reassociated. Submission requires an available compatible
assay/diagnosis scope; a draft for an unregistered assay cannot enter review or
supply report wording.

## Start with named sections

The **Report wording** and **Bulk annotation text** tabs share the current draft
and review lifecycle. Report wording retains section/rule editing and report
preview. Bulk annotation text uses Tier I–III navigation, ordered conditional
templates and a synthetic finding preview; it saves annotations during opted-in
bulk tiering, not report prose. Switching tabs preserves edits and selection.
**Version notes** groups the change summary, governance details and revision
history. The change summary explains edits for reviewers and never enters report
or annotation text.

The normal path is **choose when → write the sentence → include and preview**.
Circular question-mark buttons explain each choice; hover, focus, or click to
read a hint, and press Escape to close it. Use **Section settings** only when you
need a different destination, analysis, evaluation mode, matching policy,
identifier or conflict group. These settings remain available for advanced rules.

Under **Start with a common scenario**, select paired/unpaired control, reportable
SNVs present/absent, at least one selected SNV list, or outside accreditation.
Selecting a scenario replaces the condition and preserves the sentence. Its
plain-language explanation remains visible; open **Refine condition** to adjust
the generated checks. Custom conditions remain expanded. In collection checks,
only items satisfying the inner condition are counted. Changing the collection
starts a new item condition; a specific count starts at **At least 1**.

Choose **SNV summary: findings / no findings** to create a once-per-report SNV
section with complementary true/false tiered-SNV conditions and **Exactly one**
matching. The positive rule contains grouped sentences; the negative rule has
editable wording. Missing Swedish terminology is copied into the draft for
review without overwriting configured wording. Other languages require reviewed
terminology in that language. Review and enable both alternatives, then preview
positive and negative cases before publication.

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
Select a rule and use **Move rule up/down** to change its position within the
section. Moving preserves the rule's identifier, conditions and wording. Changes
use the existing draft autosave. This order also determines precedence for
**First match** sections.

The rule-set ID stays `assay__diagnosis__language`, for example
`hema_gmsv1__base__sv`; content versions and revisions are separate fields.
New starter-rule IDs include their section context and purpose, for example
`hema_gmsv1_base_snv_summary_reportable_snvs_present`. Duplicate starters receive
unique suffixes. Display-name edits do not regenerate IDs, and existing IDs are
preserved. Open **Rule details and identifier** to inspect or deliberately edit
a rule ID; update embedded-case expectations when changing it. Clinical rationale
is available in its own reviewer-details panel.

## Compose the introduction without fixed names or counts

For clinical interpretation use **Report summary**. For method and scope wording
use **Analysis description**, as described below.

### Analysis description

Use **Start a section → Analysis description** for method and scope text printed
under **Analysbeskrivning**. Existing sections can select **Section settings →
Output destination → Analysis description**. This destination is separate from
**Report summary**, **Header suffix** and **Clinical question**. It supports the
same sentence editor, dynamic values, conditions, collection iteration and paragraph
placement as summary text. The report supplies the section heading.

Keep reviewed extraction, sequencing, limitations and validated sensitivity wording
in these rules. Insert assay names, covered-gene counts and applied gene-list names,
genes and unique counts through **Insert value at cursor**. Panel gene counts and
selected gene-list counts describe different scopes. For panel-DNA assays, the
selected scope includes only genes covered by the assay; the source list may be
larger. Full source list definitions remain available for provenance. Generated gene tables and
their captions remain part of report rendering. Table references inside authored
text are literal; review them against the rendered tables.

Publish shared assay wording in the assay's **Base** rule set. A diagnosis rule set
with no `analysis_description` block inherits only those blocks from the published
Base release for the same analyte and language. Conditions use the actual sample's
facts. An explicit diagnosis description overrides Base, including when its rules
are disabled or none match. Base summary and header text are not appended.
Sample previews show summary and analysis description separately and identify the
inherited source in evaluation provenance. Saved report receipts capture both releases.

Analysis descriptions are authored and published exclusively through clinical rules.

### Compose dynamic sentences

Report sentences, advanced literal and singular/plural text, structured wording,
clinical rationale, tumor-type wording and change summaries use the shared comment
Markdown editor. Use **Write** and **Preview** to switch between source and rendered
text, or select text and use the formatting toolbar. Saved read-only prose renders
as Markdown. Identifiers, numbers, field paths and condition literals retain their
structured meaning and do not become formatted query expressions.

Markdown can surround an inline value, for example
`**{{asp.display_name}}**`. Formatting preserves the value's type, precision,
missing-value behavior and list settings. The complete report preview renders
Markdown with placeholder labels until a sample resolves actual values. Preview
uses the same escaped-HTML and safe-link handling as comments. Existing comment
length limits remain unchanged; report wording has no new editor length limit.

Under **Report text**, write the complete sentence in **Report sentence**. Expand
**Insert value at cursor**, search by name, count, diagnosis or VAF, and choose a
value. The editor inserts a placeholder such as `{{asp.display_name}}` at the
cursor. You can also type known placeholders directly. Unknown or incomplete
placeholders are marked locally and pause saving until corrected.

For example:

```text
Sekvensanalysen omfattar exoner i {{asp.covered_genes_count}} gener som inkluderas i {{asp.display_name}} sekvenseringspanel.
```

Placeholders retain the existing typed value, number and list contracts; they do
not execute expressions or query the database. **Advanced output parts and
formatting** exposes precision, list conjunctions, missing-value behavior,
structured renderers and the individual parts when needed. Editing a sentence
preserves those settings for its existing placeholders.

### CNV calculations and summary sentences

CNV calculations run in report preparation. In a CNV section evaluated **for each
finding**, insert these values into a sentence:

| Value | Meaning |
| --- | --- |
| `finding.cnv_copy_number` | `2 × 2^ratio`, rounded to two decimals, without purity correction |
| `finding.cnv_paired_read_percent` | Alternate paired reads divided by total paired reads, as a percentage |
| `finding.cnv_split_read_percent` | Alternate split reads divided by total split reads, as a percentage |
| `finding.cnv_report_genes` | Genes carrying a classification key in the prepared CNV |
| `finding.cnv_other_gene_count` | Number of other gene records in the CNV |

Read counts accept reference/alternate pairs separated by commas or slashes.
Fractions are rounded to three decimals before conversion to percent. Missing,
malformed, nonfinite, negative, fractional-count and zero-total evidence remains
unknown; an observed zero alternate count remains `0.0`. Missing, nonfinite or
overflowing copy-number estimates remain unknown. Guard required values with
**Is unknown → Not**, or choose **Omit** for missing output values.

For grouped prose, set the CNV section to evaluate **once** and add this output
under **Advanced output parts and formatting → Structured summary → Grouped CNV
summary**:

```json
{"type": "renderer", "name": "cnv_summary"}
```

Use `aggregates.cnv_summary_count > 0` as the condition. The renderer reads
`aggregates.cnv_summaries` and requires `terminology.cnv_summary`. Expand **Edit cnv
summary wording** to add the supplied Swedish sentence wording for review, then
edit its fragments. All report wording remains part of the published rule set.

Preparation groups explicitly interesting calls by ordered classified genes and
gain/loss, preserving first-occurrence order. Calls without classified genes or
a known effect do not produce summary groups. Positive ratios mean gain;
nonpositive ratios mean loss. Without a ratio, stored AMP/DUP/GAIN and DEL/LOSS
types can supply the effect. Each group retains the largest GATK/CNVkit copy
number and other-gene count, and the last valid Manta paired/split percentages,
matching the established summary selection policy. An observed zero replaces
earlier support; unknown support does not. These groups do not change the finding
list, report filters or classifications.

Sentences use first/next/final leads, singular/plural gene labels and available
positive evidence. Missing evidence does not create empty parentheses. The CNV
analysis must also be enabled in the assay's report sections and declared with
`narrative: "enabled"` in the rule set. Importing a rule does not enable CNV
reporting in assay settings.

### Swedish introduction sentences

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

The introduction starter includes separate paired and unpaired control sentences,
both disabled until reviewed. Their conditions are complementary; replace the
generic wording if the assay requires a more specific statement about material.

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

**Complete report summary** combines enabled rules in section and rule order.
Without a selected sample, **Report structure** shows an ordered card for each
enabled sentence, with its rule name, conditional status and placement (continue,
new paragraph, new line or list item). Conditional sentences stay separate rather
than being joined into one misleading paragraph. **When this sentence applies**
expands the condition; **Show conditional wording** hides or reveals conditional
text while retaining its place in the outline. Each section states its match
behavior and whether its heading appears in the actual report. Brackets represent
unresolved dynamic values; this structure view does not evaluate conditions. Users with
`clinical_rules:test` can choose an authorized **Preview sample** to evaluate all
conditions and resolve actual values on the server. The preview refreshes after
valid edits save. Invalid edits and failed autosaves pause it; preview errors
appear inline instead of generating repeated notifications. **Test rules** provides
the separate sample-testing and trace workspace. Include paired/unpaired, empty/positive findings, overlapping
gene lists, missing names and relevant diagnosis scopes in clinical acceptance.
Then validate, assign the independent clinical reviewer and submit. Section
starters do not install approved clinical thresholds or publish a rule set.
Initial configuration can enter review before samples or embedded test cases are
available. Missing embedded cases produce a warning in the rule workspace and
the assigned reviewer's notification. Existing cases must pass before submission;
structural and semantic rule errors still block it.

**Validate** separates blocking errors from warnings. Missing embedded cases do
not block submission, but publication still requires passing embedded cases.
These cases use prepared facts and expected text; they do not require a live sample.
**All matches** intentionally combines independent introduction or closing
sentences and is not an overlap error. Use **Exactly one** or **At most one** for
mutually exclusive conclusions. **First match** uses configured numeric rule order;
validation warns when an earlier unconditional or identical rule makes a later
rule unreachable. The editor shows imported sections and rules in evaluation order.
Header suffix and clinical question each permit one value; validation still warns
when their **All matches** configuration could produce several values. Deleting
an earlier section or rule preserves the current selection when it still exists.

For a once-per-report SNV rule, **Use grouped SNV sentences** replaces that rule's
output with grouped tier/gene/VAF prose and adds missing Swedish terminology
for review. It preserves existing shared terminology and does not add a table.
Configured findings tables remain controlled by the report configuration.
For an existing summary without wording, **Add Swedish sentence wording** repairs
the missing terminology without replacing the rule's output. Other languages
require wording supplied for that language.

When a rule uses a **Structured summary**, expand **Edit … wording** below its
output to edit the configured sentence fragments, tier labels, number settings
and separators. Changes affect every use of that renderer in the draft. A renderer
without configured terminology is not ready to use: copy a reviewed rule-set
template with its terminology, or compose explicit text and dynamic values.
Avoid adding both a complete literal introduction and a structured introduction
unless the combined text is intentional.

## Choose where each conditional sentence appears

Each rule has a **Text placement** selector. It applies only if that rule matches:

| Choice | Result within the same output section |
| --- | --- |
| New paragraph | Start a separate paragraph; this is the default for existing rules |
| Continue previous sentence | Append to the previous matched wording, inserting a separating space when needed |
| New line | Add a Markdown hard line break after the previous matched wording |
| Bullet point | Add a bullet; consecutive bullet rules share a list |
| Numbered list item | Add a numbered item; consecutive numbered rules share a list |

Introduction starters continue the first sentence for the following independent
control/list sentences. If no preceding rule matches, continuation or line layout
starts the section normally. A rule that does not match contributes no separator
or empty list item. Section headings remain controlled separately by **Show section
heading**. Header suffix and clinical-question outputs retain paragraph placement.
Changing placement changes the rendered section text. Update the embedded cases'
expected sections and complete the normal review before publishing that change.

## Import and export rule configuration

Use **Import JSON** beside **Export JSON**, or choose **New rule set → Import JSON**.
Upload authored configuration, review the inferred scope/name, and create the
draft. Files contain `scope`, `name`, `analysis_declarations`, `terminology`,
`blocks`, `test_cases` and `references`. Optional `schema_version` identifies the
file syntax and defaults to `1`; it is separate from the application's rule versions.

Do not supply author, timestamps, document identity, content version or revision.
The application allocates the version and records the authenticated importing user
and current timestamps. It creates an inactive draft with fresh review and lifecycle
state. Import does not overwrite or publish the source version. Embedded cases and
structured terminology are retained and validated.

**Export JSON** downloads configuration without application-managed metadata by
default. Check **Include metadata** to include the stored version's identity,
timestamps, authors, content version, revision, provenance and lifecycle for inspection.
Both export forms can be imported. Included metadata is ignored when importing;
it cannot restore approval, publication, ownership or version numbers. Unknown
configuration fields and invalid authored rule content are still rejected.
Valid source version and revision numbers from a metadata-inclusive file remain
informational import provenance; the new draft receives its own version and revision.

The API exposes the same default at
`GET /api/v1/admin/clinical-rule-sets/versions/{document_id}/export`; add
`?include_metadata=true` to request metadata explicitly. Normal version and revision
endpoints continue to return the complete governed records.

## Correct an autosave error

Availability predicates such as **is available** require a Yes/No value even for
numeric or list facts. The editor changes the value type when the operator changes.
Incomplete conditions remain local until valid. If a save fails, autosave pauses
for that edit instead of retrying continuously. Correct the highlighted input or
use **Retry save** after resolving the reported problem. Keep unsaved wording
before leaving the editor.

## Relationship to the previous report composer

The default branch (`master`) composes introduction, tiered SNVs, CNVs, DNA
fusions, biomarkers and closing accreditation wording in
`coyote/blueprints/common/util.py`. The current editor separates those decisions
into conditions, output values and ordered sections. Existing named structured
renderers retain their governed terminology and behavior; adding the new dynamic
facts does not rewrite published rule wording. See the
[rule contract and evaluator reference](../reference/clinical-reporting-rules.md)
for supported facts, renderers and validation rules.
