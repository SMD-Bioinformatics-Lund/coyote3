# Report templates and rendering

DNA and RNA reports use `smd-reports==0.5.3` exclusively. Coyote4 supplies evaluated
clinical content as JSON; the package owns HTML, styles, fonts, tables, detail
cards and pagination. There are no bundled Jinja report templates or layout fallbacks.

## Current rendering pipeline

1. DNA/RNA workflows resolve applied configuration, eligible findings, annotations
   and governed clinical rules.
2. `application/reporting/report_context.py` prepares presentation values.
3. `application/reporting/document/` builds the native document contract using
   the package's `coyote3` preset ID. This is an external renderer identifier;
   application branding is Coyote4. It preserves missing measurements, zero counts, selected
   fusion calls, notation and reviewed Swedish text. Gene lists use ordered matrix
   items and numbered captions; reference tables use the package's compact style.
4. `ReportLoader().loads(...)` validates the in-memory JSON document, then
   `ReportRenderer().render_html(...)` produces standalone HTML.
5. Coyote4 adds its browser content-security policy. Its restricted WeasyPrint
   renderer produces PDF from the same HTML. Saving retains the artifacts,
   finding snapshots and configuration/rule resolution receipt.

No CLI, subprocess, external resource fetch or temporary JSON file is needed.
Clinical decisions remain in application/domain workflows, outside presentation.

### Template selection

`ReportTemplate` defines the identifiers `dna` and `rna`. Each selects the
package-owned document for its analyte; identifiers are not file paths. Both use
the `coyote3` preset. Wrong-analyte identifiers and arbitrary paths are rejected.

Published configuration profiles capture `template_name` and `content_hash` in
`template_release`. Rendering verifies both against installed resources. A profile
approved against an earlier file-like identifier fails validation until its replacement
is reviewed and published through the existing governance workflow. It is never
silently upgraded or treated as already approved.

Before upgrading a development installation that used file-like identifiers,
create and review replacement template profiles with `template_name: dna` or
`template_name: rna` and the newly captured content hash, then publish the affected
configuration revisions. Existing issued artifacts remain readable. Old preview
fingerprints require a fresh preview and review.

Reports have one renderer. HTTP requests do not accept a format selector,
and Coyote Core calls do not accept a layout argument. Integrations can request matching
HTML/PDF content through `/preview/bundle` without persisting report artifacts.

Actual renderer identity, configuration, presentation values and clinical inputs
participate in the preview fingerprint. Save requires the reviewed fingerprint.
Previously issued HTML/PDF files are retrieved unchanged; they are not regenerated.

### Edit and verify

Change the JSON projection when a supported package feature needs different input.
Change shared document rendering in `smd-reports`, then update the pinned dependency.
Do not add application-owned templates, CSS overrides or clinical rules to the renderer.

Run report, API and client regressions, template-approval and saved-artifact checks,
then inspect synthetic DNA/RNA HTML/PDF output. Include long annotations, missing
values, gene order, embedded logos and multiple pages. Check the frontend preview,
confirmation and download flows after API changes.

### Template bundle releases

The installed package supplies DNA/RNA template versions through
`smd_reports/themes/versions.json`. Its package and template versions appear in
report metadata and the PDF footer, independently of the patient report number.
Coyote4 has no separate report-template manifest or fallback version.

The content hash covers installed package resources and Coyote4's input adapter.
Shared cell formatting belongs to `document/formatting.py`; section builders do
not import the renderer. Renderer imports are declared at module scope, and
configuration/receipt code imports identity and hashing directly from `report_service.py`.
Package upgrades and adapter changes require reviewed template configuration
revisions before clinical rollout. Issued artifacts retain their original versions.
See [Version identities](../core/compatibility.md#version-identities).

### PDF pagination

The package owns A4 geometry, embedded Source Sans 3 fonts, tables, repeating
patient metadata, continuation headers and page numbering. HTML is a continuous
preview; PDF adds pagination. Long finding content must remain visible across pages.
Coyote4 passes compact body-sized bold labels inside the conclusion without changing
reviewed words. Additional v4 CNV/translocation cards, germline, biomarker and PGx
content remain available through the package document contract.

## Browser PDF previews

`ReportPdfFrame` uses prepared PDF bytes from the shared API client. The client
checks the PDF header and end-of-file marker before opening the viewer. Object URLs
are released on replacement or unmount. Open/download controls remain available
when a browser cannot display the embedded PDF. Preview and download do not save.

## Center branding

The HTTP host loads logos from reviewed center configuration and embeds them as
data URLs. Coyote Core receives branding explicitly and does not read host directories.
`contact.toml` supplies organization name, department and address. The performing
laboratory metadata uses that same identity. Phone values are omitted from reports.

`organization.report_logo` selects the bundled Region Skåne mark, a relative SVG,
PNG or JPEG inside the center directory, or an empty value to omit the mark.
`organization.accreditation_logo` selects a center-owned image shown only when the
applied assay snapshot explicitly has `accredited = true`. Existing path, size,
SVG and embedded-resource validation remains enforced. External resources are blocked.

[Report presentation settings](../configuration/report-presentation-file.md) supply
validated empty-result wording. Application operations capture these values in
preview fingerprints and saved resolution receipts. Package rendering and clinical
configuration are reviewed separately.
