# Coyote3 documentation

Coyote3 supports clinical genomics workflows from sample ingestion and assay-aware
review to classification and reporting. Documentation covers clinical workflows,
assay configuration, access management, integration, deployment, and operations.

## Start with a task

| Task | Start here |
| --- | --- |
| Evaluate Coyote3 locally | [Local quickstart](getting-started/local-quickstart.md) |
| Install at a new center | [First installation](deployment/first-installation.md), then the [installation checklist](deployment/installation-checklist.md) |
| Migrate an existing Coyote v3 database | [Upgrade from v3](operations/migrations/upgrade-from-v3.md) |
| Review a DNA or RNA sample | [Clinical review workflow](user-guide/clinical-review-workflow.md) |
| Explain a missing sample, tab, or result | [Sample readiness and missing results](user-guide/sample-readiness-and-missing-results.md) |
| Manage accounts or clinical configuration | [Application administration](administration/administration-guide.md) |
| Plan a clinical configuration change | [Planning configuration changes](administration/planning-configuration-changes.md) |
| Submit samples from a pipeline or client | [Sample ingestion API](api/sample-ingestion.md) and [sample manifest](reference/sample-manifest.md) |
| Change or extend the application | [Developer guide](development/developer-guide.md) |
| Investigate an installed-system failure | [Operations troubleshooting](operations/troubleshooting.md) |
| Investigate an accepted or failed ingest job | [Ingest job recovery](operations/ingest-job-recovery.md) |

## Browse the documentation tree

| Directory | What belongs here |
| --- | --- |
| [getting-started/](getting-started/README.md) | Local quickstart and developer environment setup. |
| [user-guide/](user-guide/README.md) | Clinical review, samples, coverage, dashboards, pages, and controls. |
| [administration/](administration/README.md) | Users, access, assay groups, subpanels, clinical configuration, and catalog publication. |
| [api/](api/README.md) | Authentication, HTTP routes, ingestion, collection imports, and compatibility. |
| [architecture/](architecture/README.md) | Components, resource relationships, clinical data flow, security, and design decisions. |
| [deployment/](deployment/README.md) | Installation, infrastructure, center configuration, and acceptance checklists. |
| [development/](development/README.md) | Code structure, extension guides, frontend components, commands, and documentation practices. |
| [operations/](operations/README.md) | Monitoring, logs, incidents, backups, reference updates, and migrations. |
| [reference/](reference/README.md) | Clinical concepts, rules, report snapshots, input formats, and database contracts. |
| [testing/](testing/README.md) | Quality gates, synthetic fixtures, browser validation, and load testing. |
| [project/](project/README.md) | Contribution, maintenance, governance, conduct, and licensing. |

## Frequently used references

- [Samples and clinical review](user-guide/sample-management.md)
- [Assays, configurations, and gene lists](user-guide/gene-lists-and-assay-context.md)
- [Assay groups](administration/assay-groups.md) and [subpanels](administration/assay-subpanels.md)
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
