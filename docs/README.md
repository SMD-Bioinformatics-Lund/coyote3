![Coyote4](assets/coyote4-logo.svg)

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

These guides describe the complete application: clinical workflows, administration,
deployment, operations and integration between components. Library and frontend
interfaces are documented in their own package guides below.

## Find a guide {#start-with-a-task}

- **[Review and report a sample](user-guide/clinical-review-workflow.md):** check findings, save your interpretation and issue a report.
- **[Configure an assay](administration/assay-setup.md#step-by-step-add-a-new-assay):** prepare its settings, activate them and check a validation sample.
- **[Try Coyote4 with synthetic samples](deployment/demo-installation.md):** choose Docker or native processes with dedicated demo storage.
- **Install Coyote4:** choose [Docker](deployment/first-installation.md) or [native Linux/WSL](deployment/installation-operations.md#native-application-on-wsl-or-linux).
- **Update an existing installation:** [upgrade the release](deployment/application-upgrades.md) or [restart the same release](deployment/application-redeployment.md).
- **Connect a pipeline:** [arrange authentication](api/authentication.md), then [submit and track samples](api/submit-sample.md).
- **[Change the code](getting-started/developer-environment.md):** prepare a local development environment.
- **Investigate a problem:** use [service troubleshooting](operations/troubleshooting.md) or [missing sample results](user-guide/sample-readiness-and-missing-results.md).

The sidebar groups guides by subject. Sections within the current page appear
beneath its sidebar entry. Search finds pages by screen name, command or setting.

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
- [API and maintenance](../api/docs/README.md): HTTP handling and host composition.
- [MongoDB adapter](../adapters/mongo/docs/README.md): persistence and transactions.
- [Python HTTP client](https://github.com/SMD-Bioinformatics-Lund/coyote-pyclient/blob/dev/docs/README.md): remote integration.
- [Ingestion service](https://github.com/SMD-Bioinformatics-Lund/coyote-relay/blob/dev/docs/README.md): submission tools and workers.
- [Atlas references](../services/atlas/docs/README.md): inspect and install HGNC/VEP reference bundles.
- [Demo datasets](../services/demo/docs/README.md): synthetic resources and guarded installation.
- [Frontend](../frontend/docs/README.md): browser application development.

The [packaging decision](architecture/decisions/0004-installable-application-packages.md)
explains the boundaries, artifact benefits and maintenance costs.
