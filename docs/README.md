# Coyote4 documentation

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

<img src="assets/coyote4-logo.svg" alt="Coyote4" width="360">

These guides describe the complete application: clinical workflows, administration,
deployment, operations and integration between components. Library and frontend
interfaces are documented in their own package guides below.

## Start with a task

<div class="docs-task-start" markdown="1">

- **[Review and report a sample](user-guide/clinical-review-workflow.md):** check findings, save your interpretation and issue a report.
- **[Configure an assay](administration/assay-setup.md#step-by-step-add-a-new-assay):** prepare its settings, activate them and check a validation sample.
- **[Try Coyote4 locally](getting-started/local-quickstart.md):** start an application with synthetic starter data.
- **[Install at a center](deployment/first-installation.md):** prepare services, baseline data and the initial account.
- **Update an existing installation:** [upgrade the release](deployment/application-upgrades.md) or [restart the same release](deployment/application-redeployment.md).
- **Connect a pipeline:** [arrange authentication](api/authentication.md), then [submit and track samples](api/sample-ingestion.md).
- **[Change the code](getting-started/developer-environment.md):** prepare a local development environment.
- **Investigate a problem:** use [service troubleshooting](operations/troubleshooting.md) or [missing sample results](user-guide/sample-readiness-and-missing-results.md).

</div>

Follow the numbered steps in the selected guide. You do not need to read the
whole manual. The sidebar puts those procedures first; supporting references
are one group below them. Search is useful when you already know a field or screen name.

## Terms used in the guides

| Term | Meaning |
| --- | --- |
| Assay / ASP | The physical assay definition |
| Assay configuration / ASPC | Analysis and reporting settings for an assay, diagnosis and environment |
| Gene list / ISGL | A versioned list selected by a configuration or sample filter |
| Query rule | A condition used to select findings |
| Reporting rule | A condition and text used to suggest report wording |
| Report template | The HTML/PDF layout supplied by `smd-reports` |

For exact fields, open the [configuration reference](configuration/README.md),
[sample input formats](reference/ingest-files/README.md) or
[collection contracts](reference/mongodb-collections.md). These are lookup material,
not additional steps in every workflow.

See [clinical concepts](reference/clinical-concepts.md) for detailed definitions,
and [writing documentation](development/writing-documentation.md) for contribution guidance.

## Package guides

- [Clinical core](../core/docs/README.md): trusted in-process clinical operations.
- [API and workers](../api/docs/README.md): HTTP handling and host composition.
- [MongoDB adapter](../adapters/mongo/docs/README.md): persistence and transactions.
- [Python HTTP client](../clients/python/docs/README.md): remote integration.
- [Frontend](../frontend/docs/README.md): browser application development.

The [packaging decision](architecture/decisions/0004-installable-application-packages.md)
explains the boundaries, artifact benefits and maintenance costs.
