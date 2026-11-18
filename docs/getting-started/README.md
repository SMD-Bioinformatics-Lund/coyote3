# Find the right guide {#getting-started}

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Choose the operation you want to perform on the
[documentation home page](../README.md#start-with-a-task).

- To evaluate Coyote4 with synthetic samples, follow the [isolated demo installation](../deployment/demo-installation.md).
- To run the ordinary development containers, use the [local development stack](local-quickstart.md).
- To work on source code, use the [developer environment](developer-environment.md).
- To install Coyote4, choose [Docker](../deployment/first-installation.md) or [native Linux/WSL](../deployment/installation-operations.md#native-application-on-wsl-or-linux).
- To review a sample, use the [clinical review workflow](../user-guide/clinical-review-workflow.md).

## Procedures and references {#choose-a-reading-path}

A procedure gives ordered actions and the result to check. A reference explains
individual fields, defaults and constraints. Follow the procedure; open a linked
reference only when you need that detail. Use browser Back to return.

## Find the right kind of rule or setting

- **Query rules** select findings: [query administration](../administration/query-rules.md).
- **Review filters** set depth, frequency and gene scope: [filter fields](../reference/filter-profile-fields.md).
- **Reporting rules** generate suggested text: [wording editor](../administration/report-rule-authoring.md).
- **Report presentation** controls supported display settings: [presentation file](../configuration/report-presentation-file.md).
- **Deployment settings** configure endpoints, secrets and paths: [environment reference](../deployment/configuration-reference.md).

## Using the documentation navigation

The sidebar groups guides by subject: User guide, Administration, Installation,
Operations, API and integrations, Packages, Development and Reference. Expand the
current page's sidebar entry to jump to a section. Links in the text open related
instructions; use browser Back to return.

Text such as `<RELEASE_TAG>` is a placeholder to replace. Values in examples are
not an approved center configuration.

## Installation and updates

Use the [installation guide](../deployment/README.md) to select a new deployment,
[upgrade](../deployment/application-upgrades.md) for a changed release,
or [redeploy](../deployment/application-redeployment.md) to restart the same release.

## Read a procedure and its references

Each guide states its prerequisites, steps and expected results. If an action
fails, use the linked troubleshooting section before continuing. API endpoints,
configuration keys and defaults should be checked in their reference rather than
inferred from example filenames or shell variables.
