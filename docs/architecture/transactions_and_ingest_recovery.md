# Transactions and ingest recovery

## Persistence boundaries

Coyote3 requires a MongoDB replica set or sharded cluster. A one-member replica
set supports transactions but does not provide failover. All repositories joining
a transaction must use the same MongoClient and deployment, including repositories
bound to different databases.

| Operation | Consistency boundary |
| --- | --- |
| Single-document updates and job lease claims | MongoDB atomic conditional writes. |
| Sample creation and update | Sample metadata, declared dependent evidence, readiness, and async completion receipt commit together. |
| Sample deletion | Sample anchor, findings, quality data, comments, report metadata, and reported finding snapshots are removed together. Shared annotations, references, audit records, and report files are retained. |
| Report save | Sample report state, report metadata, and finding snapshots commit together. Files remain outside MongoDB. |
| Configuration revision rotation | Retiring the active revision and inserting its successor commit together. |
| Clinical rules and public catalog governance | Related lifecycle records and revision/history changes share the existing repository transaction. |
| Repository batch mutations | Bulk annotation, flag, notification, evidence, and retention writes use a transaction; session-aware helpers join the caller's transaction. |
| OncoKB public marker refresh | Both marker products are upserted and pruned in one transaction after successful retrieval and validation. |
| File access, HTTP retrieval, Redis, index management, collection rename/import administration | Not covered by a MongoDB document transaction. Use their explicit validation and recovery procedures. |

`api/infra/mongo/transactions.py` owns the required transaction helper. It uses
snapshot reads, primary routing, and journaled majority writes. Session setup or
transaction failure never falls back to ordinary writes. The driver can retry the
callback: it must contain database work only, with stable identities. Do not put
file writes, broker publication, remote requests, or notifications inside it.

Return values must come from the committed callback attempt, not mutable state
retained across attempts. Clinical-rule publication returns that attempt's updated
candidate, or `None` if no approved candidate matches; an aborted attempt's candidate
is not a published result. Sibling deactivation and revision snapshots share the commit.

Parsing and validation precede sample transactions. Updates compare the sample
with the version read during preparation and reject intervening changes. The
sample anchor is written before evidence replacement, providing a conflict point
for concurrent ingest, deletion, and report workflows. Cache invalidation follows
commit and is not evidence of database success or failure.

Transactions do not make arbitrarily large batches inexpensive. Measure the
largest supported assay against the deployment's transaction lifetime, memory,
and storage limits before rollout. A timeout must abort the operation; do not
split a clinically related mutation into independently visible commits to bypass it.

## Durable ingest jobs

The primary database's `ingest_jobs` collection holds delivery state for async
sample bundles, collection insert/bulk/upsert requests, and watched manifests.
Acceptance is recorded with journaled majority write concern before Celery is
notified. Celery messages contain the job identifier rather than the clinical
payload. Broker failure after acceptance leaves recoverable pending work.

| State | Meaning and recovery |
| --- | --- |
| `pending` | Accepted but not claimed; beat attempts delivery every 30 seconds. |
| `running` | A worker holds a tokenized lease. Its expiry exceeds the task hard limit; expired work is eligible for redelivery. |
| `succeeded` | Data and completion receipt committed together. Redelivery returns the original result without repeating writes. |
| `failed` | A non-retryable validation or write failure. Investigate and submit corrected input as a new job; beat does not retry this state. |

Lease tokens fence stale workers. A worker cannot commit evidence if its receipt
no longer owns the lease. Transient connection/transaction failures return work
to pending; an ambiguous acknowledgement is checked against the stored receipt.
The failure update cannot overwrite a committed success. Disabled ingest families
retain their pending work until enabled. Beat dispatches at most 100 eligible jobs
per scan; worker concurrency controls execution, not this batch size.

Task status uses the MongoDB receipt for these jobs. Existing endpoint permission
checks still apply; only the submitter or a superuser can inspect the job. Responses
exclude source payloads, staging paths, and lease tokens. Other operational Celery
tasks continue to use their task backend.

Upload staging is removed only after confirmed success. Failed jobs retain source
payloads and staging files for investigation. Successful receipts clear the payload
but retain identity and result. There is no automatic receipt TTL: deleting a
receipt removes its replay protection. Treat this collection and retained files as
sensitive application data, not public metadata. Apply center retention and backup
policy; do not delete records or staging for pending/running jobs.

Watched manifests derive a stable job identifier from their absolute path,
modification time, and bytes. A failed acknowledgement rename does not undo a
committed ingest. A subsequent scan can return its receipt and retry the marker.
Only successful processing produces a completion marker and success audit event.
If the ingest family is disabled during a scan, the job and unchanged manifest remain
available for later processing, without a `.done` acknowledgement. Busy jobs likewise
remain unacknowledged; non-retryable failures use the failure marker.
Producers must publish complete manifests atomically and leave them unchanged
until acknowledgement; an edited/replaced manifest represents a new submission.

## Deployment and rollout

1. Configure an initialized replica set with a writable primary, reachable from
   API and workers. See [MongoDB deployment](../operations/mongodb_deployment_and_recovery.md).
2. Include `ingest_jobs_collection = "ingest_jobs"` under `[primary]` in the center
   collection map. Custom maps are complete mappings, not partial overlays of defaults.
3. Apply the repository index plan with `scripts/manage_mongo_indexes.py` using
   the configured deployment environment. The ledger requires `pending_delivery`;
   startup verification does not substitute for applying indexes.
4. Quiesce producers and drain previously queued ingest tasks with their matching
   worker version before rollout. The current task contract accepts `job_id`, not
   embedded source payloads. Do not run mixed worker protocols on the same queue.
5. Preserve the Compose `redis-data` volume and ingest staging mounts. Redis uses
   AOF, `appendfsync always`, and `noeviction`; cache, broker, and results use logical
   databases 0, 1, and 2. Drain any old broker database before changing its URL.
6. Run worker and beat services. Confirm pending jobs progress and poll final
   receipts before considering accepted submissions complete.

Logical Redis databases share one process and memory budget; this is isolation of
keys, not high availability. A full Redis instance rejects writes instead of
evicting queued work. MongoDB retains accepted ingest jobs for redispatch, but
MongoDB and staged files still need backups. Do not remove volumes as a cache reset.

For [load testing](../testing/load_testing.md), measure submission latency separately
from receipt completion and backlog drain. Use a separate Redis instance and storage;
never reset a shared broker to create a cold-cache phase.

## Report artifact reconciliation

MongoDB cannot atomically commit files with report records. Report persistence
retains artifacts when commit acknowledgement is uncertain. Inspect discrepancies
without changing records or files:

```bash
PYTHONPATH=. .venv/bin/python scripts/inspect_report_artifacts.py \
  --database "$APPLICATION_DATABASE" --reports-root "$REPORTS_ROOT"
```

The script reads `COYOTE3_MONGO_URI` from the environment, supports
`--reports-collection`, and prints counts by default. `--details` includes local
report identifiers and relative paths and must be handled as sensitive output.
Use the same report root mount/path representation as the report-writing service.

| Result | Operator action |
| --- | --- |
| `missing` | Investigate inaccessible mounts or absent referenced HTML/PDF files; restore verified artifacts through the center's recovery procedure. |
| `outside_root` | Investigate an invalid persisted path; the script does not read the external file. |
| `unreferenced` | Review against retention policy and uncertain commits before any manual cleanup. Sample deletion deliberately retains report files, so this is not proof of an orphan that may be deleted. |

Unreferenced files newer than 24 hours are excluded by default; adjust with
`--minimum-age-hours`. Exit status is 1 for missing/outside-root references and 0
otherwise. This is an inspection aid, not a restore command or a crash-recovery
acceptance test. Run during a quiet period to reduce concurrent filesystem changes.
