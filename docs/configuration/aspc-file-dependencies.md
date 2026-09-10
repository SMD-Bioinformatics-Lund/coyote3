# ASPC analysis and reporting availability

The selected ASP's `expected_files` and `required_files` together determine which
ASPC analyses can be enabled. The analysis-to-file mapping is maintained in
`api/config/center/clinical_vocabulary.toml`; ASP category and sequencing family
continue to restrict the available analyses.

For example, `vcf_files` enables SNV and `cnv` enables CNV. An ASP declaring neither
file cannot enable those analyses. Missing or empty file declarations enable no
analyses. Explicit empty selections remain empty when an ASP is saved. ASP imports
that omit `expected_files` entirely retain the existing category defaults.
These settings describe the ingestion contract, rather than checking the
filesystem or whether an individual sample has already been ingested.

Unavailable choices are disabled in the editor. Reporting sections can only be
selected from enabled ASPC analyses. Changing the selected ASP clears unavailable
analysis and reporting selections. The API rejects unavailable selections on both
create and update, including JSON imports.

ASP, ASPC, and ISGL IDs are editable when creating a record. Copying clears the
source ID so a new ID must be entered. Once created, IDs are read-only because
other records may reference them. Duplicate IDs continue to be rejected.
ASPC copies also require an unused ASP/subpanel/environment combination: only one
active configuration may serve each combination. Sample configuration lookup uses
that combination independently of the chosen ASPC ID.
