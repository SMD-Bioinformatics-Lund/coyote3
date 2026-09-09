# Load and capacity testing

Locust exercises Coyote3 over HTTP using synthetic users and records. Run it against
an isolated deployment through Nginx, including the application's URL prefix. It
does not connect directly to MongoDB, Redis, or external knowledgebase services.

The generator is optional and separate from the API runtime. Its Python dependency
is pinned in `requirements-load.txt`; its Compose service is enabled only by the
`loadtest` profile in `deploy/compose/docker-compose.loadtest.yml`.

## Prepare the target

> **Warning:** Never point this suite at a production deployment or a database
> containing clinical records. Nonproduction naming alone does not establish isolation.

Start with the [disposable deployment procedure](disposable_full_stack_validation.md).
Use dedicated application, identity, and BAM databases, Redis queues and cache,
storage, and local test accounts. Disable or mock external knowledgebase requests,
SMTP, and other outbound integrations. A shared knowledgebase may be read-only,
but its capacity must be included in the test plan and approved by its operator.

The generator checks `/api/v1/public/about` before authenticating each virtual user.
The environment, URL prefix, and three mutable database names must match the
configuration exactly. Production and unrecognized environments are rejected.
These checks cannot establish whether the target's storage or database contents
are synthetic; the operator must verify that separately.

Use the same TLS and proxy setup as the intended deployment. Certificate validation
is enabled. For a private CA, supply `ca_bundle` in the configuration; there is no
insecure TLS option. Redirects are rejected instead of forwarding credentials to a
different URL. HTTP is intended only for an isolated local test network.

## Configure the generator

Run from the repository root:

```bash
mkdir -p .coyote3_load load-results
chmod 700 .coyote3_load load-results
cp tests/load/config.example.json .coyote3_load/config.json
cp tests/load/fixtures.example.json .coyote3_load/fixtures.example.json
```

Edit the private configuration and replace example identifiers with records from
the synthetic deployment. Example finding and rule-version identifiers are
placeholders, not bootstrap records guaranteed to exist.

| Configuration | Meaning |
| --- | --- |
| `target_url` | Exact public base URL, including `SCRIPT_NAME`, without `/api/v1`. |
| `environment` | Exact nonproduction environment returned by the target. |
| `databases` | Exact `primary`, `identity`, and `bam_service` database names. |
| `synthetic_data` | Must be `true`: the operator has verified synthetic target data. |
| `external_lookups_disabled` | Must be `true`: outbound integrations are disabled or mocked. |
| `fixtures_file` | Synthetic fixture JSON path, relative to the configuration file. |
| `allow_writes` | Defaults to `false`; required for comments and ingest. |
| `ca_bundle` | Optional trusted PEM CA path, relative to the configuration file. |
| `request_timeout_seconds` | HTTP request timeout; default 10 seconds. |
| `think_time_seconds` | Minimum and maximum delay between workflows; default `[1, 3]`. |
| `poll_interval_seconds` | Ingest status interval; default 1 second. |
| `poll_timeout_seconds` | Overall ingest polling budget; default 60 seconds. |
| `max_poll_attempts` | Maximum status requests per ingest; default 60. |

Create `.coyote3_load/credentials.json` privately with this structure, supplying a
password set only on the synthetic target:

```json
{
  "accounts": [
    {
      "username": "synthetic.reviewer",
      "password": "REPLACE_WITH_TEST_ACCOUNT_PASSWORD",
      "provider": "local",
      "workflows": ["browsing", "findings", "dashboard"]
    }
  ]
}
```

```bash
chmod 600 .coyote3_load/*.json
```

Each virtual user has its own cookie session, logs in once, sends `X-CSRF-Token`
where applicable, and logs out when it stops. Accounts are assigned in rotation.
Provide enough separate accounts to represent concurrent users without accidentally
benchmarking per-account session limits. Use existing roles and permissions; denied
requests count as failures rather than being skipped. LDAP credentials are not supported.

Only explicit fixture identifiers are used for detail requests. List responses do
not become a source of further sample IDs. Use separate personas for ordinary
reviewers and privileged workflows. The fixture manifest is versioned independently
of application records and is validated before requests begin.

### Workflows and fixtures

| Workflow | Requests | Required fixtures |
| --- | --- | --- |
| `browsing` | Search the sample list for a configured synthetic sample. | `samples[].sample_id` |
| `findings` | Read small-variant list and one explicit variant detail. | Sample IDs and nonempty `finding_ids` per sample. |
| `dashboard` | Read the sample dashboard metric. | None. |
| `genes` | Read gene information. | `gene_symbols` |
| `reports` | Read the saved-report list. | None; target contains synthetic reports only. |
| `report_preview` | Render a sample's report preview without saving. | Sample IDs and `report_type` (`dna` or `rna`). |
| `rule_testing` | Evaluate one rule version against its configured sample without saving. | `rule_tests[]` pairs of `sample_id` and `rule_version_id`. |
| `comments` | Add a fixed synthetic sample comment. | Sample IDs; `allow_writes: true`. |
| `ingest` | Submit a unique synthetic sample with biomarker input and await terminal status. | `ingest_sample_template`; `allow_writes: true`; synthetic file mounted on the target. |

The default persona selects `browsing`, `findings`, and `dashboard`. Selection is
weighted: browsing and findings each have weight 5, dashboard and genes each 2,
and the other workflows each 1. Weights apply only within that account's selected
workflows. For distinct workload proportions, use separate accounts with a single
workflow and control their count.

Rule-test pairs must belong to matching assays and subpanels. Ingest requires a
dedicated synthetic ASP with `expected_files: ["biomarkers"]` and
`required_files: ["biomarkers"]`, and a matching ASPC with
`analysis_types: ["BIOMARKER"]`. The bootstrap `assay_1`
requires VCF input and cannot run this biomarker-only workload.
Create the synthetic configuration through the normal admin workflow; the generator
does not create or weaken assay requirements. The sample's environment
is an assay-configuration scope, separate from the server's runtime environment;
its value must match that synthetic ASPC. Ingest generates unique `load_` sample
and case names and never requests replacement of existing data. Comments and
ingested samples remain in the disposable target until operator cleanup.

The example uses `asp_id: load_assay`, sample environment `testing`, and the fixed
input `/load/synthetic/biomarkers.json`. The tiny source file is supplied under
`tests/load/synthetic/`. The suite rejects other ingest file paths, rather than
allowing a fixture to name clinical files. For Docker targets, add this to the
disposable application's private Compose storage override, not the generator's
Compose file:

```yaml
services:
  api:
    volumes:
      - type: bind
        source: ${COYOTE3_LOAD_SYNTHETIC_ROOT:?Set the synthetic fixture directory}
        target: /load/synthetic
        read_only: true
        bind:
          create_host_path: false
  worker:
    volumes:
      - type: bind
        source: ${COYOTE3_LOAD_SYNTHETIC_ROOT:?Set the synthetic fixture directory}
        target: /load/synthetic
        read_only: true
        bind:
          create_host_path: false
```

Run `export COYOTE3_LOAD_SYNTHETIC_ROOT="$PWD/tests/load/synthetic"` before recreating
the disposable API and worker with that override. Both services must be able to
read the file at its container path. This variable is used only by the example
override. The generator sends JSON; it does not upload the file or configure mounts.
For a non-container target, provision the same synthetic file at the fixed path.
Read-only workloads do not need this mount or an ingest assay.

The supplied scenarios do not cover every endpoint or every modality. CNV, fusion,
translocation, coverage, PDF rendering, and large input files need dedicated
workloads before claiming performance coverage for those features.

## Run locally

Use a separate virtual environment. Locust's networking runtime must not be added
to the API's interpreter or imported into backend pytest collection.

```bash
.venv/bin/python -m venv .venv-load
.venv-load/bin/python -m pip install -r requirements-load.txt
.venv-load/bin/python tests/load/smoke_test.py
export COYOTE3_LOAD_CONFIG="$PWD/.coyote3_load/config.json"
export COYOTE3_LOAD_CREDENTIALS="$PWD/.coyote3_load/credentials.json"
.venv-load/bin/locust -f tests/load/locustfile.py --web-host 127.0.0.1
```

Open `http://127.0.0.1:8089`. Start with one user and verify every workflow before
increasing concurrency. The web UI's host field must agree with the pinned URL.

For a bounded run, after validating the target and permissions:

```bash
.venv-load/bin/locust -f tests/load/locustfile.py --headless --users 5 --spawn-rate 1 --run-time 2m --stop-timeout 15 --csv load-results/run --csv-full-history --html load-results/report.html
```

This is an initial exercise, not a recommended production capacity or acceptance
threshold. Choose a new output prefix for every run so evidence is not overwritten.

## Run with Docker

The standalone Compose file starts only the generator. It does not start or modify
the target application's databases, workers, or proxy. Set the network to the
existing isolated application's network and make the private `target_url`
resolvable from inside the generator container. Container `localhost` is not the host.

```bash
export COYOTE3_LOAD_NETWORK=coyote3-loadtest-net
export COYOTE3_LOAD_UID="$(id -u)"
export COYOTE3_LOAD_GID="$(id -g)"
docker compose --env-file deploy/env/example.loadtest.env -f deploy/compose/docker-compose.loadtest.yml --profile loadtest config --quiet
docker compose --env-file deploy/env/example.loadtest.env -f deploy/compose/docker-compose.loadtest.yml --profile loadtest up loadtest
```

Replace the example network with the target's actual isolated network before running.
The service publishes its UI only on `127.0.0.1:8089`. It mounts the test code and
private configuration read-only and writes results to `load-results/`. UID/GID must
match the owner of those host directories. Custom CA files must be inside the mounted
private directory when using Compose. No application environment file or database
credentials are passed to Locust.

### Load-generator environment reference

`deploy/env/example.loadtest.env` configures the standalone generator, not the
application. Every setting below is consumed by `docker-compose.loadtest.yml`.

| Variable | Default | Purpose |
| --- | --- | --- |
| `COYOTE3_LOAD_NETWORK` | `coyote3-loadtest-net` | Existing isolated target network to join; Compose does not create it. |
| `COYOTE3_LOAD_PORT` | `8089` | Host web-UI port, bound to loopback only. |
| `COYOTE3_LOAD_UID` | `1000` | Container UID; match the private input and output directory owner. |
| `COYOTE3_LOAD_GID` | `1000` | Container GID for directory access. |
| `COYOTE3_LOAD_PRIVATE_DIR` | `../../.coyote3_load` | Read-only configuration and credential directory. Relative paths resolve from `deploy/compose`. |
| `COYOTE3_LOAD_RESULTS_DIR` | `../../load-results` | Writable results directory; relative paths resolve from `deploy/compose`. |
| `COYOTE3_LOAD_MEM_LIMIT` | `512m` | Container memory limit. |
| `COYOTE3_LOAD_CPU_LIMIT` | `1.0` | Container CPU limit. |

Create both directories before starting the generator. Targets, synthetic-account
credentials, workload choices, and acceptance limits belong in its private JSON
configuration, not these deployment variables.

```bash
docker compose --env-file deploy/env/example.loadtest.env -f deploy/compose/docker-compose.loadtest.yml --profile loadtest down
```

Stopping the generator does not cancel already queued ingest jobs or remove test data.
Wait for workers to finish before tearing down the disposable target.

## Interpret results

Record the application commit, configuration, synthetic dataset size, index state,
worker concurrency, database topology, hardware, and scenario mix with each run.
Measure cold-cache and warmed-cache runs separately; clear only the disposable
environment's cache when preparing a cold-cache run.

Track p50, p95, p99, throughput, concurrency, error rate, and HTTP 429 responses.
Correlate them with API CPU and memory, MongoDB query latency and connection pools,
Redis latency, worker utilization, and queue depth. A saturated generator is not
evidence that the API has reached capacity.

HTTP 202 records submission acceptance only. The ingest workflow polls a fixed
task-status route with bounded attempts and time, validates the terminal result,
and records `WORKFLOW ingest/terminal` separately. A Celery `SUCCESS` containing
a failed application result is a failure. This small synthetic biomarker ingest
exercises dispatch, parsing, and persistence; it does not measure VCF parsing, archive extraction,
coverage imports, or large-file throughput.

Request names use route templates rather than sample IDs. Reports and logs remain
private operational artifacts and must not be committed. Keep unexpected HTTP
statuses, malformed JSON, authorization failures, and rate limiting visible; do not
raise production limits to hide failures in the test.

Define performance thresholds before the run from expected center workloads.
Locust's error exit status is not a latency service-level objective. A passing
synthetic smoke test proves the generator can run, not that Coyote3 has passed
capacity, recovery, browser, security, or clinical acceptance.

## Maintenance and verification

Pure configuration and workflow tests live in `tests/unit/test_load_testing.py`.
Compose isolation is checked by `tests/unit/test_loadtest_compose.py`. The separate
CI smoke job installs only `requirements-load.txt` and runs the actual Locust process
against a temporary synthetic HTTP server, without application credentials or MongoDB.

Keep request paths and response assertions aligned with API contracts. Add tests
for new workflows, including denied permissions and application failures returned
with HTTP 200. Never add publication, retirement, report finalization, or deletion
to a capacity loop without a separate reviewed test design.

See [testing and quality](testing_and_quality.md),
[observability](../operations/observability_slos_and_alerts.md), and
[release readiness](../operations/release_readiness.md) for related checks.
Locust documents [HTTP workflows](https://docs.locust.io/en/stable/writing-a-locustfile.html),
[command-line options](https://docs.locust.io/en/stable/configuration.html), and
[distributed execution](https://docs.locust.io/en/stable/running-distributed.html).
For multiple generators, provision every worker with the same reviewed target and
fixtures and partition test accounts; the supplied Compose file runs one generator.
