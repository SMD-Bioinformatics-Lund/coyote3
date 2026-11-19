# API changelog

## v1.0.0

- Release runtime connections and cached services after shutdown or failed startup;
  share ownership across overlapping ASGI lifespans and close worker resources on exit.
- Type-check ingestion, account recovery and saved-report repository contracts.
- Superuser-only aggregate login activity endpoint with uncached counts and no
  session credentials or personal account details in the response.
- Correct finding inventory totals for scoped accounts, including sample names that
  coincide with another sample's identifier.
- Authorize sample workspace reads with sample viewing permission; keep mutation guards separate.
- Expose read-only named-resource queries for metadata, IDs, counts, existence and
  distinct values, including bounded sample relation filters and documented limits.
- Report only installed application components on the About page; the external
  Python client is no longer an application dependency or installed-version field.

- Inject notification delivery when composing the refactored clinical-rule authoring
  service, preserving assignment, review and publication notifications.
- Load optional Atlas and Demo extensions, validate declared deployment constraints
  before persistence initialization, and expose enabled extensions to the frontend.
- Keep synthetic data out of normal bootstrap; support isolated native storage and
  an explicit process protection mode.

- Discover installed API router extensions; expose ingestion endpoints and their
  documentation when Coyote Relay is installed, without a required Relay dependency.
- Publish allowlisted ingestion jobs to the separately installable `coyote-relay`
  workers; retain server composition, maintenance tasks and beat scheduling.
- Apply authentication, CSRF, rate limits and documentation security headers to
  mounted API paths as well as paths already stripped by a reverse proxy.
- Fail startup consistently when runtime initialization fails, including under
  tests; mark readiness only after successful initialization and allow retry.
- Own HTTP, security, worker, configuration and branding regression tests with
  package-local fixtures, smoke checks and independent branch coverage.
- Include the separate copyright/affiliation notice in distributions and identify
  first-party source with GPL-3.0-only SPDX headers.
- Import the authoritative Mongo adapter implementation directly after removing
  its unused factory/forwarding module.
- Validate and retain package-specific backend settings before infrastructure
  initialization. Project Mongo settings and public-core flags without passing
  unrelated deployment credentials into those packages.
- Clarify environment loading, center-file ownership and packaged demo-data paths;
  correct configuration documentation after the source layout change.
- Distribute the API, maintenance workers and MongoDB adapter as `coyote-server`,
  retaining separate component source folders, tests, coverage and documentation.
- Depend on the independently versioned core wheel.
- Include API assets, center examples and synthetic installation workflows.
- Support editable uv workspace development and normal wheel deployment.
- Preserve HTTP contracts, scoped access and clinical workflow behavior.
- License this package under GNU GPL version 3 only.
- Version the server independently from the application release and core library;
  retain Coyote4 application labels while OpenAPI identifies the server release.
