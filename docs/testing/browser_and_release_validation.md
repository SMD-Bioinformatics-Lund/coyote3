# Browser And Release Validation

This procedure verifies the user-visible behavior that unit and API tests cannot
fully establish: browser rendering, routing, asynchronous state, persisted data,
and generated clinical artifacts. Run it against a disposable development or
staging deployment populated only with approved synthetic or de-identified test
data.

## Validation Boundary

Automated backend tests validate contracts, permissions, business logic, and
route declarations. The frontend route registry is checked against the FastAPI
route table and every React Router path is required to have a route contract.
Playwright exercises browser-level login and account-route behavior with
deterministic API fixtures. The composed-stack workflow then verifies the
actual API, MongoDB, Celery ingestion path, and persisted ready-sample state.

Browser validation remains necessary because it exercises the deployed bundle,
reverse proxy, browser history, viewport behavior, tooltips, file rendering,
and the actual request lifecycle.

!!! caution "Clinical safety"

    Do not use production patient data for browser or release validation.
    Validate report text and PDF structure with approved synthetic fixtures or
    formally de-identified cases only.

## Automated Release Gate

Run the complete local quality suite before a release candidate:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/run_quality_suite.sh

# Include rendered Compose validation when checking a deployment profile.
PYTHON_BIN=.venv/bin/python \
COMPOSE_FILE=deploy/compose/docker-compose.dev.yml \
bash scripts/run_quality_suite.sh
```

The command runs backend tests, repository/contract checks, frontend lint and
production build, and a strict MkDocs build. It does not start services or
modify MongoDB.

### Browser Route Checks

Install the browser once on a workstation, then run the front-end suite:

```bash
cd frontend
npx playwright install chromium
npm run test:e2e
```

The suite uses API fixtures for repeatable rendering and error-state tests. It
does not replace deployment validation or clinical test data checks. GitHub
Actions installs Chromium and runs the same command in the `quality` workflow.

### Composed Stack Acceptance Check

The `bootstrap-and-ingest-check` workflow starts the stage Compose profile,
creates a disposable administrator, seeds the minimum test collections, uploads
the approved synthetic DNA bundle, and calls
`scripts/verify_composed_workflow.py`. The final check requires `/samples` to
return an ingested sample in the `ready` state. This verifies the production
boundaries that mocked browser tests cannot cover: authentication, request
routing, persistence, ingest processing, and sample-list projection.

## Browser Validation Protocol

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
