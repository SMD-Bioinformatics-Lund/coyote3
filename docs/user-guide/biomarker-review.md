# Review biomarker assessments

Open a DNA sample and select **Biomarker analysis**, alongside **Coverage** and
**Reports**. The tab appears when HRD, MSI or TMB is enabled in the sample's applied
ASPC. Each measured result shows its original score and any saved clinical assessment.
MSI single (`MSIS`) and paired (`MSIP`) measurements are assessed separately.

1. Select **Edit HRD/MSIS/MSIP/TMB assessment** for the result being reviewed.
2. Choose **High**, **Moderate**, **Low**, or **Not assessed** to clear the value.
3. Select **Save assessment**. The saved author and time appear below the value.
   **Cancel** discards the unsaved selection.

Editing requires `sample:edit:own` and sample access. Production samples also
require `annotation:publish`. A sample editing session prevents overlapping
editors; a revision check rejects stale saves. If another reviewer has changed the
value, reload and review the current result before saving again.

These are manual assessments. The application does not infer them from numerical
cutoffs, and choosing a value does not change the original measurement.
Absent measurements cannot be created through this editor. Old results without
an assessment remain **Not assessed**.

The modern report's **Kliniskt relevanta biomarkörer** table shows the saved value,
or **Ej bedömd** when unset. Detailed measured results follow detailed SNVs.
Refresh the report preview after reviewing biomarkers. Issued reports retain the
assessment captured when they were saved.

For database fields, API routes and ingestion safeguards, see
[Measurement analyses](../reference/measurement-analyses.md).
