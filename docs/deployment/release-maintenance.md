# Maintenance for the pending release

Use this release record with the [upgrade procedure](application-upgrades.md).
It applies to the changes listed under **Unreleased** in the repository changelog.
Record the reviewed commit and image digests before deployment; this page does not
assign a new release version or approve a center's promotion.

## Select the installation path

| Starting state | Required path |
| --- | --- |
| Empty application and identity databases | [First installation](first-installation.md) installs accounts, catalogs, bundled references and starter demonstrations by default. Each module has an explicit skip flag. |
| Existing v4 installation | Preserve installed data. Use the maintenance steps below; do not rerun fresh bootstrap. |
| Supported v2 or v3 database | Complete the corresponding [migration](../operations/migrations/README.md) before normal v4 operation. Retain migration validation and recovery evidence. |

Fresh accounts receive temporary passwords and must change them at first sign-in.
Later bundled-data additions or selected repairs use
`scripts/deployment/manage_data.py --api-url URL --modules MODULE ...`; `--force`
repairs only the selected modules. The command authenticates through the API,
completes a required password change, and relies on server-side authorization.
See [installation and data maintenance](installation-operations.md).

## Before replacing services

1. Follow the upgrade guide to preserve the previous images, environment, center
   files, ordered Compose overlays and configuration. Record whether production
   Redis TLS is selected. It remains optional; development/staging do not use it.
2. Pause application writes and drain both Celery queues. Keep API, ingest worker,
   maintenance worker, beat and monitor stopped for the coordinated backup and
   database maintenance window. Preserve pending Redis work and persistent roots.
3. Back up application, identity, knowledgebase and BAM databases according to their
   separate endpoint/name pairs. Back up report storage, audit disk spools and
   notification/error-mail state. Export the last successful audit verification to
   independently controlled storage; do not replace a trusted checkpoint on failure.
4. If the installation has the old notification `expires_on` TTL index, follow
   [notification retention migration](../operations/email-and-notifications.md#existing-installations).
   Review its dry run before applying. It preserves remaining records; it cannot
   recover notifications already deleted by the old index.
5. Plan and apply the declared application/identity indexes using the upgrade
   procedure. These include report-erasure route/attempt and route/age indexes and
   the audit activity cursor index. Separately plan/apply knowledgebase indexes
   with approved maintenance privileges, including the publication cursor index.
   The index tool's default scope is `application`; select `--scope knowledgebase`
   for reference indexes. Stop on conflicts; index application does not authorize
   dropping indexes or replacing data.
6. Review installed RBAC against the bundled catalog. Sample deletion requires
   `sample:delete:global`; ordinary authenticated users must not gain it. Retain
   center-specific grants. Use the upgrade guide's catalog plan before applying
   changes. Clinical-rule/query releases remain governed resources, not incidental
   deployment replacements.

The audit chain applies to supported new traceability events. Historical unchained
events remain explicitly outside the chain; verification does not turn them into
cryptographically proven history. Do not rewrite existing events to hide this boundary.

## Runtime changes

- Query policies and clinical reporting rules now resolve current published scopes
  for subsequent requests, independently of the sample's ASPC revision. Before
  rollout, review the active publications for every deployed scope: current rules
  may differ from historical ASPC captures. New ASPC writes exclude rule captures;
  retained historical fields are ignored and need no destructive migration. Saved
  reports and their original receipts are preserved. A rule publication after a
  report preview requires reviewing a fresh preview before saving.

- Application identity comes from `release.toml`; SDK identity comes from
  `pyproject.toml`. Retain the selected SDK wheel and its SHA-256 release record.
  See [versions and compatibility](../sdk/compatibility.md). Existing development
  installations must reinstall the library after this layout change.
- Center examples now live in `config/examples/center/`. Keep deployed center
  directories external and update any explicit paths pointing into the old SDK
  or `api/config/center/` location. API and workers select the same profile before
  importing vocabulary-dependent contracts; changing profiles requires restart.

- Deploy matching API/frontend images and both workers, beat and monitor. The
  ingest worker consumes `ingest`; `maintenance-worker` consumes `default` for
  audit replay, notifications and maintenance. Stop older combined-queue workers.
- Reuse the same approved overlays for bootstrap, startup, upgrade and recovery.
  If production Redis TLS was selected, provision the CA/server files before
  recreation and verify connections from clients as well as Redis itself.
- Clinical inbox messages now require current `sample:view` permission and current
  sample scope. Previously addressed notices become hidden after access revocation
  or sample deletion. Administrative announcements retain recipient-based visibility.
- Structural finding detail reads require the canonical `SAMPLE_ID` ownership field.
  Malformed or unmigrated findings are rejected rather than admitted by a secondary
  list lookup. Use the supported data migration/validation process for old records.
- SNV exclusions are saved in each intent's existing SNV filter blob. Empty
  `exclude_flags` preserves prior behavior. Configured raw flag names, rather than
  hardcoded frontend options or display labels, supply choices.
- New activity progress is initialized automatically in its internal application
  collection. Existing notification IDs and recipient state are preserved. Late
  audit arrivals are found through bounded cyclic reconciliation within retention.
- Error-mail retries, quarantine, spool capacity and report-erasure diagnosis are
  described in [background delivery](../operations/background-delivery.md).

## Verify and recover

Complete the [acceptance checklist](acceptance-checklist.md) with representative
synthetic DNA/RNA samples, first-login password setup, restricted roles, current
clinical inbox access, worker consumers, report snapshots and audit verification.
Observe report-erasure backlog and monitor status. Check the
[email channel controls](../operations/email-and-notifications.md#runtime-email-switch);
the application email switch does not pause the standalone monitor.

Restore testing must use an isolated target. Verify the chain against the retained
checkpoint and reconcile the report-volume device/inode before erasure resumes.
A replaced mount correctly blocks pending jobs; do not bypass the guard by changing
queued paths or route identities.

An older application may not understand new queue ownership, notification retention
or committed erasure jobs. Establish compatibility before application-only rollback.
If data/files/queues require coordinated restoration, follow the approved recovery
plan while preserving post-backup work and audit evidence. Restoring images cannot
undo already completed file erasure or recall accepted email.

Repository test results are recorded in the audit. They do not substitute for the
center's live certificate checks, authenticated acceptance, backup/restore rehearsal
or capacity assessment.
