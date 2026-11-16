# Find the right guide {#getting-started}

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Choose the operation you want to perform on the
[documentation home page](../README.md#start-with-a-task).

- To evaluate Coyote4 with synthetic samples, follow the [isolated demo installation](../deployment/demo-installation.md).
- To run the ordinary development containers, use the [local development stack](local-quickstart.md).
- To work on source code, use the [developer environment](developer-environment.md).
- To deploy at a center, use [first installation](../deployment/first-installation.md).
- To review a sample, use the [clinical review workflow](../user-guide/clinical-review-workflow.md).

## Choose a reading path

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

Start with a direct task link in the sidebar. Its reference group contains extra
detail, not another required reading sequence. **On this page** lists headings
inside the current guide. Text such as `<RELEASE_TAG>` is a placeholder to replace;
values in examples are not an approved center configuration.

## Installation and updates

Use [first installation](../deployment/first-installation.md) for a new application
database, [upgrade](../deployment/application-upgrades.md) for a changed release,
or [redeploy](../deployment/application-redeployment.md) to restart the same release.

## Read a procedure and its references

Each guide states its prerequisites, steps and expected results. If an action
fails, use the linked troubleshooting section before continuing. API endpoints,
configuration keys and defaults should be checked in their reference rather than
inferred from example filenames or shell variables.
