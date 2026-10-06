# Application control settings

Application controls are database-backed settings managed in the administration
workspace. They are not TOML keys or environment-file assignments. Viewing requires
`app.controls:view`; editing requires `app.controls:edit`; an explicit maintenance
run requires `app.maintenance:run`.

## Fields and defaults

The active record uses `control_id: "default"`. The following are contract defaults;
initial retention values are populated from the environment settings shown in the
table. An existing saved control is not replaced by editing the environment file.

| Key | Type / allowed values | Default or initialization | Meaning |
| --- | --- | --- | --- |
| `email.enabled` | Boolean | `true` | Outgoing application email switch; SMTP connectivity is configured separately. |
| `celery.enabled` | Boolean | `true` | Overall background-task switch. |
| `celery.sample_ingest_enabled` | Boolean | `true` | Sample-ingest task-family switch. |
| `celery.collection_writes_enabled` | Boolean | `true` | Collection-write task-family switch. |
| `celery.maintenance_enabled` | Boolean | `true` | Maintenance task-family switch. |
| `retention.audit_events_days` | Integer, 30–3650 days | `AUDIT_RETENTION_DAYS`, otherwise 730 | Operational audit-event retention; not a blanket clinical-record deletion policy. |
| `retention.notification_days` | Integer, 7–3650 days | `NOTIFICATION_RETENTION_DAYS`, otherwise 180 | Notification retention. |
| `retention.disk_log_days` | Integer, 1–3650 days | `LOG_RETENTION_DAYS`, otherwise 30 | Disk-log retention. |
| `retention.gzip_disk_logs_after_days` | Integer, 1–3650 days, no greater than disk-log retention | `LOG_GZIP_AFTER_DAYS`, otherwise 7 | Age at which eligible logs are compressed. |
| `modules.dna_analysis_enabled` | Boolean | `true` | DNA module availability. |
| `modules.rna_analysis_enabled` | Boolean | `true` | RNA module availability. |
| `modules.reports_enabled` | Boolean | `true` | Reporting module availability. |
| `modules.variant_search_enabled` | Boolean | `true` | Variant search availability. |
| `modules.knowledgebases_enabled` | Boolean | `true` | Knowledgebase module availability. |
| `modules.ingest_workspace_enabled` | Boolean | `true` | Ingest workspace availability. |
| `modules.assay_catalog_enabled` | Boolean | `true` | Assay catalog availability. |
| `curation.tiering.small_variant_enabled` | Boolean | `true` | SNV tier mutation availability. |
| `curation.tiering.fusion_enabled` | Boolean | `true` | Fusion tier mutation availability. |
| `curation.tiering.cnv_enabled` | Boolean | `false` | CNV tier mutation availability. |
| `curation.tiering.translocation_enabled` | Boolean | `false` | Translocation tier mutation availability. |

Fields with defaults may be omitted when constructing a new contract-shaped record;
this does not imply a partial update request preserves omitted settings. Edit through
the control form and review the complete saved result. Actor/time fields are managed
by the service. Full storage contract: [`app_controls`](../reference/mongodb-collections.md#app_controls).

## Applying controls

A switch expresses configured availability. It does not start Docker containers,
prove a worker is connected, grant a permission or enable an unimplemented analysis.
The controls screen displays observed worker state separately. Disabling a task
family is not proof that already-running work has stopped; inspect active work and
follow the [upgrade drain procedure](../deployment/application-upgrades.md).

Module controls do not erase stored findings or reports. Tiering controls govern
mutations and do not rewrite historical classifications. Retention acts through
maintenance and applies to its specific operational data, not to all MongoDB
collections. See [audit and logging](../operations/audit-and-logging.md) and
[maintenance](../operations/maintenance-and-verification.md) before changing retention.

For example, `email.enabled = false` describes the stored boolean setting, not
an environment assignment. Use the application form to change it. SMTP host,
credentials and sender addresses remain [deployment settings](../deployment/configuration-reference.md#environment-variable-reference).
