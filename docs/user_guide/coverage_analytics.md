# Coverage Review

The coverage workspace identifies assay regions below a selected depth cutoff
and provides the transcript, exon, CDS, and probe context needed for technical
review. Coverage is a DNA quality analysis and appears only when it is enabled
by the sample's recorded ASPC revision and coverage data was ingested for the sample.

## Open Coverage Review

1. Open a DNA sample.
2. Confirm on **Overview** that coverage data was loaded.
3. Open **Coverage**.
4. Set the depth cutoff appropriate for the validated assay workflow.
5. Select a low-coverage gene to inspect its detailed design and measurements.

Changing the cutoff requests a new server-side coverage result. The displayed
counts and low-coverage lists therefore use the same cutoff.

## Summary Metrics

The top of the workspace shows:

| Metric | Meaning |
| --- | --- |
| Low regions | Number of returned regions below the selected depth cutoff. |
| Genes with coverage | Number of genes represented in the coverage payload. |
| Cutoff | Depth threshold, in `X`, used to classify a measured region as low or passing. |

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

The gene view draws the transcript interval and the available exon, CDS, and
probe records. Hover a region to read its exact coordinates and measured
coverage. The legend distinguishes:

- coverage below the current cutoff;
- passing probe coverage;
- passing CDS coverage; and
- regions not covered by the assay design.

Below the plot, use **Low exons** and **Low probes** to review only failed
features. The complete information area provides separate transcript, exon,
CDS, and probe tables for the selected gene.

## Coverage Blacklist

Authorized users can add a low CDS or probe interval to the assay-group scoped
coverage blacklist. The action records the genomic region, gene, and relevant
sample context through the coverage blacklist API.

!!! warning
    Blacklisting changes how a region is handled in subsequent review. Apply
    it only under the laboratory's approved quality procedure and confirm the
    action when prompted.

## Interpreting Missing Information

- **Coverage tab absent:** coverage is not enabled for the sample's recorded ASPC revision, the
  module is disabled, or no coverage resource is available for the sample.
- **No low-covered genes:** no returned measurement is below the selected
  cutoff and applied gene-list scope.
- **No design:** the payload contains a feature without a numeric coverage
  measurement.
- **Missing exon or probe details:** the ingest source did not provide that
  level of design metadata.

Coverage review supports technical assessment; it does not replace the
assay-specific acceptance criteria or laboratory quality procedure.
