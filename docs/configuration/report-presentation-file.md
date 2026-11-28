# Report presentation file

The optional center-owned `report_presentation.toml` supplies plain text for modern
report sections that contain no reportable findings. It does not change finding
selection, classification, reporting rules, or ASPC revisions. Previously issued
reports retain their saved layout and wording.

Bundled clinical wording uses `variant` / `varianter`. A center-owned file overrides
the defaults, so update its SNV messages explicitly when adopting this terminology.
Published reporting rules require a new reviewed version to change their authored
text. Existing report snapshots are not rewritten.

Place the file beside `contact.toml` in the center directory selected by
`COYOTE4_CENTER_CONFIG_HOST_DIR`. Host-run commands inherit this directory; Compose
mounts it at `/app/center-config`. An explicit `COYOTE4_CENTER_CONFIG_DIR` overrides
the process location. A complete example is supplied in
`api/src/coyote_api/config/examples/center/report_presentation.toml`.

```toml
[empty_results]
SNV = "Inga detekterade mutationer"
CNV = "Inga detekterade genspecifika kopietalsförändringar."
FUSION = "Inga detekterade fusioner"
```

## Supported keys and defaults

All keys are optional and case-sensitive. Missing files and omitted keys retain
the defaults below. Values must be nonblank strings of at most 1,000 characters;
surrounding whitespace is removed. Unknown keys and invalid values fail validation.
HTML is escaped and is displayed as text.

| Key under `empty_results` | Section | Default |
| --- | --- | --- |
| `SNV` | DNA SNVs and small INDELs | `Inga detekterade mutationer` |
| `GERMLINE_SNV` | Separate germline SNV section | `Inga detekterade germline-varianter` |
| `CNV` | Copy-number findings | `Inga detekterade genspecifika kopietalsförändringar.` |
| `TRANSLOCATION` | DNA fusions/translocations | `Inga detekterade fusioner` |
| `FUSION` | RNA fusions | `Inga detekterade fusioner` |
| `HRD` | HRD results | `Inga rapporterbara biomarkörresultat` |
| `MSI` | MSI results | `Inga rapporterbara biomarkörresultat` |
| `TMB` | TMB results | `Inga rapporterbara biomarkörresultat` |
| `BIOMARKER` | Other biomarker results | `Inga rapporterbara biomarkörresultat` |
| `PGX` | Pharmacogenomic results | `Inga rapporterbara farmakogenomiska resultat` |

## Rendering and deployment

### Report layout

Reports use the `coyote3` preset supplied by `smd-reports` 0.5.3. The package
owns embedded fonts, paper geometry and HTML/PDF styles. Shared result tables,
numbered gene-list captions and bordered classification reference tables match
the production report format. The author caption is "Rapport genererad av".
The conclusion heading is "Slutsats", followed by the evaluated clinical question
when supplied. Headings inside its narrative render as body-sized bold paragraphs
with one line break before the following text. The existing scope label and
reviewed narrative remain present.
The title combines the ASPC `reporting.report_header`, clinical-rule
`report_header_suffix`, and sample name.

SNV summaries contain gene, mutation, variant frequency and clinical significance.
Tier I significance cells use semibold text. CNV summaries contain genes, size,
type and copy number, using the production report's rounding expression. DNA fusion
summaries contain gene pairs and HGVS protein notation; RNA summaries contain
fusion names and classification. Detailed cards retain the additional version-four
classification, chromosome, exon, intron and supporting-read evidence.

Detailed tables include CNVs and DNA translocations, with stored paired/split
read evidence where available. DNA translocation sample, paired-read and split-read
values occupy separate bordered label/value cells. RNA details retain caller read support.
SNV summaries use one-letter protein notation. Detail tables retain the
`Tier I`–`Tier IV` labels and all recorded protein changes. Transcript labels include
the first exon or intron rank, while separate version-four rank cells retain all ranks.
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

Local Coyote Core callers can supply a validated
`coyote.application.reporting.presentation.ReportPresentation` through the report
renderer’s `presentation` argument. Coyote Core does not read center directories.

## ASPC summary order

Analysis order belongs to each ASPC's **Reporting → Summary order**, independently
of the center-owned empty-result wording. Two ordered lists can be configured:

```json
{
  "reporting": {
    "summary_text_order": ["CNV", "TRANSLOCATION", "SNV"],
    "summary_table_order": ["SNV", "CNV", "TRANSLOCATION", "TMB", "MSI", "HRD"]
  }
}
```

In **Summary order**, check the analyses to prioritize for the text or table.
Use the up and down arrows to change their order. Clear all checkboxes in either
group to use its default order. DNA fusions use `TRANSLOCATION` and RNA fusions use `FUSION`.
Duplicate, unknown and wrong-modality names are rejected. An order does not enable
an analysis or select additional findings. Names for currently disabled analyses
have no effect until the analysis is enabled.

Both fields default to empty lists. Empty text order retains the published rule
section order. Empty table order retains the renderer's existing order: SNVs
(including enabled germline findings), CNVs, DNA translocations or RNA fusions,
biomarkers, then PGx. A partial list puts listed analyses first; all other analyses
retain their relative order afterward. RNA-only configurations retain their
existing fusion, biomarker and PGx ordering unless explicitly configured.

Text order applies after rule matching to generated analysis-tagged sections.
Introduction, conclusion, metadata, method description and any other untagged
sections stay in their original positions. A section shared by several analyses
moves as one group using its earliest configured analysis; its authored sentences
remain together and unchanged. Already saved or edited sample comments are never
reordered automatically. Generate and review a new suggestion to adopt text order.

Table order changes result summaries and enabled empty-result messages, leaving
detailed finding cards, reference tables and gene lists in their existing order.
Somatic and germline SNV tables remain grouped. The combined biomarker table moves
as one unit using its earliest contained analysis; its rows follow the configured
priority while biomarker detail cards keep their original order.

Save these settings through normal ASPC review/versioning. Both values participate
in report preview fingerprints, so changing either invalidates an older preview
before artifact creation. Already issued report files remain unchanged.
