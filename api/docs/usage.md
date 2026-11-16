# Requests, workers and reporting

HTTP routes under `/api/v1` authenticate the caller, validate transport inputs and
delegate to core operations. Current permissions and sample scope remain
server-side decisions. The browser and HTTP client use the same API boundary.

The host supplies core operations with verified identities, current policy,
repositories, integration clients and worker capabilities. Clinical finding
selection and rule evaluation remain in the core; persistence remains in the
MongoDB adapter.

Maintenance workers and beat use `coyote_api.celery_app`. Ingestion workers use
`coyote_relay.celery_app` from the separately installed ingestion service. API and
workers must use the tested core/server/ingestion combination and compatible
configuration. Uvicorn reload does not restart separate workers.

Report endpoints prepare JSON through core operations and render it with
`smd-reports`. Previewing and downloading are distinct from finalizing a report.
Finalization retains the selected findings, report artifacts and provenance using
the existing recoverable persistence flow.

Installation catalogs, center examples, documentation templates and brand assets
ship as server package data. Importing the host does not install its catalogs into a
database. Provisioning and maintenance remain explicit application operations.
