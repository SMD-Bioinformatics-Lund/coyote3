# Ingest Demo Fixtures

These files are privacy-safe, compact fixtures for sample ingestion flows.

- `generic_case_control.yaml`: Example DNA ingestion spec, including `vep_version`.
- `generic_rna_sample.yaml`: Example RNA ingestion spec, including `vep_version`.
- `generic_case_control.final.filtered.vcf`: Small VCF with case/control columns.
- `generic_case_control.cnvs.merged.json`: Minimal CNV payload.
- `generic_case_control.cov.json`: Minimal coverage payload.
- `generic_case_control.modeled.png`: Placeholder CNV profile image.

The YAML manifests use the canonical nested `files.<file_key>.path` format.
Optional file keys may be omitted, but any declared file must be readable and
successfully parsed for the sample to become `ready`.

The payloads are intentionally generic and do not contain patient identifiers.
