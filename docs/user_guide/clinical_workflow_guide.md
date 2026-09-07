# Clinical review workflow

This guide covers the normal path from finding a sample to saving its report.
For every screen, field, and action, use the
[complete user manual](complete_user_manual.md).

## 1. Find the sample

Open **Samples**, select the date range and assay scope, then search by sample
or case identifier. Select the sample name to open its workspace.

![Coyote3 sample list](../assets/screenshots/samples.png)

| Sample state | Meaning |
| --- | --- |
| Ready | All declared inputs were validated and stored. |
| Unreported | No saved report has completed the sample workflow. |
| Reported | At least one report has been saved. |
| Base configuration | No subpanel-specific ASPC was active, so the base ASPC was resolved. |

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

## 6. Add comments

Use sample comments for report-level interpretation and finding comments for a
specific event. Global annotations are shared across matching findings and
should be used only when the text is valid beyond one sample.

Hidden comments are inactive. Users with the required permission can reveal
them with **Show hidden comments** and restore them when appropriate.

## 7. Prepare the report

Open **Reports** and review the temporary preview. The report text uses the
latest visible sample comment; no comment produces an empty summary. Reported
finding rows are built from the current reportable findings and enabled report
sections.

Saving a report stores:

- the rendered report and artifacts;
- the resolved ASPC and reporting-rule identity;
- the effective filter snapshot;
- typed reported-finding snapshots; and
- author and creation time.

Review the saved output before treating the sample as complete.

## 8. Return to a table

Sorting, search, page, page size, and active analysis are kept in the URL where
the workflow supports it. Opening a detail page and going back should restore
the previous table state.

## Related guides

| Task | Guide |
| --- | --- |
| Full UI reference | [Complete user manual](complete_user_manual.md) |
| DNA findings | [DNA clinical review](clinical_review_dna.md) |
| RNA findings | [RNA clinical review](clinical_review_rna.md) |
| Coverage | [Coverage review](coverage_analytics.md) |
| Sample list | [Sample management](sample_management.md) |
| Reporting logic | [Clinical reporting rules](../product/clinical_reporting_rules.md) |
