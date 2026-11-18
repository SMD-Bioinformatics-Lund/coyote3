# Browser And Release Validation

This procedure verifies the user-visible behavior that unit and API tests cannot
fully establish: browser rendering, routing, asynchronous state, persisted data,
and generated clinical artifacts. Automated browser tests use synthetic fixtures
or newly created local containers. They must never target a production database
or an existing deployment, even when the submitted records are synthetic.

## Validation Boundary

Automated backend tests validate contracts, permissions, business logic, and
route declarations. The frontend route registry is checked against the FastAPI
route table and every React Router path is required to have a route contract.
Playwright exercises complete browser workflows with deterministic API
fixtures. These workflows cover authentication, analysis-tab request gating,
dashboard composition, sample-list state, module availability, public matrix
search, profile persistence, and administrative notification broadcasting.
The composed-stack workflow then verifies the actual API, MongoDB, Celery
ingestion path, and persisted ready-sample state.

Browser validation remains necessary because it exercises the deployed bundle,
reverse proxy, browser history, viewport behavior, tooltips, file rendering,
and the actual request lifecycle.

> **Caution: Clinical safety**
>
>
> Do not use production databases or patient data for automated browser validation.
> Validate report text and PDF structure with approved synthetic fixtures.
>

## Automated Release Gate

Run the complete local quality suite before a release candidate:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh

# Include rendered Compose validation when checking a deployment profile.
PYTHON_BIN=.venv/bin/python \
COMPOSE_FILES="deploy/compose/docker-compose.yml deploy/compose/docker-compose.dev.yml" \
COMPOSE_ENV_FILE=deploy/env/example.env \
bash scripts/quality/run_quality_suite.sh
```

The command runs backend tests, repository/contract checks, frontend lint and
production build, and a strict MkDocs build. It does not provision an application
deployment or MongoDB. Browser checks start a local Vite server, and proxy tests
may start temporary Nginx containers.

Run the additional database checks explicitly when needed:

```bash
.venv/bin/python scripts/quality/run_transaction_tests.py -- -q tests/integration
```

This requires a local `mongod` executable and uses newly created temporary
replicas, including authentication checks. It does not reuse a deployment
database. See [database quality gates](test-strategy-and-quality-gates.md#unified-quality-gate)
for the manual CI option. The disposable-container checks below are also on demand.

### Browser Route Checks

Install the browser once on a workstation, then run the front-end suite:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e -- --workers=4
```

The worker limit keeps full-schema API documentation and screenshot scenarios
from competing with too many browser processes on a development workstation.
It does not change test assertions or timeouts.

The suite uses API fixtures for repeatable rendering and error-state tests. It
starts its own frontend on a fixed local port, refuses to reuse an existing
server and overrides the backend proxy with a loopback dead end. Unmatched API
requests cannot fall through to an ambient deployment configuration. It
does not replace deployment validation or clinical test data checks. Run it as
part of local release validation; the GitHub `quality` workflow runs smoke checks
without installing browsers or running this suite.

The sample-analysis browser contracts also assert that endpoints are requested
only when their configured tab is opened. DNA tests distinguish somatic and
germline SNV requests by the `intent` query parameter; RNA tests ensure fusion
requests are not issued for DNA samples or before the RNA fusion tab is
selected. This protects both correctness and unnecessary backend/database
work.

The deterministic suite intentionally does not repeat every component-level
assertion already owned by Vitest. Playwright owns behavior that depends on the
browser runtime: routing, URL state, navigation between pages, deferred network
requests, form submission across real React providers, and module guards.

### Running With Disposable Containers

The real-service suite runs only on a fresh local Docker stack with synthetic
Demo records. **Never point browser tests at production, an existing deployment,
or a database reached through a tunnel.** The runner accepts no target URL,
database URI, credentials or existing project name.

From the repository root, after installing the workspace development dependencies,
frontend dependencies and Playwright Chromium:

```bash
bash install.sh test-browser
# Optionally retain evidence under a chosen new directory in this checkout:
bash install.sh test-browser --output .cache/browser-acceptance-candidate
```

The command builds the current server and frontend, starts authenticated MongoDB,
Redis, API, ingestion and maintenance workers, and the synthetic bootstrap. Each
run receives independent credentials, a random project name and new data volumes.
MongoDB and Redis have no published ports and stay on an internal network. Only
the frontend joins a separate bridge and publishes a loopback browser port.
Ordinary environment files, Docker contexts and Compose overrides are not used.
The application database credentials are restricted to the four demo databases.

Before starting browsers, configuration and runtime checks verify the database
names, storage ownership, Docker project labels and frontend port binding. The
Playwright configuration requires the live runner's private state file and rejects
arbitrary deployment URLs. `npm run test:e2e:real` is the runner's internal command;
invoke `install.sh test-browser` to create its required disposable target.

The suite exercises real HTTP requests without API interception:

- Anonymous and scoped access, assay/environment separation, CSRF enforcement and
  server-side session invalidation.
- Superuser login counts, multiple sessions for one account, logout and denial for
  regular user administrators.
- DNA and RNA workspaces, WGS uploads with populated CNV/translocation/SNV tables,
  persistent sanitized comments and concurrent editing.
- HTML/PDF previews without report creation, cancellation, stale-preview rejection,
  reviewed report saving and immutable saved artifacts with finding snapshots.
- Queued ingestion while its worker is stopped, recovery after restart, and invalid
  uploads that fail visibly without creating a partial sample.
- Public catalog, gene matrix, API documentation and application controls.

Every collected scenario must pass. Skipped or unfinished scenarios, expected
failures, retries masking a failure and focused tests fail acceptance. The runner
retains `browser-results.json`, `run.json`, redacted service logs and failure traces
in its evidence directory. These may include synthetic credentials in browser
traces; keep the directory private and outside Git. Generated credential files are
removed, and the runner removes only its own containers, networks and data volumes,
including after test failures. `run.json` records the cleanup result.

Report checks compare renderer metadata with the pin in
`core/pyproject.toml`. The workspace Python reads that TOML declaration. This suite
uses the normal application build with the isolated Demo package and local HTTP;
trusted HTTPS, center configuration, final release-artifact identity and clinical
expected results remain separate acceptance checks on isolated validation systems.
They must never use production databases.

### Composed Stack Acceptance Check

Use an [isolated demo deployment](../deployment/demo-installation.md) for composed
acceptance. Verify health through its public proxy and `SCRIPT_NAME`, sign in with
a controlled account, install synthetic samples and confirm that an ingested sample
reaches `ready`. Exercise review and report saving, failure recovery, permission
boundaries and backup/restore against disposable targets.

Record the candidate artifact identifiers and results. These checks exercise real
authentication, routing, persistence and workers; mocked browser tests do not replace
them. They run as local or center-controlled release validation, not GitHub CI.

## Browser Validation Protocol

The [Locust workload](load-and-capacity-testing.md) measures HTTP requests through the deployed
proxy, not React rendering, deferred component behavior, layout, or accessibility.
Keep these browser checks separate, even when both suites use the same synthetic
fixture revision. Do not repeat this protocol's report saves or administrative
mutations in a load loop; the load workload excludes publication and finalization.

Use a clean browser profile and a controlled account for each access scope:

| Account scope | Purpose |
| --- | --- |
| Clinical reviewer | Review tables, filters, detail views, comments, reports, and exports. |
| Admin | Validate managed resources, role/permission enforcement, audit events, and controls. |
| Public visitor | Validate `/public`, catalog, matrix, gene pages, contact, and unauthenticated routing. |
| Restricted user | Confirm permissions fail safely with useful messages and no hidden mutation. |

### 1. Reverse Proxy And Entry Points

1. Open `${SCRIPT_NAME}` with and without a trailing slash.
2. Confirm the browser remains on the configured prefix and does not redirect
   to an internal container port.
3. Open `${SCRIPT_NAME}/docs-site/` and `${SCRIPT_NAME}/api/v1/docs`.
4. Open `${SCRIPT_NAME}/public` while signed out. Confirm only public
   navigation is available and a sign-in action is shown.
5. Sign in and open the same public URL. Confirm the public content remains
   accessible while the regular session navigation is available.

### 2. Sample Review

For one DNA sample with SNV, CNV, coverage, biomarker, and structural inputs:

1. Open `/samples`; verify the live/reported tabs, server-side pagination,
   multi-column sorting, filtering, CSV export, local-time dates, and sample
   links.
2. Open the sample. Refresh while on each tab and use browser Back from each
   finding detail page. Confirm tab, filter, page, and sort state persist.
3. On Small Variants, CNV, Fusion, and Translocation tabs, check:
   row count, server sorting, table paging, selection, confirmation dialogs,
   mutation notifications, and in-place refresh after a permitted action.
4. Open a finding detail page. Check header context, caller badges, tier
   controls where supported, comments, knowledgebase accordions, transcript
   details, tooltip placement near viewport edges, and external links.
5. On the CNV tab, resize the split pane and rotate the profile image. Confirm
   the image uses available pane space and the table remains usable.
6. On Coverage, click genes and inspect exon/CDS/probe context, low coverage,
   and blacklist add/remove behavior.

### 3. Report Lifecycle

1. Change sample filters and confirm the temporary preview refreshes.
2. Confirm preview rows include the configured report sections and the active
   ASPC/filter context.
3. Review HTML preview at normal and narrow viewport widths.
4. Save only after confirming the preview. Verify the confirmation, notification,
   saved report row, PDF download, and report history link.
5. Inspect the saved report through the API or MongoDB and verify immutable
   ASPC reference, filter snapshot, report rows, artifact metadata, and
   `reported_variants` records.

### 4. Admin And Operations

1. Create, view, edit, and list one non-production test record
   for each managed resource type.
2. Verify each mutation creates an audit event with actor, resource name, id,
   outcome, and local-time display in the UI.
3. Open Application Controls. Compare configured task switches with the
   observed Celery worker count, queues, active/reserved/scheduled counts,
   registered tasks, and Beat schedule entries.
4. Queue manual maintenance once. Confirm its task id, result through the
   internal task-status endpoint, and resulting audit/log retention behavior.
5. Turn off a task family in the test environment. Verify future invocations
   report `disabled`, while already-running tasks are not terminated.

### 5. Notifications And Failure States

1. Trigger one allowed mutation and one denied mutation.
2. Trigger a controlled API validation failure.
3. Confirm toast and notification history identify the affected sample,
   finding, resource, or task and show a user-facing explanation rather than
   an opaque HTTP error.
4. Reload and navigate between pages. Confirm notification history persists as
   intended and stale failure notices do not reappear as new events.

## Release Evidence

Record the following for each candidate:

- application version and Git revision
- deployment environment and `SCRIPT_NAME`
- synthetic fixture revision
- browser and operating system
- test operator and date
- passed/failed protocol steps with screenshots for deviations
- report/PDF artifact checksums for approved golden cases
- links or identifiers for relevant audit events

## Failure Handling

Do not promote a release when a validation failure changes clinical finding
visibility, report text, report snapshots, access control, ingest atomicity, or
auditability. Capture the request id, sample/test fixture identifier, browser
console output, API response, and related audit event before investigation.
