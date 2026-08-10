# Sample Management And Navigation

The Sample List (accessible via the main navigation or assay-specific routes) is the central workspace for triaging incoming clinical cases. It is located at the `/samples/` route.

![Coyote3 sample list](../assets/screenshots/samples.png)

## Interface Overview

The sample management interface is designed to help you quickly locate and prioritize cases for review.

### 1. Global Filters and Search

At the top of the page, you can narrow down the sample list using:

*   **Profile Scope**: Toggle between "Production" (live clinical cases) and "All Profiles" (which includes validation and development samples).
*   **Search Bar**: Search by Sample ID, Case ID, or Patient identifiers. The search is real-time and filters both "Live" and "Reported" tables.

### 2. Live Samples Table

This table lists all samples that currently require interpretation.

*   **Status Indicators**: Compact badges show analysis state, report state, and available result counts.
*   **Case Details**: View associated Case IDs, Control IDs, and the specific Assay/Panel used for the test.
*   **Quick Actions**: The action button opens the sample workspace. Additional mutation actions are shown only where the user has permission.
*   **Sorting**: Most single-value columns can be sorted. Multi-value count columns are displayed compactly and are not intended as a single sortable value.

### 3. Reported Samples Table

Once a report is finalized, the sample moves to this section. It serves as an archive of completed work.

*   **Report History**: Click on the numbered badges (e.g., `1`, `2`) to download or view specific versions of the clinical report.
*   **Audit Trail**: The "Last Report" column shows exactly when the diagnostic event was closed.

## Data Integration Links

For each sample, Coyote3 provides direct links to the raw data and quality metrics:

*   **BAM/BAI**: Direct links to download visualization files for external IGV review.
*   **QC Metrics**: A percentage or read-count badge that link to a detailed Quality Control report, showing mapping stats and coverage per-base.

## Entering Interpretation

Clicking on a **Sample ID** opens the specialized interpretation environment for that data type:

*   **DNA Samples**: Opens the SNV/CNV interpretation view.
*   **RNA Samples**: Opens the Fusion and Expression analysis view.

## Table Layout

| Column | Description |
| --- | --- |
| Sample | Canonical sample name and link to the sample workspace. |
| Case ID / Control | Case and control identifiers. Control columns are populated only for paired samples. |
| Profile | Profile badge such as production, validation, test, or development. |
| Assay / Subpanel | ASP and ASPC/subpanel context used for sample review. |
| Analysis | Current ingest/analysis state. |
| Report | Reported or unreported state. |
| Counts | Short-form count badges for enabled analysis domains. |
| Added | Human relative date with detailed timestamp available from the browser tooltip. |
