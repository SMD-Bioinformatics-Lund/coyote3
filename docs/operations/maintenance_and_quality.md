# Operational Maintenance and Quality Verification

**Last reviewed:** 10 August 2026.

This document lists the routine checks for code quality, seed integrity, and environment validation.

## Pre-Release Quality Check

Run the contract and logic checks before pushing changes.

```bash
# Run project-wide integrity verification
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

For the complete cross-layer source/build gate, use:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/run_quality_suite.sh
```

The full gate is deliberately read-only with respect to MongoDB. Run the
[Browser And Release Validation](../testing/browser_and_release_validation.md)
procedure separately with controlled fixtures before promoting a release.

Checks covered:

- import integrity
- removal of stray `print()` calls in runtime code
- logging and error-message checks
- seed and contract consistency
- documentation build checks

## Seed Consistency

Validate seed data and cross-collection assay relationships before using them.

```bash
# Validate core seed structures and assay relations
.venv/bin/python scripts/validate_assay_consistency.py \
  --seed-file api/config/bootstrap/demo_center \
  --reference-seed-data api/config/bootstrap/rbac \
  --reference-seed-data api/config/bootstrap/reference \
  --validate-all-contracts
```

## Database Bootstrap Command

Example staging command:

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB" \
  --username "admin.coyote3" \
  --email "admin@coyote3.local" \
  --password "ENFORCED_SECRET"
```

## Audit and Logging

### Logging Integrity

Use structured logging:

- add operation-specific metadata
- keep exception traces with `exc_info=True`
- do not use stdout `print()` for runtime telemetry

### Audit Metadata Persistence

Documents created through administrative or clinical actions must keep an audit trail:

- `created_by` / `updated_by`: Explicit identity of the originating user.
- `created_on` / `updated_on`: Standardized UTC (ISO-8601) timestamps.

### Runtime and Retention Verification

Application Controls exposes both configured controls and observed Celery state.
For a maintenance validation run:

1. Record the pre-run audit-event and log-file state.
2. Queue maintenance from **Admin > Application Controls**.
3. Keep the returned task id and check its state through the internal task
   status endpoint as an authorized operator.
4. Confirm the task outcome in worker logs and inspect configured retention
   effects in the test environment.
5. Preserve the corresponding audit-event identifiers in release evidence.

Do not test destructive retention cleanup against production evidence stores.

### Public OncoKB reference refresh

**Admin > Application Controls > Refresh public OncoKB** queues a separate
maintenance task. It reads all local `hgnc_genes` records, uses approved, previous, and alias
symbols to resolve public records, fetches the public cancer-gene and
curated-gene catalogues once each, and reconciles
`oncokb_cancer_genes_public` and `oncokb_genes_public`.

The maintenance task is subject to the current operational controls. An empty
HGNC catalogue or an upstream OncoKB failure marks the task failed and emits an
audit event; existing cache data is not cleared.

## MongoDB Index Lifecycle

MongoDB indexes are declared by repository and security contracts in the API.
The API performs a read-only comparison during process initialization and
reports missing or conflicting definitions through logs and observed runtime
state. Startup does not create, rebuild, rename, or drop an index. Operators
provision reviewed contracts with the explicit `apply` command.

Index creation can be expensive only when a required index is genuinely absent,
especially on large SNV, CNV, fusion, annotation, and transcript collections.
Build new large indexes during a controlled maintenance window and monitor
MongoDB disk, CPU, memory, replication lag, and temporary storage.

MongoDB treats a matching `createIndex` request from the maintenance command as
idempotent: an existing matching index is reused and its collection is not
rebuilt or rescanned.

| Command | Database effect | Intended use |
| --- | --- | --- |
| `status` | Read only | Show every required contract, current state, and known obsolete indexes. |
| `plan` | Read only | Show only missing or conflicting contracts. |
| `apply` | Creates missing compatible indexes | Provision a reviewed release contract; never drops indexes. |
| `retire` | Drops one exact confirmed index | Remove an obsolete definition during a maintenance window. |

```bash
PYTHONPATH=. python3 scripts/manage_mongo_indexes.py status
PYTHONPATH=. python3 scripts/manage_mongo_indexes.py plan
PYTHONPATH=. python3 scripts/manage_mongo_indexes.py apply
```

The retirement command requires the collection name, index name, and a second
exact confirmation of the index name. This makes retirement a deliberate
operation rather than an API-startup side effect. Preserve before-and-after
command output with the release or maintenance evidence.

## MongoDB client sizing and durability

Each API and Celery process owns a PyMongo connection pool. The upper-bound
connection estimate is therefore the configured maximum pool size multiplied
by the number of API workers and Celery processes; it is not one shared pool
for the deployment. Start with the documented defaults, compare that estimate
with the replica set's connection capacity, and tune only from measured queue
waits and database utilization.

Production defaults use `majority` read concern, `majority` write concern, and
journal acknowledgement. These settings favor acknowledged clinical writes
over the lower latency of primary-only acknowledgement. Changing them requires
a documented database-operator review and recovery test.

### Capacity Baseline

Capture a read-only capacity snapshot before a release, a large ingest change,
or a planned index build. The command reads collection counts, storage/index
sizes, and index names. It never reads clinical documents, changes indexes, or
writes to MongoDB.

```bash
# Record all configured primary-database collections.
PYTHONPATH=. python3 scripts/inspect_mongo_capacity.py \
  --output maintenance/mongo_capacity_$(date +%F).json

# Investigate only high-volume collections.
PYTHONPATH=. python3 scripts/inspect_mongo_capacity.py \
  --collection variants \
  --collection anno_vep \
  --collection annotations
```

Use the resulting JSON as maintenance evidence and compare it with the prior
snapshot. It is a capacity inventory, not a synthetic benchmark: latency
changes still need to be assessed against an approved non-production workload.

## Integrated Operational Assets

Use these related documents for detailed procedures:

- [Initial Deployment Checklist](initial_deployment_checklist.md)
- [Center Deployment Guide](center_deployment_guide.md)
- [Quality Engineering and Validation Standards](../testing/testing_and_quality.md)
- [Browser And Release Validation](../testing/browser_and_release_validation.md)
- [Collection Contract Reference](../api/collection_contracts.md)
