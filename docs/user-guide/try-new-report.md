# Preview and save reports

Open a DNA or RNA sample's **Reports** tab. **Modern report** is the default;
**Legacy format** selects the older presentation. Both use the sample's applied
configuration, selected findings and reporting rules.

1. Review the **HTML preview** and **PDF preview**. **Refresh** reloads current inputs.
2. Use **Download HTML** or **Download PDF** for an unsaved local copy.
3. Select **Save report**, review the sample, format and included finding count,
   then confirm to create the issued report and its immutable snapshots.

Preview and download require `report:preview`; saving requires `report:create`.
All operations require sample access. Saving rejects a changed preview, including
a changed clinical assessment or a different selected format. Refresh and review
again before saving. Previously issued reports retain their original files.

## Modern presentation

The PDF repeats the Coyote3/center logo line and a compact patient-information
table on every page. The HTML shows this information once. The DNA or RNA template
version appears above the page number in the bottom-right PDF footer; it is independent
of the patient's report number. Pagination reads `Sida 1 av 2`. The footer also contains,
when configured, an accreditation
logo for an assay whose applied ASP snapshot has `accredited = true`.
See [center branding](../configuration/contact-file.md).

**Slutsats** begins on a new PDF page. Its saved comment supports sanitized
Markdown, including tables and lists. Summary tables use the available report width,
with plain borders, compact text and padding, and wrapping inside cells. Conclusions
containing tables omit the shaded outer box. Only the classification cell for a Tier 1 SNV
uses semibold text; the other summary cells use normal weight.
Detailed finding tables retain their compact layout and stay together when they
fit on a page; longer content can continue onto another page.

**Kliniskt relevanta biomarkörer** summarizes manually assigned HRD, MSI and TMB
assessments. Unassessed measurements show **Ej bedömd**. Raw scores appear in the
detailed biomarker tables after detailed SNVs. Set assessments in
[Biomarker analysis](biomarker-review.md) before reviewing the report.

Enabled sections without findings show configurable messages from the
[report presentation file](../configuration/report-presentation-file.md).
Fonts, styles and logos are embedded for offline viewing.

## Temporary API render

The existing `GET /api/v1/samples/{sample_id}/reports/{dna|rna}/try-new` operation
remains available for integrations. It returns one temporary modern HTML/PDF pair
without allocating a report number or saving files on the server. The normal UI
uses the preview and save endpoints, with an explicit modern or legacy selection.
