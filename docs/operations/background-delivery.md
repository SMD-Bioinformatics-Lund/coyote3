# Background delivery and recovery

Use this procedure when notifications, audit delivery, error emails or report-file
erasure are delayed. For ingest receipts, use [ingest job recovery](ingest-job-recovery.md).
For SMTP setup, use [email and notifications](email-and-notifications.md).

## Worker ownership

The base Compose stack runs two Celery workers from the same API image:

| Service | Queue | Work |
| --- | --- | --- |
| `worker` | `ingest` | Sample and collection ingestion. |
| `maintenance-worker` | `default` | Audit replay, activity notices, broadcast delivery, erasure and scheduled maintenance. |
| `beat` | Schedules both queues | Publishes scheduled tasks; it does not execute them. |
| `monitor` | No Celery dependency | Reads disk logs and retries system-error emails. |

Long ingests cannot consume maintenance-worker slots. Maintenance tasks still share
their own pool; inspect active tasks and queue consumers in Application controls
when that pool is busy. Default concurrency is two processes for each worker.
`CELERY_WORKER_CONCURRENCY` controls ingestion; `CELERY_MAINTENANCE_CONCURRENCY`
controls maintenance. The latter service defaults to one CPU and 1 GiB, configurable
with `COYOTE3_MAINTENANCE_CPU_LIMIT` and `COYOTE3_MAINTENANCE_MEM_LIMIT`.

Recreate API, both workers, beat and monitor with the same release and the same
environment/overlay selection. Development and storage overlays include both
workers. The optional production Redis TLS overlay supplies the CA and verified
Redis URLs to both. Keep older combined-queue workers stopped after the change.
This change does not require creating or replacing the application network.

## Activity notices

Each poll reads at most 100 source rows by default: 25 forward and 25 reconciliation
rows from each of the audit and knowledgebase release collections. Stable compound
cursors are stored in the application's `notification_activity_progress` collection,
keyed by environment. Positions are acknowledged only after notification writes.
Retries retain stable notification IDs and existing read/dismissal state.

The cyclic reconciliation reader catches audit-outbox events that arrive behind
the forward cursor. Such events can wait for one complete reconciliation cycle;
this delay grows with retained history. Events outside notification retention are
not delivered. No source audit event is modified to mark notification delivery.

Apply the current index plan before enabling the new workers. The audit cursor uses
`source.environment`, `occurred_at`, `_id`; reference publication uses `published_at`,
`_id`. See [index maintenance](maintenance-and-verification.md) for the supported
inspection and application procedure.

Report recipients must have `sample:view` and matching current clinical scope.
Inbox reads check permission and scope again. Deleted or inaccessible sample links
hide their message text; unrelated announcements remain visible.

## System-error mail

The monitor retains jobs under `LOG_ROOT/.error-mail`. Delivery retries begin after
30 seconds and back off to at most one hour. Successfully accepted recipients are
not sent the same batch again. After 20 failed passes, metadata is renamed to
`.quarantined`; its diagnostic excerpt remains available for operator review.
Malformed metadata is also quarantined so it cannot block other messages.

Each scanned batch and attachment is limited to 1 MiB; message bodies are limited
to 64 KiB. An oversized log record produces a diagnostic notice and remains in the
original log rather than being copied into an unbounded attachment. The spool has
a 256 MiB admission budget, including quarantined evidence. At capacity the monitor
stops advancing scan offsets and logs an error. Restore delivery or archive reviewed
quarantined jobs before source-log retention removes unread records.

`status.json` records pending/quarantined counts, oldest retained excerpt age,
spool usage and capacity after delivery passes. Alert on growing age, any quarantine,
or capacity exhaustion. A stopped monitor cannot refresh this file; check its
timestamp and service health as well. Pending mail with no eligible recipients
remains on disk.

Before retrying a quarantined job, correct the relay/recipient fault and inspect its
metadata and excerpt using authorized diagnostic-log access. Stop the monitor while
recovering files. Keep `sent` recipient history, reset `attempts` and `next_attempt`,
and rename valid metadata from `.quarantined` to `.json`; then restart the monitor.
Never discard evidence merely to clear the status. SMTP acceptance followed by a
crash before persistence can still result in a duplicate email.

## Report-file erasure

Sample deletion commits an erasure job with its database changes. The worker checks
the configured root, original mount identity, ownership references and symlink-safe
path traversal before removing each artifact. Failures retain the job and record
`attempts`, `last_attempt` and one bounded `last_error` code:

| Code | Operator action |
| --- | --- |
| `storage_unavailable` | Restore the configured report volume. |
| `root_changed` | Reconcile the queued root against the intended deployment configuration. |
| `storage_identity_changed` | Reconcile the restored/replaced mount before authorizing further erasure. |
| `still_referenced` | Investigate another report referencing the artifact; preserve it while referenced. |
| `permission_denied` | Restore the application's intended storage permissions. |
| `invalid_path` | Investigate malformed or unexpected queued paths. |
| `io_error` | Inspect storage health and retry after repair. |

Application controls runtime data includes `report_erasure`: pending count, failed
pending count and oldest age in seconds, or `status=unavailable` when inspection
fails. Task results include the same counts. Logs contain reason codes and job IDs,
not report paths. Queue indexes cover route/last-attempt selection and route/creation
age. Successful jobs are acknowledged with an audit receipt.

Do not bypass root or reference guards after restoring storage. Follow
[transaction and erasure recovery](../architecture/transactions-and-ingest-recovery.md)
and verify the [audit checkpoint](audit-and-logging.md) as part of restore acceptance.

## Deep finding pages

Sorted pages beyond the first 1,000 rows use stable external merging in private
`coyote-table-*` temporary directories. Runs contain at most 1,000 rows and merge at
most 32 files at a time. The API retains the requested page rather than its entire
sorted prefix. Sorting preserves missing-last behavior, multi-column direction and
input order for ties. Complete export responses still retain their complete output.

Provision local temporary disk for concurrent deep queries. Files contain internal
clinical row data, are protected by owner-only directories, and are removed when a
request completes or raises an exception. A killed process may leave a directory;
remove abandoned directories only after confirming the owning process has stopped.
Disk exhaustion fails the request rather than returning an incomplete page.

A synthetic measurement on 22 October 2026 used 512-character annotation payloads,
97 tied sort values and the last 100-row page. Python allocation peaks measured with
`tracemalloc` were 1.6 MB for 10,000 rows and 4.6 MB for 100,000 rows, within an 8 MiB
budget for that fixture. These are allocation measurements, not container RSS or a
capacity guarantee for larger clinical row payloads or concurrent requests.
