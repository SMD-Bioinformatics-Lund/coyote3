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
| `modern/report.html` | Modern inheritance and overrides over the same clinical body. |
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
using it. Arbitrary filenames and paths are not accepted. Without a profile, the
established modality-specific layout remains the default. The temporary
**Try new report** operation selects modern presentation without changing the
sample configuration or saving report records/files.

CSS is embedded in rendered HTML; no linked stylesheet or network fetch is needed.
PDF rendering consumes the same HTML. The old report paths, clinical content,
styling and temporary-download behavior remain unchanged by template extraction.

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

## Modern PDF pagination

The modern stylesheet defines A4 paper, 18 mm top, 15 mm side and 20 mm bottom
margins, plus page counters. Fixed table layouts and wrapping keep long identifiers
within the printable width. Section headings stay with the following content.
Long finding annotations flow across pages rather than remaining in an oversized,
non-breaking table row. CNV profile images retain their aspect ratio and fit within
the page without the legacy rotation or fixed-width padding.

The report can contain as many pages as its clinical content requires; text is not
truncated or scaled down to force a single page. Pagination tests render DNA/RNA,
long annotations and identifiers, and portrait/landscape CNV images with WeasyPrint.
They check A4 dimensions, text and image bounds, and retention of the final annotation.
Review a real PDF after changing print styles, including multi-page text and images.
