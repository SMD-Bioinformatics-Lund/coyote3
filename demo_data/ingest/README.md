# Ingest Demo Fixtures

These files are privacy-safe, compact fixtures for sample ingestion flows.

- `generic_case_control.yaml`: Canonical DNA case-control ingestion manifest,
  including an explicit database-version snapshot.
- `generic_rna_sample.yaml`: Canonical unpaired WTS ingestion manifest with
  fusion, expression, classification, and QC resources.
- `generic_case_control.final.filtered.vcf`: Small VCF with case/control columns.
- `generic_case_control.cnvs.merged.json`: Minimal CNV payload.
- `generic_case_control.cov.json`: Minimal coverage payload.
- `generic_case_control.modeled.png`: Placeholder CNV profile image.
- `generic_rna_expression.json`, `generic_rna_classification.json`, and
  `generic_rna_qc.json`: Single-object raw RNA inputs, without the array wrapper
  used by collection seed exports.

The YAML files represent the raw manifests produced by analysis pipelines. Case
and control metadata therefore use top-level `case_*` and `control_*` keys, and
analysis resources use top-level keys such as `vcf_files`, `cnv`,
`fusion_files`, and `expression_path`. Ingestion converts those fields into the
nested `case`, `control`, and `files` structure stored in the sample document.
Optional file keys may be omitted, but any declared file must be readable and
successfully parsed for the sample to become `ready`.

Optional `case_bam`, `case_bai`, `control_bam`, and `control_bai` are IGV file
references, not analysis resources. They become nested sample metadata and may
be omitted; ingest does not read or copy their file contents.

The DNA manifest uses paths relative to its own directory. Keep
`generic_case_control.yaml` and its four `generic_case_control.*` resources
together when copying the fixture into a watch directory. This matches the
ingest service's manifest-relative path resolution and keeps the bundle
portable between the repository, upload staging, and container mounts.

Identity and deployment scope use the pipeline keys `assay`, `subpanel`, and
`profile`. Sequencing metadata uses `sequencing_technology`; ingestion maps
these fields to the internal sample contract and derives `read_technology`.
RNA fusion ingest does not use VEP, so the RNA example has no VEP database
version.

The payloads are intentionally generic and do not contain patient identifiers.
