# Testing and validation

Verification includes automated quality gates, synthetic fixtures, disposable-stack
checks, browser acceptance, and load testing. Synthetic load tests require an
explicitly approved target and do not establish clinical validation.

## Choose the checks for your task

- **Code change:** [test strategy and quality gates](test-strategy-and-quality-gates.md),
  using [synthetic fixtures](test-data-and-fixtures.md).
- **Installation or end-to-end workflow:** [disposable stack](disposable-stack-validation.md),
  then [clinical workflow exercises](clinical-workflow-demo.md).
- **Release verification:** [browser and release validation](browser-and-release-validation.md)
  and the operator's [deployment acceptance checklist](../deployment/acceptance-checklist.md).
- **Capacity measurement:** [load testing](load-and-capacity-testing.md) against an
  explicitly approved synthetic target.

For assay configuration prerequisites, return to [assay setup](../administration/assay-setup.md).
For development commands and failure diagnosis, use [development](../development/README.md).

## Guides

| Guide | Use it to |
| --- | --- |
| [Test strategy and quality gates](test-strategy-and-quality-gates.md) | Understand testing boundaries, coverage, and repository quality checks. |
| [Validation Datasets and Test Fixtures](test-data-and-fixtures.md) | Use synthetic fixtures, bootstrap catalogs, and ingest examples. |
| [Synthetic clinical workflow exercises](clinical-workflow-demo.md) | Ingest portable raw demo files and exercise query policies, filters, tiers, comments and report workflows. |
| [Demo data bundle](demo-data-bundle.md) | Locate shared raw inputs, read the manifest and analysis formats, and replay the bundle in mongomock. |
| [Local disposable full-stack validation](disposable-stack-validation.md) | Create an isolated full stack for installation and workflow checks. |
| [Browser And Release Validation](browser-and-release-validation.md) | Run browser acceptance and release validation gates. |
| [Load and capacity testing](load-and-capacity-testing.md) | Configure approved synthetic workloads and interpret capacity measurements. |

[Documentation home](../README.md)
