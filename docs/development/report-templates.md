# Report templates and rendering

Report HTML and CSS live in `src/coyote3/templates/reporting/` and are included
in the Coyote3 wheel. Python does not contain report document or stylesheet strings.
Jinja's package loader resolves files independently of the working directory.

| Location | Responsibility |
| --- | --- |
| `base.html` | Established document structure and shared stylesheet embedding. |
| `assets/report.css` | Existing report styles, included inside the HTML style element. |
| `assets/modern.css` | Modern layout overrides, embedded in the same document. |
| `legacy/report.html` | Legacy inheritance entry point. |
| `legacy/dna.html`, `legacy/rna.html` | Modality-specific body composition. |
| `components/dna/`, `components/rna/` | Sample information, finding tables and classification wording; distinct markup remains distinct. |
| `modern/components/dna/`, `modern/components/rna/` | Modern sample-information overrides; the legacy components retain their original markup. |
| `components/modern/` | Branded report header and labeled sample-details layout. |
| `modern/report.html` | Modern inheritance and overrides over the same clinical body. |
| `modern/manifest.toml` | Version of the shared modern DNA/RNA template bundle. |
| `components/header.html`, `components/footer.html` | Modern head metadata/styles and temporary-preview notice. |

`application/reporting/report_context.py` prepares display defaults from already
evaluated clinical inputs. `report_service.py` registers layouts and verifies their
content identity. `report_renderer.py` configures Jinja filters, applies escaping
and sanitization, renders HTML, and renders PDF bytes with the existing restricted
resource fetcher. Clinical selection, reporting rules and variant classification
remain in the existing application/domain workflows. Templates display their
results rather than evaluating clinical policies.

## Template selection

The existing governed template configuration profiles accept:

| Template identifier | Analyte | Layout |
| --- | --- | --- |
| `dna_report.html` | DNA | Legacy |
| `report_fusion.html` | RNA | Legacy |
| `modern/dna_report.html` | DNA | Modern |
| `modern/report_fusion.html` | RNA | Modern |

Published profile compilation captures `template_name` and `content_hash` in
`template_release`. Rendering verifies the installed content and analyte before
using it. Arbitrary filenames and paths are not accepted. HTTP previews default to
`format=modern`; `format=legacy` selects the older presentation. Save requests use
the matching `report_format`. The actual layout and content hash participate in
the preview fingerprint and saved resolution receipt, alongside the configured
template identity. Selecting another format requires a new preview.

Local SDK callers can select `layout="modern"` or `layout="legacy"` on preview,
PDF preview and save. Omitting `layout` preserves the configured presentation for
existing SDK callers. The temporary `try-new` API remains available without saving
report records or files.

CSS is embedded in rendered HTML; no linked stylesheet or network fetch is needed.
PDF rendering consumes the same HTML. Legacy presentation and finding selection
retain their existing behavior.

## Edit and verify

Edit templates or CSS directly and reload the consuming process. Include files
are registered package resources, not center-supplied executable templates.
Do not place clinical policy decisions, database lookups or unescaped authored
content in templates. Keep existing sanitization filters on authored report text.

Legacy content hashes expand component includes and ignore empty inheritance
extension points. This preserves approved digests after extraction while making
HTML/CSS content edits change the digest. Modern digests additionally cover the
modern overrides. An intentional template change must follow the existing profile
review/publication process. Issued report snapshots are not regenerated.

Synthetic golden tests compare approved HTML for DNA/RNA in both layouts,
verify unchanged legacy hashes, and render real PDFs. Further tests cover
clinical text parity, sanitization, profile selection, authorization and temporary
report nonpersistence. The report directory is excluded from automatic HTML
reformatting because whitespace participates in approved source identities.

## Template bundle releases

DNA and RNA template versions are two of Coyote3's five release version numbers.
For the application/UI, core SDK and Python client SDK versions, see
[Version identities](../sdk/compatibility.md#version-identities).

Manage the modern reports' independent DNA and RNA versions in
`src/coyote3/templates/reporting/modern/manifest.toml`, alongside its template files:

```toml
[dna]
version = "1.0.0"

[rna]
version = "1.0.0"
```

The manifest is packaged with the HTML, CSS and fonts. The renderer selects the
version for the report's analyte. The loader requires valid `MAJOR.MINOR.PATCH`
versions for both analytes and rejects missing or invalid metadata instead of
supplying a default.

For a template release:

1. Update the layout assets and increment the affected analyte's version. Changes
   to shared HTML, CSS or fonts require both versions to advance. Use a patch
   release for presentation fixes, a minor release for compatible presentation
   additions, and a major release for incompatible template changes.
2. Run the reporting regressions and inspect DNA/RNA HTML and PDFs, including
   multi-page content. Clinical wording and finding selection still follow their
   existing governed workflows.
3. Build the package with the manifest and assets together. Review and publish
   affected template profiles through the existing approval process before use.

The PDF footer displays the selected analyte's manifest version above the page number. Its content hash
includes that version; changing only the DNA version does not change the RNA hash,
and vice versa. Changing shared assets still
changes the hash even when the version was not incremented. Existing issued
reports retain their original artifacts and do not acquire a later template version.

## Modern PDF pagination

Modern reports use white paper, neutral text and table fills, purple section headings,
and a thin purple-to-orange masthead rule. Patient-information and finding-table
headings use a near-white fill with darker text. The masthead contains Coyote3 and
center logos, with a black Coyote3 wordmark and no product subtitle.
A separate document heading displays the configured report title and sample name.
Patient and sample details appear in a compact table with paired labels and values,
and full-width question and report-identifier fields. Findings use consistent tables;
the conclusion has a distinct bordered panel unless it contains a table. Conclusion tables
use the full content width, compact cells and plain borders, with long text wrapping.
Only the classification cell of a Tier 1 SNV summary row is semibold.
Supporting descriptions and classification references use
the same typography, with smaller text than the main results.

The modern layout embeds Source Sans 3 in regular, semibold and italic weights
as WOFF2 data URLs in `assets/fonts.css`. Its SIL Open Font License is packaged alongside
the stylesheet in `assets/SourceSans3-LICENSE.md`. Browser and PDF rendering use the
same font without network requests or installed system fonts. The fonts come from the
[Source Sans project](https://github.com/adobe-fonts/source-sans)
and the static regular, semibold and italic faces are packaged as WOFF2 files.
The same selected clinical findings remain available in both formats. Modern
reports summarize manual biomarker assessments and move their numeric details
after the detailed SNVs. Presentation overrides are
loaded only for the modern layout, and their sources participate in its content hash.

The modern stylesheet defines A4 paper, a 65 mm top region for the repeating
logo line and patient table, 16 mm side and 22 mm bottom margins. When an accredited
applied assay has a configured accreditation logo, the bottom margin increases to
38 mm. The footer places the logo on the left in a 28 mm high image area, capped
at 32 mm wide with its proportions preserved; the template version and Swedish
`Sida X av Y` counter align on the right. HTML uses 14 mm top padding and shows
the logo line and patient table once.
Both formats use the same 210 mm paper width, giving both renderers
178 mm of content width. The preview scrolls horizontally on narrower screens
instead of changing table columns, font sizes or label placement. Detailed finding
tables and CNV images use the same layout rules in screen and print media.
PDF pagination adds page breaks, continuation references and footers; HTML remains
a continuous document on the same paper width.
Patient and specimen information uses two label/value pairs per HTML row and
three per PDF row. PDF rows use smaller padding and text, with full-width cells for long values.
Clinical questions and report identifiers use full-width value cells.
Result tables use 4 px vertical cell padding, with smaller gaps between sections.
Modern summary tables wrap their shared clinical header row in `thead` and finding
rows in `tbody`, so column headings repeat when a table continues onto another PDF page.
Detailed finding tables use single neutral rules, with full-height label backgrounds
for classification and annotation rows.
The conclusion uses a pale yellow background and an amber rule. The modern layout
renders its saved comment through the existing sanitized Markdown formatter. Tables
have bordered cells, left-aligned headings and light header fills. Lists, headings,
quotes and code retain their structure with compact spacing in both HTML and PDF.
These styles are scoped to the conclusion and do not change clinical result tables.
The PDF starts **Slutsats** on a new page. HTML flows continuously; legacy forced
page breaks after the conclusion and CNV profile are suppressed. Fixed table layouts and wrapping keep long identifiers
within the printable width. Section headings stay with the following content.
Detail tables that fit on a page stay together; a table moves to the next page
when there is insufficient space. Longer finding annotations can still flow across
pages without text loss. The bottom-right footer identifies the analyte and template version,
for example `DNA template v1.0.0`. The version comes from the
bundle's `modern/manifest.toml` and is independent of the patient report number
and application release. Below it, Swedish pagination reads `Sida 1 av 2`.
See [Template bundle releases](#template-bundle-releases)
for version updates and approval.
CNV profile images retain their aspect ratio and fit within
the page without the legacy rotation or fixed-width padding.

The report can contain as many pages as its clinical content requires; text is not
truncated or scaled down to force a single page. Pagination tests render DNA/RNA,
long annotations and identifiers, and portrait/landscape CNV images with WeasyPrint.
They check A4 dimensions, screen/PDF geometry, text and image bounds, repeated
continuation headings, and retention of every summary finding and the final annotation.
Review a real PDF after changing print styles, including multi-page text and images.

## Browser PDF previews

Modern and legacy reports use `ReportPdfFrame` for PDF previews. Binary
requests use the shared API client, including session handling and structured
errors. The client checks the PDF header and final end-of-file marker before
opening the viewer, and supplies the PDF MIME type when the response omits it.
These checks detect error pages and truncated responses; they do not replace PDF parsing.

The viewer owns its object URL and releases it on replacement or unmount. Reloading
the viewer creates a fresh URL without regenerating or saving the report. A failed
or stalled iframe offers recovery controls; browsers without embedded PDF support
show open/download controls directly. Open PDF and Download this PDF use the same
prepared bytes as the embedded preview. A browser load event cannot prove that its
native PDF plugin painted every page, so those controls remain available after load.

## Center branding

The HTTP host resolves branding; the application SDK accepts embedded image URLs
and never reads center directories. In the center-owned `contact.toml`:

```toml
[organization]
report_logo = "region-skane"
```

`region-skane` selects the bundled mark for the affiliated center and is the default
when this key is absent. Other centers can set a relative SVG, PNG or JPEG path
inside their mounted center configuration directory, or `""` to omit the mark.
The selected file must be at most one megabyte. Paths escaping that directory,
SVG scripts, nested images and external references are rejected.
The performing organization name comes from the existing organization setting.
Optional `organization.address` and `organization.phone` in `contact.toml` appear
below the center name; the telephone has an embedded icon. Omitted or blank values
produce no contact row. The support escalation number is not used as a report contact.
Apply center configuration through the normal deployment/restart procedure.

Logos are embedded in the HTML for offline viewing and PDF generation. Report
paper uses fixed ink colors independently of the web UI's dark/light theme.
Existing issued HTML/PDF files retain their embedded branding. Published modern
template profiles require review and publication of the new content hash after
template or stylesheet changes; the legacy template identities are unchanged.

Empty modern finding sections display plain text rather than empty tables.
The host supplies validated [per-analysis wording](../configuration/report-presentation-file.md)
through `ReportPresentation`; local SDK callers can supply the same model explicitly.
Trusted SDK hosts bind `ReportingServices.presentation` to their settings provider;
application operations include those values in saved modern-report preview fingerprints.
Presentation blocks reuse the existing tables for populated sections. Legacy
output and its approved digests remain unchanged.
