# Operational Dashboard

The dashboard summarizes the samples, findings, review workload, and clinical
configuration visible to the signed-in user. It uses aggregated API responses
instead of loading complete clinical collections into the browser.

![Coyote3 operational dashboard](../assets/screenshots/dashboard.png)

> **Info**
>
> Dashboard counts respect the user's role, assay, and environment scope.
> Two users can therefore see different totals from the same deployment.
>

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

The **Top Tiered Genes** table ranks up to 15 genes by their unique current Tier
1-4 biological findings. Protein, cDNA, and genomic annotation records that
share a genomic identity contribute one count, and the latest classification
sets that finding's tier. Fusion and translocation records contribute once to
each distinct partner gene. Records without a gene identity are not included.
The metric is calculated from the configured
`annotation` collection; it does not use report snapshots or the
`reported_variants` collection. Selecting a gene opens its Gene Cohort Explorer
view.

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

## Metric Refresh Behavior

![Dashboard metric data path](../assets/diagrams/dashboard_metric_path.svg)

MongoDB collections remain the source of truth. Dashboard aggregates are split
into independent metrics and cached briefly in Redis. Opening the dashboard
therefore reads small cached payloads instead of running every collection-wide
aggregate in one request.

| Metric | API endpoint | Main source collections |
| --- | --- | --- |
| Sample workload | `/api/v1/dashboard/metrics/samples` | `samples`, with the current user's assay scope |
| Finding review | `/api/v1/dashboard/metrics/findings` | `variants`, `cnvs`, `fusions`, `translocations`, `blacklist`, `annotation`, and `reported_variants` |
| Top tiered genes | `/api/v1/dashboard/metrics/top-tiered-genes` | `annotation` |
| Panel inventory | `/api/v1/dashboard/metrics/panels` | `assay_specific_panels` and `asp_configs` |
| Clinical configuration | `/api/v1/dashboard/metrics/clinical-configuration` | `assay_specific_panels` and `insilico_genelists` |
| Resource capacity | `/api/v1/dashboard/metrics/resources` | `users`, `roles`, ASP, ASPC, and ISGL repositories |

Each section is requested independently. A failure in one metric displays an
error for that section while the remaining dashboard continues to work.

A fresh cache entry is returned immediately. When an entry reaches its
freshness limit, the API returns the existing value and queues a refresh for
that metric. On a cache miss, the metric is calculated once and stored. A
short-lived distributed lock prevents simultaneous requests from scheduling
the same work repeatedly.

Writes invalidate only dependent metrics. For example, a variant update marks
the finding metric stale but does not invalidate panel inventory. Equivalent
authorization scopes share sample and resource cache entries; global metrics
share one entry across users.

Select **Refresh metrics** to queue all dashboard metrics for the current
access scope. The current values remain visible while Celery recalculates them,
and the browser checks the individual endpoints for replacements.

`DASHBOARD_METRIC_CACHE_TTL_SECONDS` sets the freshness limit. Celery Beat also
warms metrics at half this interval, with a minimum interval of 30 seconds.
`DASHBOARD_METRIC_CACHE_RETENTION_SECONDS` determines how long an unused Redis
entry can remain available.

> **Note**
>
> A displayed zero is a real count only when the corresponding aggregate was
> calculated successfully. Refresh failures leave an existing cached value
> visible and marked stale.
