# Operational Dashboard

The dashboard summarizes the samples, findings, review workload, and clinical
configuration visible to the signed-in user. It uses aggregated API responses
instead of loading complete clinical collections into the browser.

![Coyote3 operational dashboard](../assets/screenshots/dashboard.png)

!!! info
    Dashboard counts respect the user's role, assay, and environment scope.
    Two users can therefore see different totals from the same deployment.

## Operational Snapshot

The first section answers three immediate questions:

| Card | Meaning |
| --- | --- |
| Analysis progress | Analysed samples compared with all samples in the visible scope, including the number awaiting review. |
| My visible samples | Samples available through the user's assigned roles, assays, and environments. |
| Finding inventory | Persisted findings across the visible samples, with the unique small-variant count shown as supporting context. |

## Review Workload and Recent Samples

**Review Workload** groups sample progress by assay and shows the distribution
of sample environments. Each assay row reports analysed, total, and pending
samples.

**My Recent Samples** lists the latest samples visible to the account. Select a
row to open the sample workspace. Each row includes the sample name, omics
layer, ingest state, ASP, subpanel, and relative ingest time when available.

## Sample Composition

The composition section summarizes the visible sample population by:

- ingest status;
- omics layer;
- sequencing scope;
- environment; and
- paired or unpaired state.

It also groups samples by observed pipeline name and version. Each pipeline row
shows its sample count and the proportion already analysed. A missing version is
shown explicitly as **Version not recorded**; it is not replaced with a version
from another sample or from application configuration.

These values describe workload composition. They do not replace sample-level
quality review.

## Variant Review

The variant review section provides persisted finding and curation totals:

- small variants, CNVs, fusions, and translocations;
- blacklisted and false-positive findings;
- Tier 1 or Tier 2 findings, Tier 4 findings, and VUS;
- findings saved in report snapshots;
- reported-tier distribution; and
- small-variant class distribution.

An unavailable tier chart means that the aggregate contains no reported tier
data. It is not rendered as a clinical zero unless the source aggregate
explicitly reports zero.

## Targeted-Panel Configuration

The panel sections include only active targeted-panel ASP and ASPC definitions;
WGS and WTS configurations are excluded.

### Panel Gene Coverage

The chart compares covered and germline gene assignments across active panels.
It summarizes panel design scope, not observed sample coverage.

### Panel Portfolio

The portfolio reports active panels, represented assay groups, accredited
panels, and covered or germline gene assignments.

### Panel Analysis Capability

For each analysis type, this chart compares:

- **Enabled:** active targeted-panel ASPCs that expose the analysis in
  `analysis_types`.
- **Reportable:** those configurations that also include the analysis in
  `reporting.report_sections`.

An enabled analysis does not have to be reportable. The difference represents
the configured review and reporting policy.

### Resource Capacity

The resource panel reports administrative inventory such as users, roles,
ASPs, ASPCs, and ISGLs when those values are available to the current user.

## Clinical Configuration

This section summarizes active gene-list and assay relationships, including
unique active genes, public and private ISGL counts, ad-hoc lists, and common
assay-to-ISGL associations. Use **Open catalog** for the complete public assay
and gene-list reference.

## Data Sources

| Dashboard value | Source | Meaning |
| --- | --- | --- |
| Sample workload and composition | `samples` aggregates | Ready, analysed, pending, profile, omics, scope, and pairing counts visible to the user. |
| Pipeline distribution | `samples.pipeline` and `samples.pipeline_version` aggregates | Visible sample counts and analysed progress for each observed pipeline version. |
| Finding inventory | Finding collection aggregates | Persisted small variants, CNVs, fusions, and translocations. |
| Tier distribution | `reported_variants` aggregates | Findings stored in clinical report snapshots, grouped by tier. |
| False-positive and blacklist counts | Finding and blacklist aggregates | Persisted curation and technical-artifact identities. |
| Panel gene coverage and portfolio | Active targeted-panel ASP definitions | Covered and germline gene assignments and panel metadata. |
| Panel analysis capability | Active targeted-panel ASPC definitions | Enabled analyses compared with reportable sections. |
| Clinical configuration | Active ASP and ISGL aggregates | Gene-list visibility and assay relationships. |

## Caching and Refresh Behavior

![Dashboard metric data path](../assets/diagrams/dashboard_metric_path.svg)

Expensive aggregates are generated by a scheduled Celery task and persisted as
MongoDB metric snapshots. The dashboard API reads those snapshots; opening or
refreshing the page does not run collection-wide aggregates. Redis provides a
short-lived hot cache for the persisted payload. The browser checks for a newer
snapshot periodically using the same lightweight endpoint.

Sample ingest and relevant finding, blacklist, user-access, or configuration
mutations mark existing snapshots as stale. The current snapshot remains
available while the next background refresh replaces it. Access-equivalent
users share one snapshot, so the worker does not repeat the same aggregation
for every account.

Select **Refresh metrics** to queue an immediate refresh for the current access
scope. The current values remain visible while the job runs, and the page
automatically displays the new snapshot when it is ready. This action does not
perform the aggregation in the API request.

The background schedule uses half of
`DASHBOARD_SUMMARY_SNAPSHOT_MAX_AGE_SECONDS`, with a minimum interval of 30
seconds. `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` controls snapshot retention,
and `DASHBOARD_SUMMARY_CACHE_TTL_SECONDS` controls only the Redis copy.

!!! note
    A displayed zero is a real count only when the corresponding aggregate was
    calculated successfully. A new installation can briefly return a
    preparation message until the first background snapshot is complete.
    Refresh failures leave the previous snapshot available and marked stale.
