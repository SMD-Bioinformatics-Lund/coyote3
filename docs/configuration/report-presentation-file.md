# Report presentation file

The optional center-owned `report_presentation.toml` supplies plain text for modern
report sections that contain no reportable findings. It does not change finding
selection, classification, reporting rules, or ASPC revisions. Legacy reports keep
their existing layout and wording.

Place the file beside `contact.toml` in `COYOTE3_CENTER_CONFIG_DIR`. A complete
example is supplied in `config/examples/center/report_presentation.toml`.

```toml
[empty_results]
SNV = "Inga detekterade mutationer"
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
| `SNV` | DNA SNVs and small INDELs | `Inga detekterade mutationer` |
| `GERMLINE_SNV` | Separate germline SNV section | `Inga detekterade germline-mutationer` |
| `CNV` | Copy-number findings | `Inga detekterade kopietalsförändringar.` |
| `TRANSLOCATION` | DNA fusions/translocations | `Inga detekterade fusioner` |
| `FUSION` | RNA fusions | `Inga detekterade fusioner` |
| `HRD` | HRD results | `Inga rapporterbara biomarkörresultat` |
| `MSI` | MSI results | `Inga rapporterbara biomarkörresultat` |
| `TMB` | TMB results | `Inga rapporterbara biomarkörresultat` |
| `BIOMARKER` | Other biomarker results | `Inga rapporterbara biomarkörresultat` |
| `PGX` | Pharmacogenomic results | `Inga rapporterbara farmakogenomiska resultat` |

## Rendering and deployment

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
