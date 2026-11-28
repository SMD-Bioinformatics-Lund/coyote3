# Install assay resources

Use the individual pages in **Admin**. Saving an assay (ASP), assay configuration (ASPC) or gene list (ISGL) makes its first revision active immediately. Each list page accepts multiple JSON or YAML files through **Upload JSON / YAML**. Review the records and choose **Install records**. To change an existing resource, open it and choose **Edit**.

## Installation order

| Order | Admin page | What to install |
| --- | --- | --- |
| 1 | Assay groups | Ensure the assay's group exists and is active. |
| 2 | Diagnosis definitions | Register named diagnoses with their assay IDs. The built-in `base` scope needs no record. |
| 3 | Gene lists | Install lists with their genes, analysis types and assay or group associations. Diagnoses and lists can reference a planned assay ID. |
| 4 | Assays | Import the ASP definitions. An assay can exist before it has a configuration. |
| 5 | Assay configurations | Import each ASPC for its assay, diagnosis and environment. The assay and group must be active. A named diagnosis needs an active definition and association. Selected filter lists must be available to that assay for the required analysis. |
| 6 | Reporting Rule Sets | Import the desired rules as drafts. Test, review and publish them through the reporting-rule workflow. |

For a sample with a named diagnosis, intake uses the active matching ASPC or falls back to the active Base ASPC in the same environment. If neither exists, intake cannot proceed. A missing reporting-rule publication affects automatic report wording.

## Revisions and existing samples

Saving an edit creates a new document with the same business ID, a new database ID and the next version. The previous version becomes inactive and remains available under **Version history**. An assay edit refreshes its active configurations. A shared list edit refreshes the configurations of all affected assays, including group associations. These revisions and their audit receipts commit together.

New samples use the active configuration. An existing sample keeps its recorded configuration and gene lists. To move it, open **Sample settings** or the **Filters** sidebar, choose **Review configuration update**, inspect the preview, enter a reason and apply. The preview shows added or removed genes when the recorded membership differs. Saved reports keep their original evidence.

See [bulk installation](bulk-installation.md) for file limits and per-record results, and [reporting rule authoring](report-rule-authoring.md) for the publication steps.
