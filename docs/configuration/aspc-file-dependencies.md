# ASPC analysis and reporting availability

The selected ASP's `expected_files` determine which
ASPC analyses can be enabled. The analysis-to-file mapping is maintained in
`api/config/center/clinical_vocabulary.toml`; ASP category and sequencing family
continue to restrict the available analyses.

For example, `vcf_files` enables SNV and `cnv` enables CNV. An ASP declaring neither
file cannot enable those analyses. Missing or empty file declarations enable no
analyses. Explicit empty selections remain empty when an ASP is saved. ASP imports
that omit `expected_files` entirely retain the existing category defaults.
These settings describe the ingestion contract, rather than checking the
filesystem or whether an individual sample has already been ingested.

`required_files` must be a subset of `expected_files`. Missing or unreadable required
files block ingestion. Missing expected files that are not required produce a warning
and allow the sample and its available data to be ingested. For example, expected
`transloc` without a readable file does not block ingestion unless it is also required.
The sample retains `missing_expected_files`; the samples table and overview show those
resources in red as **Not available**, rather than treating them as zero findings.
This records availability for the latest ingest input, including updates.

After ingestion commits, missing expected files produce a warning log, an audit event,
and an inbox notification for active users in `monitoring_group` (or `ERROR_EMAIL_GROUP`).
The monitor queues an email with the warning and compressed log attachment, retrying
delivery until SMTP accepts it. Existing samples acquire this recorded status when
ingested again; the overview also shows missing files from the current ASP contract.

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
