# Sample input file formats

Raw analysis files supply the evidence loaded by sample ingestion. Each file contract
specifies its structure before parsing, field meanings, normalization behavior, and
stored destination. The [raw ingest file reference](ingest-files/README.md) includes
complete synthetic examples and bundle preparation requirements.

The [sample manifest](sample-manifest.md) declares sample identity, assay context, and
file paths. [Collection contracts](mongodb-collections.md) describe the resulting
database documents; database exports are not interchangeable with raw input files.

## DNA raw input files

- [Small variants: VEP-annotated VCF](ingest-files/small-variants-vcf.md)
- [Copy-number variants: JSON](ingest-files/copy-number-json.md)
- [Panel coverage: JSON](ingest-files/coverage-json.md)
- [HRD JSON](ingest-files/hrd-json.md)
- [MSI JSON](ingest-files/msi-json.md)
- [TMB JSON](ingest-files/tmb-json.md)
- [Translocations: SnpEff-annotated VCF](ingest-files/translocations-vcf.md)
- [Pharmacogenomics: JSON](ingest-files/pharmacogenomics-json.md)
- [CNV images and alignment resources](ingest-files/images-and-alignments.md)

## RNA raw input files

- [Fusions: caller evidence JSON](ingest-files/fusions-json.md)
- [Expression: sample and reference JSON](ingest-files/expression-json.md)
- [Classification: score JSON](ingest-files/classification-json.md)
- [Quality control: metrics JSON](ingest-files/quality-control-json.md)
- [Pharmacogenomics: JSON](ingest-files/pharmacogenomics-json.md)

## Submission and recovery

- [Bundle preparation and file policy](ingest-files/README.md#prepare-a-sample-bundle)
- [Ingestion API](../api/sample-ingestion.md)
- [Ingest job recovery](../operations/ingest-job-recovery.md)
