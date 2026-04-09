# Operational Troubleshooting & Remediation

This section outlines standard diagnostic signatures and remediation protocols for known operational deployment states and container lifecycle initialization faults.

## Authentication Failures During Index Provisioning

**Signature:**
- Process initialization halts unconditionally during the `ensure_indexes` procedure.
- Output logs broadcast `createIndexes requires authentication`.

**Diagnostic Cause:**
- The backend application component attempted execution against the persistent MongoDB instance without valid mapped credentials.

**Remediation Protocol:**

1. Validate the local `.coyote3_env` file to ensure the configured `MONGO_URI` connection string contains the correct authentication payload (username and password).
2. Confirm the specified application username possesses active administrative privileges within the targeted database volume.
3. If connecting to a legacy volume bootstrapped prior to authentication enforcement policies, administrators must initialize the target user manually or perform a clean container volume re-initialization.

## Configuration File Absence

**Signature:**
- The Docker Compose execution faults sequentially with the output: `.coyote3_env not found`.

**Remediation Protocol:**

Initialize the environment definition file from the authoritative templates provided in the deployment artifact repository:

```bash
cp deploy/env/example.prod.env .coyote3_env
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

## Unbounded Collection Growth Metrics

**Signature:**
- Storage analytics indicate the `dashboard_metrics` target collection expands perpetually without data reduction.

**Diagnostic Protocol:**

1. Verify the `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` configuration metric defines a valid positive integer payload.
2. Confirm the existence of the targeted TTL index by executing the following administrative command against the database:

```javascript
db.dashboard_metrics.getIndexes().filter(i => i.name === "updated_at_ttl_1")
```

3. Ensure standard snapshot write transactions are actively appending the `updated_at` temporal field.
4. Note that internal MongoDB TTL garbage collection routines execute asynchronously and lack strictly real-time millisecond guarantees.

**Remediation Protocol:**

- If the required TTL index is absent from the metrics query, forcibly restart the primary API container. The initial synchronization protocol will automatically provision missing indexes.
- If storage policies require extended or limited retention periods, modify the `DASHBOARD_SUMMARY_SNAPSHOT_TTL_SECONDS` deployment configuration value accordingly.
