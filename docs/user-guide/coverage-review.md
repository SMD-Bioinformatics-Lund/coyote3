# Coverage Review

The coverage workspace identifies assay regions below a selected depth cutoff
and provides the transcript, exon, CDS, and probe context needed for technical
review. Coverage is a DNA quality analysis and appears only when it is enabled
by the sample's recorded ASPC revision and coverage data was ingested for the sample.

## Open Coverage Review

1. Open a DNA sample.
2. Confirm on **Overview** that coverage data was loaded.
3. Open **Coverage**.
4. Review coverage using the warning depth configured in the sample's coverage filters.
5. Select a low-coverage gene to inspect its detailed design and measurements.

Changing the saved warning depth requests a new server-side coverage result. The displayed
counts and low-coverage lists therefore use the same cutoff.

Missing depth is shown as a neutral dash in the region table, rather than zero.
Measured zero remains a low-coverage result. Low-coverage coding
regions remain in the summary even when no probe overlaps them. Adding or removing
a blacklist entry refreshes cached coverage results; management controls require
the `coverage.blacklist:manage` permission.
Blacklisted intervals remain visible in the complete gene view and carry a
**Blacklisted** status, but are excluded from the low-region summary and low-exon
and low-probe lists. A blacklist entry matches either the stored interval key or
its displayed chromosome/start/end coordinates.

Coverage uses the assay definition captured in the sample's applied configuration,
not a newer assay revision. A nonempty `covered_genes` list defines the scope.
When that list is empty or absent, the workspace evaluates every gene present in
the sample's ingested coverage data. Missing measurements are not fabricated. Gene
lists selected for SNV, CNV, fusion, or translocation review do not change
coverage scope.

To focus the review, use **Coverage gene list** and select a list. The available
lists are captured in the sample's applied configuration. A selection includes
only genes shared by that list and the assay coverage scope; an empty list or one
with no overlapping genes shows no results. Blacklist exclusions still apply.
Choose **Assay scope** to restore the default. This is a temporary coverage-view
selection: it does not change saved finding filters and resets when another
sample is opened.

API and SDK callers can provide the optional `gene_list_id` parameter to the
coverage endpoint or `Sample.coverage()`. Responses include the selected identity
and the available `gene_lists`. Identities outside the applied configuration are
rejected.

## Summary Metrics

The top of the workspace shows:

| Metric | Meaning |
| --- | --- |
| Low regions | Number of returned regions below the selected depth cutoff. |
| Genes with coverage | Number of genes represented in the coverage payload. |
| Assay group | Biological group returned with the coverage result. |

## Low-Coverage Genes and Regions

The left pane lists genes with one or more measurements below the cutoff.
Selecting a gene restricts the low-region table and opens the complete gene
view.

| Column | Information shown |
| --- | --- |
| Gene | Gene associated with the region. Select it to open the gene view. |
| Region | Source region label. |
| Chrom | Chromosome from the coverage payload. |
| Start and End | Genomic coordinates of the measured interval. |
| Coverage | Measured depth. Values below the cutoff use the failure color. |
| Exon | Exon identifier when supplied by the source data. |

Use **Export to CSV** in the table controls to export the displayed coverage
rows.

## Gene Coverage View

The gene view uses separate genomic tracks for probes, exon design, and CDS
coverage. A shared position ruler keeps features aligned without placing exon,
CDS, and coordinate labels on top of one another. Hover over a feature, or move
keyboard focus to it, to open the inspector below the plot. The inspector shows
the feature type and identifier, exact genomic coordinates, interval length,
and measured coverage.

Use the zoom controls to change the genomic scale. At higher magnification,
scroll horizontally inside the plot to inspect the complete transcript
interval. Reset returns the viewer to its initial scale. The legend distinguishes:

- coverage below the current cutoff;
- passing probe coverage;
- passing CDS coverage; and
- regions not covered by the assay design.

Below the plot, use **Low exons** and **Low probes** to review only failed
features. The complete information area provides separate transcript, exon,
CDS, and probe tables for the selected gene.

## Coverage Blacklist

Authorized users can add a low CDS or probe interval to the assay-group scoped
coverage blacklist. Coverage blacklist entries are stored in the MongoDB
`d4_coverage_blacklist` collection. They are separate from finding blacklist entries
stored in the general `blacklist` collection.

| Entry | Stored fields | Scope and effect |
| --- | --- | --- |
| Gene | `group`, `gene`, and `region: gene` | Excludes the gene from low-coverage results for that assay group. |
| Region | `group`, `gene`, `region`, and `coord` | Excludes only the matching exon, CDS, or probe interval for that assay group. |

The `group` value is the sample's assay group. Region coordinates are stored in
a normalized form in which `:` and `-` are replaced by `_`. The combination of
assay group, gene, region type, and coordinate identifies a region entry.

Adding an entry uses `POST /api/v1/coverage/blacklist/entries`; removing one
uses `DELETE /api/v1/coverage/blacklist/entries/{id}`. Both operations require
the `coverage.blacklist:manage` permission and access to the affected assay
group. The coverage service applies these entries when it builds subsequent
low-coverage gene and region results. The original ingested coverage
measurements are not changed.

> [!WARNING]
>
> Blacklisting changes how a region is handled in subsequent review. Apply
> it only under the laboratory's approved quality procedure and confirm the
> action when prompted.
>

## Interpreting Missing Information

- **Coverage tab absent:** coverage is not enabled for the sample's recorded ASPC revision, the
  module is disabled, or no coverage resource is available for the sample.
- **No low-covered genes:** no eligible measurement is below the selected
  cutoff.
- **No design:** the payload contains a feature without a numeric coverage
  measurement.
- **Missing exon or probe details:** the ingest source did not provide that
  level of design metadata.

Coverage review supports technical assessment; it does not replace the
assay-specific acceptance criteria or laboratory quality procedure.
