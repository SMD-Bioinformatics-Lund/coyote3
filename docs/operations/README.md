# Operations and maintenance

Operational procedures cover monitoring, incident investigation, ingest recovery,
backups, reference updates, and database migrations. Installation requirements are
defined in [Deployment](../deployment/README.md); account and clinical resource
management are covered in [Administration](../administration/README.md).

## Choose the operational task

| Situation | Start here | Follow through with |
| --- | --- | --- |
| Install, upgrade or restart | [Deployment procedures](../deployment/production-deployment.md) | [Deployment acceptance](../deployment/acceptance-checklist.md). |
| Check a running installation | [Maintenance checks](maintenance-and-verification.md) | [Monitoring and alerts](monitoring-and-alerts.md). |
| Investigate an incident | [Troubleshooting](troubleshooting.md) | [Audit events and logs](audit-and-logging.md); [backup and recovery](backup-and-recovery.md) when recovery is required. |
| Investigate a sample ingest job | [Ingest job recovery](ingest-job-recovery.md) | [Sample readiness](../user-guide/sample-readiness-and-missing-results.md) to distinguish ingest state from filtered results. |
| Investigate a worker or notification | [Background delivery and recovery](background-delivery.md) | [Email and notifications](email-and-notifications.md). |
| Update reference data | [Knowledgebase snapshots](knowledgebase-updates.md), [VEP metadata](vep-metadata-updates.md) or [HGNC genes](hgnc-gene-installation.md) | Follow the validation and activation steps for that reference. |
| Move legacy records or apply a schema migration | [Choose a migration](migrations/README.md) | The selected version's source inventory and migration procedure. |

Account permissions and clinical assay changes belong in
[administration](../administration/README.md), not infrastructure maintenance.

## Guides

| Guide | Use it to |
| --- | --- |
| [Operational Maintenance and Quality Verification](maintenance-and-verification.md) | Run maintenance checks and verify deployment data consistency. |
| [Observability SLOs and Alerts](monitoring-and-alerts.md) | Configure telemetry, service objectives, dashboards, and alerts. |
| [Audit Events And JSON Logging](audit-and-logging.md) | Trace requests, audit events, structured logs, and error references. |
| [Redis Transport Encryption](redis-tls.md) | Enable verified TLS for the production cache, Celery broker and result backend. |
| [Backup and recovery](backup-and-recovery.md) | Create archives, restore data, and use storage snapshots. |
| [Email and notifications](email-and-notifications.md) | Configure delivery, broadcasts, and notification troubleshooting. |
| [Background delivery and recovery](background-delivery.md) | Inspect worker queues, bounded retries, notification progress and report erasure. |
| [Knowledgebase Snapshot Updates](knowledgebase-updates.md) | Stage and activate supported knowledgebase snapshots. |
| [VEP metadata updates](vep-metadata-updates.md) | Update release-specific VEP metadata and diagram assets. |
| [HGNC gene installation](hgnc-gene-installation.md) | Build, validate and install the HGNC gene reference collection. |
| [Ingest job recovery](ingest-job-recovery.md) | Interpret durable receipt states and investigate delays, failures, and uncertain acknowledgements. |
| [Operational Troubleshooting & Remediation](troubleshooting.md) | Investigate operational failures and apply documented remediation. |
| [Data migrations](migrations/README.md) | Find version, clinical-rule, and database-placement migrations. |

[Documentation home](../README.md)
