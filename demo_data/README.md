# Demonstration data

[clinical_workflows](clinical_workflows/README.md) is the installable synthetic
dataset. Its setup resources define the demo catalog; YAML manifests and raw
analysis files pass through the application's normal ingestion service.

Negative cases, scenario assertions and generated expected results live in
[workflow test fixtures](../tests/fixtures/clinical_workflows/README.md).

Isolated collection and parser examples live in
[tests/fixtures](../tests/fixtures/). They are test inputs and are not installed.
