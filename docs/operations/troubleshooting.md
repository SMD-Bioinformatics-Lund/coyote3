# Operational Troubleshooting & Remediation

This section outlines standard diagnostic signatures and remediation protocols for known operational deployment states and container lifecycle initialization faults.

## Authentication Failures During Index Inspection or Maintenance

**Signature:**

- API startup reports an authorization failure while listing index metadata, or
  the maintenance command reports `createIndexes requires authentication`.

**Diagnostic Cause:**

- The API requires read access to inspect index definitions. The explicit
  maintenance command additionally requires index-management privileges.

**Remediation Protocol:**

1. Validate the local `.coyote3_env` file to ensure the configured `MONGO_URI` connection string contains the correct authentication payload (username and password).
2. Confirm the runtime account can list collection indexes. Run `apply` with a
   separately controlled maintenance identity that can create indexes.
3. If connecting to a historical volume bootstrapped before authentication was
   enabled, initialize the required database identities through the documented
   first-deployment procedure. Do not grant the runtime account broad database
   administration solely to make index maintenance convenient.

## Configuration File Absence

**Signature:**

- The Docker Compose execution faults sequentially with the output: `.coyote3_env not found`.

**Remediation Protocol:**

Initialize the environment file from the canonical template in the repository:

```bash
cp deploy/env/example.env .coyote3_env
```

Ensure all explicit cryptographic secrets and API token parameters are manually populated within the file before re-initiating the compose commands.

## Sub-Process Interpreter Faults

**Signature:**

- Security or gate-checking bash scripts terminate reporting: `No module named pytest`.

**Remediation Protocol:**

Explicitly bind the execution command to the activated Python interpreter environment:

```bash
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

## Pre-Commit Framework Isolation Faults

**Signature:**

- Automated Git pre-commit hooks fail silently or explicitly broadcast `pytest not found`.

**Remediation Protocol:**

- Configure all local hook execution blocks to point strictly to the active `venv` environment executable explicitly, rather than relying on global system `PATH` resolution.
- Force a complete framework re-execution manually:

```bash
python -m pre_commit run --all-files
```

## Dashboard Metrics Do Not Refresh

**Signature:**

- A dashboard section remains marked stale after its source data changes.
- Selecting **Refresh metrics** does not produce a newer metric timestamp.

**Checks:**

1. Confirm Redis, the Celery worker, and Celery Beat are healthy.
2. Check worker logs for `api.tasks.maintenance.refresh_dashboard_metrics`.
3. Verify `DASHBOARD_METRIC_CACHE_TTL_SECONDS` and
   `DASHBOARD_METRIC_CACHE_RETENTION_SECONDS` are positive integers, with
   retention greater than or equal to freshness.
4. Request the affected `/api/v1/dashboard/metrics/...` endpoint directly and
   inspect `metric_meta.generated_at` and `metric_meta.stale`.

Dashboard metrics are held in Redis, not in a MongoDB collection. MongoDB index
maintenance therefore does not repair dashboard cache state. Restarting Redis
clears cached values; the next request or scheduled refresh rebuilds them from
the authoritative collections.

## Mongo Index Conflicts

**Signature:**

- API startup continues, but logs include `Mongo index conflict for repository=<name> was tolerated at startup`.
- MongoDB reports `IndexOptionsConflict` (`85`) or `IndexKeySpecsConflict` (`86`) during repository index creation.

**Diagnostic Cause:**

- The collection already contains an index with the same name and different options, or the same key pattern under a different name.
- This usually happens after a schema/index contract change against an existing database volume.

**Diagnostic Commands:**

Run the index contract inspector from the repository root. It reads the same
MongoDB configuration as the API and does not modify the database.

```bash
PYTHONPATH=. python3 scripts/manage_mongo_indexes.py status
PYTHONPATH=. python3 scripts/manage_mongo_indexes.py plan
```

`status` includes every managed repository, session, audit, and
application-control index. `plan` returns only missing definitions and
conflicts. A conflict means the name exists with a different key order or a
behavior-changing option such as uniqueness, sparsity, TTL expiry, or a partial
filter.

**Remediation Protocol:**

1. Preserve the `status` output as operational evidence and confirm the
   conflicting index is not required by the deployed release.
2. Schedule a maintenance window when writes to the affected collection are paused.
3. Retire only the exact stale index. Repeating the name is an intentional guard:

   ```bash
   PYTHONPATH=. python3 scripts/manage_mongo_indexes.py retire \
     --collection <collection> \
     --index <stale_index_name> \
     --confirm-index-name <stale_index_name>
   ```

4. Apply missing contracts without dropping any other index:

   ```bash
   PYTHONPATH=. python3 scripts/manage_mongo_indexes.py apply
   ```

5. Run `status` again and confirm every required contract is `present`.

> **Warning: Index maintenance safety**
>
>
> Normal API startup never retires indexes. Do not drop all indexes from
> clinical collections. Retire only the exact index identified by `plan`,
> after checking the release contract and current query usage.
