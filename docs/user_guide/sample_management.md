# Sample management

The Samples page is the clinical worklist. It shows every sample visible to the
current user after role, assay, group, environment, date, and search filters are
applied.

![Coyote3 sample list](../assets/screenshots/samples.png)

## Find samples

| Control | Behavior |
| --- | --- |
| DNA/RNA menu | Restricts the worklist by omics layer, sequencing family, or assay group. |
| Environment scope | Shows production only or all environments allowed for the user. |
| Date added | Uses a preset or custom date range. |
| Search | Searches supported sample and case identifiers on submission. |
| Rows per page | Sets the page size; remaining matching samples stay available through pagination. |
| Live samples | Shows samples still in the active review workflow. |
| Reported samples | Shows samples with saved reports and includes the latest report date. |

The worklist has **Classic** and **Modern** layouts. Classic shows both worklist
sections on one page. Modern shows one section at a time. The choice is saved in
the user profile.

## Table columns

| Column | Meaning |
| --- | --- |
| Sample | Canonical sample name and link to its workspace. |
| Case ID | Case identifier supplied by the ingest manifest. |
| Case clarity | Case identifier from the upstream LIMS when provided. |
| Control | Control sample identifier for paired analyses. |
| Control clarity | Control LIMS identifier when provided. |
| Environment | Production, validation, testing, or development context. |
| ASP | Assay panel used to resolve configuration. |
| Subpanel | Requested in-silico subpanel or `base`. |
| Pipeline | Pipeline name and version when supplied. |
| Analysis | Current sample analysis state. |
| Report | Reported or unreported state. |
| Counts | Loaded analysis resources and finding counts. Green badges indicate loaded data; failed or partial resources use an error state. |
| Added | Time the sample was added, shown in local time. |
| Latest report | Most recent saved report time on the reported worklist. |
| Actions | Opens the sample workspace. |

Count badges are not sorted as one value because a cell can contain several
analysis types.

## Open a sample

Select the sample name or action button. The workspace displays only analyses
enabled by the sample omics layer and resolved ASPC.

| Sample type | Possible pages |
| --- | --- |
| DNA | Overview, findings or separate SNV/CNV/translocation tabs, coverage, biomarkers, PGx when supported, and reports. |
| RNA | Overview, fusions, expression/classification for enabled WTS workflows, QC, PGx when supported, and reports. |

A missing analysis page means it is not enabled for that sample. It does not
mean that the analysis ran and returned no findings.

## Sorting and navigation state

Server-backed tables sort the complete filtered result before pagination.
Multiple columns may be added to the sort order. Supported table state is kept
in the URL, so opening a finding and returning restores the active analysis,
filters, sorting, search, and page.

## Export

**Export to CSV** includes the table's data columns and omits selection and
action controls. Sample export includes identifiers, assay context, pipeline
metadata, resource states, biomarker values, counts, and report dates where
available.

## Related guides

| Task | Guide |
| --- | --- |
| Full workflow | [Complete user manual](complete_user_manual.md) |
| DNA review | [DNA clinical review](clinical_review_dna.md) |
| RNA review | [RNA clinical review](clinical_review_rna.md) |
| Clinical workflow | [Clinical review workflow](clinical_workflow_guide.md) |
