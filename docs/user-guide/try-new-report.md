# Try new report

Open a DNA or RNA sample's **Reports** tab and select **Try new report**.
The trial renders the same clinical content used by the current report workflow
with an alternate layout. It does not change finding selection, interpretation,
report wording or reporting-rule resolution.

1. Review the **HTML preview** or **PDF preview**.
2. Use **Download HTML** or **Download PDF** to save a copy to your computer.
3. Use **Refresh** to render the current clinical state again.
4. Select **Current report** to return to the established report workflow.

Both previews and downloads use the same trial render. HTML includes its CSS;
it does not need a separate stylesheet. The PDF is generated from that HTML.
The modern layout uses Coyote3 branding, the configured center logo, and labeled
sample-detail fields. Both logos are embedded for offline HTML and PDF viewing.

The trial has no save action. It does not allocate a report number, create a
saved report or snapshot, or write report files to server storage. Rendering
uses temporary memory; leaving the trial releases its browser preview. Normal
access auditing remains active. Existing saved reports and the current report
workflow retain their established behavior.

The trial requires the same sample access and `report:preview` permission as
other report previews. It is a temporary review/download feature, not a persisted
clinical report.

The modern report uses compact patient/sample details. Enabled sections with no
reportable findings show a message instead of an empty table. Centers can configure
these messages in the [report presentation file](../configuration/report-presentation-file.md).

## Current report PDF preview

The established report also offers **HTML preview** and **PDF preview** in the
sample's Reports tab. Select **PDF preview** to generate and view its temporary
PDF in place. **Download PDF** saves a copy to your computer. Return to **HTML
preview** to review the document in the existing format. These preview actions do
not save a report; the existing **Save report** confirmation remains separate.
