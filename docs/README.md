# Coyote3 documentation

Coyote3 supports clinical genomics workflows from sample ingestion and assay-aware
review to classification and reporting. Documentation covers clinical workflows,
assay configuration, access management, integration, deployment, and operations.

## Start with a task

Pick the outcome you need below. Each link opens the procedure itself. Its reading
path shows the next task page; **On this page** opens the local section list.
References provide optional detail, with a return link to your place in the procedure.

| Task | Start here |
| --- | --- |
| Evaluate Coyote3 locally | [Local quickstart](getting-started/local-quickstart.md) |
| Install at a new center | [First installation](deployment/first-installation.md), then the [deployment acceptance checklist](deployment/acceptance-checklist.md) |
| Prepare the deployment environment file | [Environment file fields and examples](configuration/environment-file.md) |
| Update or restart an existing installation | [Choose a procedure](deployment/production-deployment.md) |
| Migrate an existing Coyote v2 or v3 database | [Select the source version and follow the migration procedure](operations/migrations/clinical-data.md#select-the-source-version) |
| Review a DNA or RNA sample | [Clinical review workflow](user-guide/clinical-review-workflow.md) |
| Explain a missing sample, tab, or result | [Sample readiness and missing results](user-guide/sample-readiness-and-missing-results.md) |
| Set up an assay for the first time | [Prerequisites and setup steps](administration/assay-setup.md#step-by-step-add-a-new-assay) |
| Understand application query defaults or change finding selection | [Base queries by analysis](administration/query-rules.md#application-base-queries-by-analysis), then [UI rule inheritance](administration/query-rules.md#scope-and-inheritance) |
| Manage accounts and access | [Permissions and access control](administration/permissions-and-access.md) |
| Plan a clinical configuration change | [Planning configuration changes](administration/planning-configuration-changes.md) |
| Submit samples from a pipeline or client | [Sample ingestion API](api/sample-ingestion.md) and [sample manifest](reference/sample-manifest.md) |
| Make your first code change | [Developer environment setup](getting-started/developer-environment.md) |
| Use the remote Python client | [Client installation and usage](sdk/python-client.md) |
| Build a trusted Python application host | [Application SDK operations](sdk/application-sdk.md) |
| Investigate an installed-system failure | [Operations troubleshooting](operations/troubleshooting.md) |
| Investigate an accepted or failed ingest job | [Ingest job recovery](operations/ingest-job-recovery.md) |

## Browse the documentation tree

Use this index when you are looking up a subject rather than following a task.

<details markdown="1">
<summary>Open the complete section index</summary>

| Directory | What belongs here |
| --- | --- |
| [getting-started/](getting-started/README.md) | Entry point for evaluation, first installation, upgrades, redeployment and configuration references. |
| [user-guide/](user-guide/README.md) | Clinical review, samples, coverage, dashboards, pages, and controls. |
| [administration/](administration/README.md) | Users, access, assay groups, diagnoses, clinical configuration, and catalog publication. |
| [api/](api/README.md) | Authentication, HTTP routes, ingestion, collection imports, and compatibility. |
| [sdk/](sdk/README.md) | Python installation, local operations, remote client, host development, reference and independent versions. |
| [architecture/](architecture/README.md) | Components, resource relationships, clinical data flow, security, and design decisions. |
| [deployment/](deployment/README.md) | Installation and infrastructure source guides, grouped under Getting started in the site. |
| [configuration/](configuration/README.md) | File syntax, supported fields, defaults, examples and links to clinical resource contracts. |
| [development/](development/README.md) | Code structure, extension guides, frontend components, commands, and documentation practices. |
| [operations/](operations/README.md) | Monitoring, logs, incidents, backups, reference updates, and migrations. |
| [reference/](reference/README.md) | Clinical concepts, rules, report snapshots, input formats, and database contracts. |
| [testing/](testing/README.md) | Quality gates, synthetic fixtures, browser validation, and load testing. |
| [project/](project/README.md) | Contribution, maintenance, governance, conduct, and licensing. |

</details>

## Frequently used references

- [Samples and clinical review](user-guide/sample-management.md)
- [Assays, configurations, and gene lists](user-guide/gene-lists-and-assay-context.md)
- [Assay groups](administration/assay-groups.md) and [diagnoses](administration/assay-diagnoses.md)
- [Report preview and save](user-guide/application-guide.md#reports)
- [Raw ingest files and examples](reference/ingest-files/README.md)
- [Clinical concepts and resource identities](reference/clinical-concepts.md): ASP,
  ASPC, ISGL, samples, cases, findings, and reports.
- [Clinical reporting rules](reference/clinical-reporting-rules.md): rule syntax,
  scope selection, validation, and publication.
- [MongoDB collection contracts](reference/mongodb-collections.md): generated field
  definitions used by collection validation.
- [Permission catalog](administration/permission-catalog.md): generated identifiers
  and capabilities installed with the application.
- [Center configuration files](deployment/center-configuration.md): supported
  center-owned files and settings.

## Documentation sources and site support

Documentation is maintained alongside the application source. Contribution standards,
site configuration, and validation commands are defined in
[Writing documentation](development/writing-documentation.md).
