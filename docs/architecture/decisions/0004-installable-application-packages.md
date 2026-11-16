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

Maintain six installable Python distributions in one uv workspace. The root
project builds the server; core, client, ingestion, reference and demonstration
packages have their own workspace projects.

| Distribution and source | Responsibility | Local dependencies |
| --- | --- | --- |
| `coyote-core`, in `core/` | Clinical contracts, rules and application operations | None |
| `coyote-server`, at the root | API, runtime composition and maintenance in `api/`; MongoDB persistence in `adapters/mongo/` | Core |
| `coyote-pyclient`, in `clients/python/` | Remote HTTP access and client-owned response models | None |
| `coyote-relay`, in `services/relay/` | Pipeline submission tools, optional HTTP routes and ingestion workers | Core and client; API/worker extras use server composition |
| `coyote-atlas`, in `services/atlas/` | Reference bundles, provenance, validation and publication | Core and client; optional API integration uses server composition |
| `coyote-demo`, in `services/demo/` | Synthetic datasets and guarded demo installation | Core; optional API integration uses server, and worker integration uses Relay |

The root `pyproject.toml` owns the server version, dependencies and wheel build.
API and MongoDB code retain their `src/` namespaces, documentation, changelogs and
test suites. Their component `pyproject.toml` files configure tests and coverage;
they do not define separate distributions or releases. Each other package owns its
independent distribution metadata. The frontend remains a separate Node application
in the same repository. Packaging does not introduce additional deployed services.

The server installs `coyote_api` and `coyote_mongo` together. Their code boundaries
remain explicit: API composition supplies adapter implementations of core repository
interfaces, and neither core nor adapter imports the API. The server is not a second
clinical SDK. API and worker entry points consume installed code and resources,
including templates, logos, configuration defaults and installation catalogs.

Ingestion parsing and clinical workflows belong to core. The ingestion service
owns submission transports, ingestion HTTP routes and worker entry points. The server
publishes named tasks without importing worker code and discovers installed API
extensions through `coyote.api.routers`. It has no required Relay dependency.
API and worker installation include server composition and MongoDB integration,
while submission-only installation requires no server.

Atlas owns reference artifacts and their lifecycle independently of clinical
interpretation policy. The server selects its provider through an installed entry
point and supplies repository implementations. Demo owns synthetic data and
installation, with a separate guarded deployment. Its extension stays disabled
unless explicitly configured for restricted demo databases and local services.
The ordinary application image excludes Demo. These packages supply commands and
optional integrations; neither requires an always-running service of its own.

The independent client communicates through HTTP and imports no server or core code.
The deployment image includes its verified wheel for administration commands such
as `install.sh data`; the API runtime does not depend on or import the client.

## Benefits

- **Reusable clinical behavior:** another trusted host can consume the core
  without importing FastAPI or MongoDB.
- **Explicit dependencies:** each distribution declares the libraries it installs;
  architecture tests reject dependencies pointing back toward the API.
- **Testable artifacts:** wheel-isolation tests run outside the checkout and
  detect missing resources or accidental imports from local source directories.
- **Deployment traceability:** release records retain the selected versions and
  SHA-256 hashes of all six selected wheels.
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

Core, client, Relay, Atlas and Demo guides describe their own packages. API and adapter guides
describe their respective server components, including configuration, interfaces
and tests. Root documentation describes the complete application, clinical user
workflows, deployment, integration and architecture decisions. The documentation
site publishes these guides directly from their source files.

## Verification

Maintain package and component tests, architecture guards, installed-wheel isolation,
source-distribution builds and shared application regressions. Verify release
metadata and artifact hashes before deployment. External-service tests require
their documented synthetic environments.

Each package owns its unit, smoke and integration tests and coverage floor. Root
tests verify composition. Reusable test helpers may form a development-only
testkit when there is demonstrated duplication; this does not move component
suites into a central testing service. Frozen clinical regression inputs stay
with their tests rather than following changes to interactive demo datasets.

See [package boundaries](../../sdk/package-boundaries.md),
[editable development](../../sdk/uv-development.md) and
[release compatibility](../../sdk/compatibility.md).
