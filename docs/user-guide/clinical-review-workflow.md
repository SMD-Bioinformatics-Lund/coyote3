# Review a sample and save its report {#clinical-review-workflow}

Sign in with access to the sample and permission to review findings and save reports.
Check the sample context, review its findings, save your interpretation, then preview
and save the report.

## 1. Find the sample

Open **Samples**, choose the assay and date range, and search for the sample or case
identifier. Select the sample name to open it.

Check its ingest status. **Ready** means the required ingest completed; optional
evidence may still be missing. **Reported** means a report has been saved, not that
every possible analysis was performed. If the sample or an expected result is
missing, use [missing samples or results](sample-readiness-and-missing-results.md).

## 2. Check the overview

Confirm the sample and control identifiers, assay, diagnosis, pipeline, files and
applied assay configuration (**ASPC**). Stop if they do not match the submitted case.
Review any warning that a Base configuration was used instead of a diagnosis-specific one.

Available analyses depend on the sample and its configuration. A missing analysis
tab does not mean that the analysis ran and found nothing.

## 3. Choose a layout

**Classic** shows enabled finding sections together. **Modern** shows one analysis
at a time. The choice is saved to your profile and does not change the findings.

## 4. Apply filters

Open the analysis's filter controls, check the thresholds and selected gene lists,
then apply your changes. Filtering applies to the matching result set across pages.
SNV, CNV, fusion and translocation gene-list selections are independent.

For specific controls, see [DNA review](dna-review.md), [RNA review](rna-review.md)
or [coverage](coverage-review.md). [Gene scope](gene-lists-and-assay-context.md)
explains panel fallback and empty selections.

## 5. Review and classify findings

Open each relevant finding and inspect its evidence, transcripts, existing
classifications and comments. Choose actions appropriate to the finding:

| Action | Meaning |
| --- | --- |
| Assign a tier | Record a classification for the finding's identity and scope. |
| False positive | Mark a technical or calling artefact. |
| Irrelevant | Mark a finding outside the current question. |
| Interesting | Mark it for attention; this alone does not select it for a report. |
| Blacklist | Apply a shared exclusion through the permitted blacklist action. |

Check the scope before saving a shared classification. Bulk actions require row
selection and confirmation. Available actions depend on your permissions.

### How a tier is matched

A tier must match the finding identity and the sample's group, assay, diagnosis
and annotation namespace. A classification from another scope is context, not an
automatic assignment. RNA fusion matching uses the selected caller's finding identity.

Deactivation preserves annotation history. Inactive annotations do not automatically
tier new samples, but recorded assignments and report links can retain an earlier
classification. See [annotation history](actions-and-record-changes.md#immutable-annotations-and-sample-history).
Knowledgebase labels such as **CGC Tier 1** describe their source's evidence, not a Coyote tier.

### Search previous interpretations

Use [Tiered Variant Search](pages-and-table-columns.md#tiered-variant-search) to find
earlier classifications and linked samples or reports. For legacy records without
links, the displayed latest match does not establish which tier a sample originally used.

## 6. Add comments

Save the report interpretation as a **sample comment**. Use a **finding comment**
for a note about one event. Global annotations are shared across matching findings.
The latest visible sample comment supplies the report conclusion; with none, it is empty.

If you request suggested wording from reporting rules, review and save it as a comment.
Generating a suggestion does not save it. Missing published rules prevent that
suggestion, but do not by themselves prevent report preview or saving.

## 7. Prepare the report

1. Open **Reports** inside the sample.
2. Review **HTML preview** and **PDF preview**, including identifiers, findings,
   biomarker assessments and conclusion text. **Refresh** regenerates the preview.
3. Select **Save report**. Check the sample and included finding count, then select
   **Confirm save**. If inputs changed after previewing, refresh and review again.
4. Open the saved report and check its contents and file availability.

Previewing or downloading a preview does not save a report. The global **Reports**
page lists saved reports. See [preview and save controls](report-preview-and-save.md)
for permissions and [saved evidence](../reference/report-snapshots.md) for storage details.

## 8. Return to a table

Use browser Back to return to the previous table. Supported analysis tables keep
their search, sorting and pagination in the URL.
