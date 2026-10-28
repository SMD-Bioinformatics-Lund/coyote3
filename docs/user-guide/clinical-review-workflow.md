# Clinical review workflow

Clinical review progresses from sample selection through analysis, classification,
and report preparation. Page controls and their effects on clinical records are
documented in the [application user guide](application-guide.md).

**You need:** access to a ready sample and permission for the review/report actions
you intend to perform. **You finish with:** reviewed findings and a saved report,
or a recorded reason why review cannot continue. Follow the steps on this page;
the DNA, RNA and coverage references provide extra detail only when needed.

![Clinical review responsibilities and evidence](../assets/diagrams/clinical-review-flow.svg)

## 1. Find the sample

Open **Samples**, select the date range and assay scope, then search by sample
or case identifier. Select the sample name to open its workspace.

| Sample state | Meaning |
| --- | --- |
| Ready | The required ingest transaction committed. Optional expected evidence may still be unavailable. |
| Unreported | No saved report has completed the sample workflow. |
| Reported | At least one report has been saved. |
| Base configuration | No diagnosis-specific ASPC was active, so the base ASPC was resolved. |

## 2. Check the overview

Before reviewing findings, confirm the sample identity, case and control
metadata, assay, ASPC, pipeline, loaded files, and analysis status. Stop if these
details do not match the submitted case.

The available pages come from the sample omics layer and resolved ASPC. A
missing page normally means that the analysis is not enabled for the sample; it
does not mean that the result set is empty.

## 3. Choose a layout

| Layout | Behavior |
| --- | --- |
| Classic | Shows all enabled finding sections on one page. Each section has its own filter button. |
| Modern | Shows one enabled analysis at a time in tabs. |

The selected layout is saved in the user profile and reused at the next login.

## 4. Apply filters

Open **Filters** for the analysis being reviewed. The panel contains only
controls valid for that sample and analysis type.

| Analysis | Common controls |
| --- | --- |
| Somatic SNVs | Depth, alternate reads, VAF, population frequency, consequences, and SNV gene lists. |
| Germline SNVs | Germline policy, frequency, consequence, and germline gene scope. |
| CNVs | Size, gain/loss cutoffs, effect, caller evidence, and CNV gene lists. |
| DNA translocations | Gene lists and configured structural-event conditions. |
| RNA fusions | Spanning evidence, caller, effect, evidence descriptions, and fusion gene lists. |
| Coverage | Coverage cutoff, gene search, and blacklist controls. |

Applying a filter runs a backend query against the complete matching set. It is
not limited to the rows on the current page.

## 5. Review and classify findings

Open a finding to inspect its evidence, transcripts, annotations, comments, and
external references. Table actions and detail-page actions update the same
persisted finding state.

| State | Use |
| --- | --- |
| Tier | Clinical classification stored in the annotation collection. |
| False positive | Technical or calling artifact. |
| Irrelevant | Valid finding outside the current clinical question. |
| Interesting | Review marker; it does not by itself include a finding in a report. |
| Blacklisted | Finding excluded through the governed blacklist workflow. |

Bulk actions require row selection and confirmation. Available actions depend
on the analysis type and the user's permissions.

### How a tier is matched

An automatic clinical tier requires a matching finding identity and the sample's
biological group, assay and diagnosis, in a visible annotation namespace. A tier
from another scope is supporting context and requires re-tiering. RNA fusion tables
and detail pages use the same selected caller's identity; see
[fusion tier matching](rna-review.md#fusion-tier-matching).

Inactive annotations do not automatically tier new samples. A recorded assignment
or report link can preserve an inactive historical tier for its original sample.
The classification card shows the current match and other matching versions, newest
first, with tier, recorded text, author and time. The current tier button uses full
color; the remaining buttons are subdued.

Use **Deactivate** to retire the current scoped tier while preserving history.
**Deactivate group annotations**, where permitted, retires this finding's matching
annotations across the group's assays and diagnoses in the same namespace. See
[deactivation and sample history](actions-and-record-changes.md#inactive-annotations-and-sample-history).

Knowledgebase evidence grades have their own meaning. **CGC Tier 1/2**, for example,
is COSMIC Cancer Gene Census evidence about a gene, not Coyote's clinical variant
tier. Its badge provides a source-specific explanation and link.

### Search previous interpretations

Open [Tiered Variant Search](pages-and-table-columns.md#tiered-variant-search), choose
the search mode and filters, and submit the query. Results identify active and inactive
annotations and show recorded sample/report links. For legacy annotations without
such links, the latest matching version can appear with a disclaimer above the table.
That fallback does not establish which tier a particular sample used.

## 6. Add comments

Use sample comments for report-level interpretation and finding comments for a
specific event. Global annotations are shared across matching findings and
should be used only when the text is valid beyond one sample.

Hidden comments are inactive. Users with the required permission can reveal
them with **Show hidden comments** and restore them when appropriate.

## 7. Prepare the report

If you use generated reporting-rule wording, request the suggestion in the sample
comment editor, review it and save the comment. A generated suggestion is a draft;
requesting it does not save a sample comment or a report. If no published reporting
rules resolve, the report remains available and the UI warns that an automatic
summary is unavailable.

Open **Reports** and review the temporary preview. The report conclusion uses the
latest visible sample comment; no comment produces an empty summary. Reported
finding rows are built from the current reportable findings and enabled report
sections.

Saving a report stores:

- the rendered report and artifacts;
- the resolved ASPC and reporting-rule identity;
- the effective filter snapshot;
- resolved query-policy provenance and the configuration resolution receipt;
- typed reported-finding snapshots; and
- author and creation time.

Review the saved output before treating the sample as complete.

Continue directly to [report preview and save controls](application-guide.md#reports)
if you need the individual screen actions. You do not need to read the reporting-rule
syntax reference to save a report.

## 8. Return to a table

Sorting, search, page, page size, and active analysis are kept in the URL where
the workflow supports it. Opening a detail page and going back should restore
the previous table state.

## Related guides

| Task | Guide |
| --- | --- |
| Full UI reference | [Application user guide](application-guide.md) |
| DNA findings | [DNA clinical review](dna-review.md) |
| RNA findings | [RNA clinical review](rna-review.md) |
| Coverage | [Coverage review](coverage-review.md) |
| Sample list | [Sample management](sample-management.md) |
| Reporting logic | [Clinical reporting rules](../reference/clinical-reporting-rules.md) |
