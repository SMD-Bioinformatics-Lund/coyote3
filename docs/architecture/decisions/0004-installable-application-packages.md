# ADR 0004: installable application and library packages

**Status:** Accepted
**Date:** 16 November 2026

## Context

Coyote combines clinical rules, persistence, an HTTP API, background workers and
a browser interface. Clinical operations must be reusable by trusted hosts without
requiring the API application. Deployment must identify and test the Python code
and resources actually installed in an image.

Running directly from a checkout can hide missing package files or undeclared
dependencies. Clinical logic needs an independent installation boundary, while the
API and MongoDB adapter are delivered together as the application's server.

## Decision

Maintain four installable Python distributions in one uv workspace: the core
library, server application, ingestion service and HTTP client. The root project builds
the server; `core/`, `services/ingest/` and `clients/python/` are workspace projects.

| Distribution and source | Responsibility | Local dependencies |
| --- | --- | --- |
| `coyote-core`, in `core/` | Clinical contracts, rules and application operations | None |
| `coyote-server`, at the root | API, runtime composition and maintenance in `api/`; MongoDB persistence in `adapters/mongo/` | Core |
| `coyote-pyclient`, in `clients/python/` | Remote HTTP access and client-owned response models | None |
| `coyote-ingest`, in `services/ingest/` | Pipeline submission tools and ingestion workers | Core and client; worker extra uses server composition |

The root `pyproject.toml` owns the server version, dependencies and wheel build.
API and MongoDB code retain their `src/` namespaces, documentation, changelogs and
test suites. Their component `pyproject.toml` files configure tests and coverage;
they do not define separate distributions or releases. Core and client own their
independent distribution metadata. The frontend remains a separate Node application
in the same repository. Packaging does not introduce additional deployed services.

The server installs `coyote_api` and `coyote_mongo` together. Their code boundaries
remain explicit: API composition supplies adapter implementations of core repository
interfaces, and neither core nor adapter imports the API. The server is not a second
clinical SDK. API and worker entry points consume installed code and resources,
including templates, logos, configuration defaults and installation catalogs.

Ingestion parsing and clinical workflows belong to core. The ingestion service
owns worker entry points and submission transports; the server publishes named
tasks without importing the service. Worker installation includes server composition
and MongoDB integration, while submission-only installation requires no server.

The independent client communicates through HTTP and imports no server or core code.
The deployment image includes its verified wheel for administration commands such
as `manage_data.py`; the API runtime does not depend on or import the client.

## Benefits

- **Reusable clinical behavior:** another trusted host can consume the core
  without importing FastAPI or MongoDB.
- **Explicit dependencies:** each distribution declares the libraries it installs;
  architecture tests reject dependencies pointing back toward the API.
- **Testable artifacts:** wheel-isolation tests run outside the checkout and
  detect missing resources or accidental imports from local source directories.
- **Deployment traceability:** release records retain the selected versions and
  SHA-256 hashes of the core, server, ingestion and administration-client wheels.
- **Fast local iteration:** editable workspace installs expose Python edits after
  process reload. Ordinary edits do not require wheel rebuilds.
- **Coordinated changes:** one repository retains shared integration tests,
  frontend/API contracts and review of changes spanning components.
- **One server release:** API and MongoDB changes share a wheel and version while
  retaining component-level tests and coverage.

## Costs and constraints

Installable distributions require dependency pins, build configuration, package data
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

Core and client guides describe their independent packages. API and adapter guides
describe their respective server components, including configuration, interfaces
and tests. Root documentation describes the complete application, clinical user
workflows, deployment, integration and architecture decisions. The documentation
site publishes these guides directly from their source files.

## Verification

Maintain package and component tests, architecture guards, installed-wheel isolation,
source-distribution builds and shared application regressions. Verify release
metadata and artifact hashes before deployment. External-service tests require
their documented synthetic environments.

See [package boundaries](../../sdk/package-boundaries.md),
[editable development](../../sdk/uv-development.md) and
[release compatibility](../../sdk/compatibility.md).
