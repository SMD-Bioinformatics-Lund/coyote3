# API changelog

## 1.0.0

- Publish allowlisted ingestion jobs to the separately installable `coyote-ingest`
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
