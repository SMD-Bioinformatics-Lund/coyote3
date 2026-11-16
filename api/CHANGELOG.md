# API changelog

## 1.0.0

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
- Distribute the API and worker host separately as `coyote-api`.
- Depend on independently versioned core and MongoDB adapter wheels.
- Include API assets, center examples and synthetic installation workflows.
- Support editable uv workspace development and normal wheel deployment.
- Preserve HTTP contracts, scoped access and clinical workflow behavior.
- License this package under GNU GPL version 3 only.
- Version the API host independently from the application release and core library;
  retain Coyote4 application labels while OpenAPI identifies the API package release.
