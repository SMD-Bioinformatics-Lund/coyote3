# Operational troubleshooting

Use the symptom below to identify the failing component and its recovery procedure.
Keep the deployment's actual environment file and complete Compose overlay list in each command.

## Authentication Failures During Index Inspection or Maintenance

**Signature:**

- API startup reports an authorization failure while listing index metadata, or
  the maintenance command reports `createIndexes requires authentication`.

**Cause:**

- The API requires read access to inspect index definitions. The explicit
  maintenance command additionally requires index-management privileges.

**Resolution:**

1. Validate the selected private environment file to ensure the configured `COYOTE3_MONGO_URI` connection string contains the correct authentication credentials.
2. Confirm the runtime account can list collection indexes. Run `apply` with a
   separately controlled maintenance identity that can create indexes.
3. If connecting to a historical volume bootstrapped before authentication was
   enabled, initialize the required database identities through the documented
   first-deployment procedure. Do not grant the runtime account broad database
   administration solely to make index maintenance convenient.

## Configuration File Absence

**Signature:**

- Compose reports that the selected environment file does not exist.

**Resolution:**

For a new development environment, copy the template; for production use the
installation's private environment path. Retain existing files and secrets:

```bash
test -f .coyote3_dev_env || cp deploy/env/example.env .coyote3_dev_env
```

Review required secrets, database URIs and storage paths, then pass this exact file
with `--env-file` on every command.

## Python interpreter errors

**Signature:**

- Security or gate-checking bash scripts terminate reporting: `No module named pytest`.

**Resolution:**

Explicitly bind the execution command to the activated Python interpreter environment:

```bash
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/quality/run_family_coverage_gates.sh
```

## Pre-commit environment errors

**Signature:**

- Automated Git pre-commit hooks fail silently or explicitly broadcast `pytest not found`.

**Resolution:**

Use the tracked hook and the repository environment:

```bash
git config core.hooksPath .githooks
.venv/bin/python -m pre_commit run --all-files
```

See [engineering commands](../development/engineering-commands.md). Do not install a
second generated hook over the tracked one.

## API startup fails while connecting to Redis

`cache_backend_unavailable namespace=api reason=connection_failed` means the API
could not initialize its required Redis cache. The final wrapper error does not
distinguish authentication, DNS, TCP, and timeout failures.

Check the connection from the API container, not only the Redis health check.
Redis's container health check uses a local connection and can pass while traffic
between containers is blocked.

Source edits and repository quality checks do not deploy services or manage Docker
networks. Development source reloads run inside existing containers. Deployment
commands such as `compose up`, `run` and `down` change containers and can cause
Docker to update its own host networking rules, even with an external network.
Keep those operations separate from code verification on a shared host.
See Docker's [packet filtering and firewall documentation](https://docs.docker.com/engine/network/packet-filtering-firewalls/)
for the bridge networking rules managed by the daemon.

The installer requires a pre-provisioned external bridge and never creates or repairs
networks. Its diagnostics do not change host firewall rules, forwarding settings or
Docker daemon configuration. Host networking repairs require a separate administrator
operation after identifying the fault; restarting Docker affects other deployments.

The center installer starts Redis and checks all three configured Redis connections
from a temporary API container whenever the `start` stage is selected. This gate runs
before database bootstrap and index operations. Authentication and connection errors
stop installation without printing connection credentials.

To repeat the check independently after Redis is running:

```bash
bash scripts/deployment/compose-with-version.sh \
  --env-file "$COYOTE_ENV_FILE" -p "$COYOTE_PROJECT" \
  -f deploy/compose/docker-compose.yml \
  run --rm --no-deps -T api python3 -m scripts.deployment.installation_checks redis
```

| Observation | Next check |
| --- | --- |
| Authentication error | Compare the configured cache credentials with Redis's runtime credentials without printing either value. |
| Redis hostname does not resolve | Check that both services share the intended Compose network and Redis has the service alias. |
| TCP connection is refused | Check Redis's listener and whether it has completed startup. |
| TCP times out between containers, but succeeds from the host | Inspect bridge forwarding and host firewall rules. A healthy local Redis check does not establish container reachability. |

For a Docker host using iptables, an administrator can inspect the relevant rules
without changing them:

```bash
sudo iptables -S FORWARD
sudo iptables -S DOCKER-USER
sudo iptables -S DOCKER-FORWARD
sudo iptables -S DOCKER
```

Chain names depend on the Docker version and firewall backend; an absent chain
alone does not identify the fault. Inspect the equivalent rules when the host
uses another backend. Restore forwarding only for the intended application
network after identifying the blocking rule. Do not flush the host firewall or
disable the required cache to work around a network failure.

After repairing connectivity, verify an authenticated Redis PING from the API
container, then restart the affected application service and check its health.
This failure does not require a MongoDB migration or data repair.

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
maintenance therefore does not repair dashboard cache state. Redis restarts can
retain cached values when persistence is enabled. Check expiration and refresh
execution rather than assuming a restart clears the cache.

## Mongo Index Conflicts

**Signature:**

- API startup continues, but logs include `Mongo index conflict for repository=<name> was tolerated at startup`.
- MongoDB reports `IndexOptionsConflict` (`85`) or `IndexKeySpecsConflict` (`86`) during repository index creation.

**Cause:**

- The collection already contains an index with the same name and different options, or the same key pattern under a different name.
- This usually happens after a schema/index contract change against an existing database volume.

**Diagnostic Commands:**

Run the index contract inspector from the repository root. It reads the same
MongoDB configuration as the API and does not modify the database.

```bash
PYTHONPATH=. python3 scripts/database/manage_mongo_indexes.py status
PYTHONPATH=. python3 scripts/database/manage_mongo_indexes.py plan
```

`status` includes every managed repository, session, audit, and
application-control index. `plan` returns only missing definitions and
conflicts. A conflict means the name exists with a different key order or a
behavior-changing option such as uniqueness, sparsity, TTL expiry, or a partial
filter.

**Resolution:**

1. Preserve the `status` output as operational evidence and confirm the
   conflicting index is not required by the deployed release.
2. Schedule a maintenance window when writes to the affected collection are paused.
3. Retire only the exact stale index. Repeating the name is an intentional guard:

   ```bash
   PYTHONPATH=. python3 scripts/database/manage_mongo_indexes.py retire \
     --collection <collection> \
     --index <stale_index_name> \
     --confirm-index-name <stale_index_name>
   ```

4. Apply missing contracts without dropping any other index:

   ```bash
   PYTHONPATH=. python3 scripts/database/manage_mongo_indexes.py apply
   ```

5. Run `status` again and confirm every required contract is `present`.

> **Warning: Index maintenance safety**
>
>
> Normal API startup never retires indexes. Do not drop all indexes from
> clinical collections. Retire only the exact index identified by `plan`,
> after checking the release contract and current query usage.
