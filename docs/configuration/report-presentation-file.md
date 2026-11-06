# Report presentation file

The optional center-owned `report_presentation.toml` supplies plain text for modern
report sections that contain no reportable findings. It does not change finding
selection, classification, reporting rules, or ASPC revisions. Legacy reports keep
their existing layout and wording.

Bundled clinical wording uses `variant` / `varianter`. A center-owned file overrides
the defaults, so update its SNV messages explicitly when adopting this terminology.
Published reporting rules require a new reviewed version to change their authored
text. Existing report snapshots are not rewritten.

Place the file beside `contact.toml` in the center directory selected by
`COYOTE3_CENTER_CONFIG_HOST_DIR`. Host-run commands inherit this directory; Compose
mounts it at `/app/center-config`. An explicit `COYOTE3_CENTER_CONFIG_DIR` overrides
the process location. A complete example is supplied in
`config/examples/center/report_presentation.toml`.

```toml
[empty_results]
SNV = "Inga detekterade varianter"
CNV = "Inga detekterade kopietalsförändringar."
FUSION = "Inga detekterade fusioner"
```

## Supported keys and defaults

All keys are optional and case-sensitive. Missing files and omitted keys retain
the defaults below. Values must be nonblank strings of at most 1,000 characters;
surrounding whitespace is removed. Unknown keys and invalid values fail validation.
HTML is escaped and is displayed as text.

| Key under `empty_results` | Section | Default |
| --- | --- | --- |
| `SNV` | DNA SNVs and small INDELs | `Inga detekterade varianter` |
| `GERMLINE_SNV` | Separate germline SNV section | `Inga detekterade germline-varianter` |
| `CNV` | Copy-number findings | `Inga detekterade kopietalsförändringar.` |
| `TRANSLOCATION` | DNA fusions/translocations | `Inga detekterade fusioner` |
| `FUSION` | RNA fusions | `Inga detekterade fusioner` |
| `HRD` | HRD results | `Inga rapporterbara biomarkörresultat` |
| `MSI` | MSI results | `Inga rapporterbara biomarkörresultat` |
| `TMB` | TMB results | `Inga rapporterbara biomarkörresultat` |
| `BIOMARKER` | Other biomarker results | `Inga rapporterbara biomarkörresultat` |
| `PGX` | Pharmacogenomic results | `Inga rapporterbara farmakogenomiska resultat` |

## Rendering and deployment

### Modern report layout

DNA and RNA presentation version 1.0.2 uses Source Sans 3 with 9.25 pt body text,
8.5 pt screen tables and 8.25 pt compact print values, with 7.5 pt printed labels.
Summary cells use 4 px × 10 px padding on screen and 2 px × 8 px in print;
detailed cells use 2 px × 4 px. Summary tables have thin gray horizontal rules
without vertical column borders. Summary body rows are uniformly white beneath
the pale purple header. Detail and patient-information tables retain complete
grids, including the detail heading row, without a colored left accent.
Table headers and the patient-information heading are black on pale purple tints;
section headings and branding retain purple/orange accents. Body text is black.
Heading separators are omitted.
The conclusion starts on its own page, with a page break after its text. Its
subheading uses the registered diagnosis display name, or the captured panel
display name for base/NA diagnoses, followed by paired/unpaired analysis context.
The document title remains the ASPC `reporting.report_header`, followed by any
clinical-rule `report_header_suffix`.

SNV summaries contain gene, chromosome, exon, HGVS, VAF, tier and clinical
significance description. CNV summaries contain genes, chromosome, type with
copy-number estimate, size, tier and clinical significance. DNA/RNA fusion
summaries use `Gene1::Gene2`, breakpoint locus, exon when recorded, tier and
clinical significance. Cytogenetic arm notation is not inferred from breakend
coordinates. RNA exon annotations are unavailable in the current caller contract
and display `-`.

Detailed tables include CNVs and DNA translocations, with stored paired/split
read evidence where available. DNA translocation sample, paired-read and split-read
values occupy separate bordered label/value cells. RNA details retain caller read support.
SNV summaries use one-letter protein notation. All finding summaries use compact
Roman tier numerals; detail tables retain the `Tier I`–`Tier IV` labels and
three-letter SNV protein notation. SNV exon and intron ranks have their own labelled
cells, separate from the transcript identifier.
Missing classifications display exactly `-`. Generated classification separators
and genomic ranges use plain hyphens.
DNA SNV summary rows are ordered by ascending tier, then descending numeric VAF, with
missing VAF last within its tier. Table headers and field labels use pale purple
tints; orange accents remain restrained, with black clinical values.
MSI uses `MSIS` for unpaired samples and `MSIP` for paired samples; biomarker
summary tables omit sample names.

CNV and translocation tiering is enabled by default. Existing explicit application
control overrides remain effective. Structural report inclusion accepts an allowed,
usable tier or an explicit report flag, then applies existing review exclusions
and gene-list restrictions. Issued HTML/PDF files and their snapshots are unchanged.
Configurations pinned to a previous modern template hash require a new reviewed
ASPC revision capturing the installed template before using the new presentation.

An enabled empty section displays its configured message under the section
heading, without an empty table. Sections with findings retain their tables;
disabled sections do not gain a message. An RNA report emits the empty-fusion
message once, without a second empty details section.

The API reads this file for each modern render. Changes in the mounted directory
apply to subsequent previews and downloads without restarting services or editing
ASPC. Already issued files are unchanged. Review institutional wording before use;
an empty reportable set does not necessarily mean that the assay detected nothing.

For saved modern templates, application operations capture the wording in the
preview context and fingerprint. A wording change requires a new preview before
save; rendering uses the captured values for that operation.

For immutable configuration releases, use
[center configuration preparation](../deployment/center-configuration.md).
`prepare_center_config.py` includes this file when present, validates it, and adds
its checksum to the release manifest. Deploy a new reviewed directory through the
normal configuration-release procedure.

Local SDK callers can supply a validated
`coyote3.application.reporting.presentation.ReportPresentation` through the report
renderer’s `presentation` argument. The SDK does not read center directories.
