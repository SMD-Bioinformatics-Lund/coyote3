# Synthetic demo bundle

This directory contains the resources installed by the demo installation service.
All samples and measurements are synthetic. Gene symbols are real vocabulary;
coordinates, transcript identifiers and HGVS strings are artificial test values.

| Directory | Contents |
| --- | --- |
| `setup/` | Shared assays, diagnoses, gene lists, testing configurations, catalog offerings and published rules |
| `raw/` | VCF, JSON and image inputs consumed by the normal ingestion service |
| `starter/` | DNA and RNA manifests used by initial demo installation |
| `manifests/` | Additional selectable demo workflows |

The starter and additional workflows use the same setup resources and raw files.
Manifest file paths are relative to their containing directory. BAM and BAI fields
are null because this bundle does not include alignments.

See the [installation guide](../../docs/testing/clinical-workflow-demo.md) and
[file-format reference](../../docs/testing/demo-data-bundle.md).

Negative cases, scenario assertions and generated expected results live in
[tests/fixtures/clinical_workflows](../../tests/fixtures/clinical_workflows/README.md).
They are not installation inputs.
