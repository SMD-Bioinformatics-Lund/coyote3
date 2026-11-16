# ADR 0004: installable application and library packages

**Status:** Accepted
**Date:** 16 November 2026

## Context

Coyote combines clinical rules, persistence, an HTTP API, background workers and
a browser interface. Clinical operations must be reusable by trusted hosts without
requiring the API application. Deployment must identify and test the Python code
and resources actually installed in an image.

Running directly from a checkout can hide missing package files or undeclared
dependencies. Keeping implementation responsibilities inside one distribution
also makes it harder to verify that clinical logic is independent of web and
database frameworks.

## Decision

Maintain the application in one repository with independently installable Python
projects. Use a virtual uv workspace for coordinated editable development.

| Project | Responsibility | Local dependencies |
| --- | --- | --- |
| `core/` (`coyote-core`) | Clinical contracts, rules and application operations | None |
| `adapters/mongo/` (`coyote-mongo`) | MongoDB repositories, query compilation and transactions | Core |
| `api/` (`coyote-api`) | HTTP handling, authentication, composition and workers | Core and MongoDB adapter |
| `clients/python/` (`coyote-pyclient`) | Remote HTTP access and client-owned response models | None |

Each Python project owns its metadata, version, `src/`, tests, documentation,
changelog and license. The frontend remains a separate Node application in the
same repository. Python project boundaries do not introduce additional deployed
services or require separate repositories.

The API is packaged as an installable server application. It is not a second
clinical SDK. API and worker entry points consume installed packages, including
their templates, logos, configuration defaults and installation resources.

## Benefits

- **Reusable clinical behavior:** another trusted host can consume the core
  without importing FastAPI or MongoDB.
- **Explicit dependencies:** each project declares the libraries it uses;
  architecture tests reject dependencies pointing back toward the API.
- **Testable artifacts:** wheel-isolation tests run outside the checkout and
  detect missing resources or accidental imports from local source directories.
- **Deployment traceability:** release records retain the selected versions and
  SHA-256 hashes of the core, adapter and API wheels.
- **Fast local iteration:** editable workspace installs expose Python edits after
  process reload. Ordinary edits do not require wheel rebuilds.
- **Coordinated changes:** one repository retains shared integration tests,
  frontend/API contracts and review of changes spanning components.

## Costs and constraints

Separate projects require dependency pins, build configuration, package data
declarations and integration testing. Version changes must be adopted as a tested
application combination. The release process verifies the selected artifacts;
packaging alone does not establish clinical correctness or deployment readiness.

A backend project already built and tested as an installed distribution can
provide the same artifact benefits. The directory name itself has no architectural
effect. Additional packages should be introduced only for a concrete independent
responsibility or reuse requirement.

Database independence belongs to the core's interfaces. A new adapter must preserve
query, identity, concurrency, audit and snapshot semantics. An ORM or connection
string does not supply that equivalence automatically.

## Documentation ownership

Package guides describe the package's installation, use, configuration and
interfaces. Root documentation describes the complete application, clinical user
workflows, deployment, cross-package integration and architecture decisions.
The documentation site publishes package guides directly from their source files.

## Verification

Maintain package-owned tests, architecture guards, installed-wheel isolation,
source-distribution builds and shared application regressions. Verify release
metadata and artifact hashes before deployment. External-service tests require
their documented synthetic environments.

See [package boundaries](../../sdk/package-boundaries.md),
[editable development](../../sdk/uv-development.md) and
[release compatibility](../../sdk/compatibility.md).
