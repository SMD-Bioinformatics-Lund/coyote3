# Test strategy and quality gates

Tests protect application behavior, HTTP contracts, clinical rules, and deployment
operations. Choose the suite for the changed boundary and use the full quality
gate for cross-layer changes or release preparation.

## Test boundaries

![Test layers and quality gates](../assets/diagrams/test-coverage-map.svg)

The test suite is grouped by runtime boundary:

- **Core (`core/tests`)**: pure functions, clinical rules, portable contracts and services.
- **MongoDB adapter (`adapters/mongo/tests`)**: query compilation, repository behavior and core-port integration.
- **REST interface (`api/tests`)**: HTTP contracts, host composition, workers and permissions.
- **HTTP client (`clients/python/tests`)**: transport, authentication, typed resources and failures.
- **Repository tooling (`tests/unit`)**: deployment definitions, maintenance tools, documentation and releases.
- **Integration Layer (`tests/integration`)**: cross-component contracts, architecture boundaries, and recovery behavior.
- **Frontend (`frontend`)**: TypeScript build, linting, Vitest unit coverage,
  and Playwright route/API contract checks.

### Python suite ownership

API tests are grouped by the behavior they protect:

| Location | Scope |
| --- | --- |
| `core/tests/unit` | Clinical rules, filtering, contracts, reporting and workflow services with synthetic ports. |
| `api/tests/unit`, `api/tests/http` | Host configuration, workers, authentication, HTTP validation and permission matrices. |
| `adapters/mongo/tests/unit`, `adapters/mongo/tests/integration` | Repository behavior, query compilation and adapter/core integration without an external server. |
| `clients/python/tests` | Independent synchronous and asynchronous HTTP client behavior. |
| `tests/unit` | Repository tooling, deployment configuration, documentation and release validation. |
| `tests/integration` | Installed distributions, application transactions, architecture boundaries and frontend/API contracts. |
| Each package's `tests/smoke`, root `tests/smoke` | Fast package checks and in-process application composition. |

`tests/integration/test_api_architecture_boundaries.py` checks import direction
and persistence boundaries in HTTP, application, and domain modules.

Root `pytest.ini` discovers all five Python test roots. Package-local pytest
configuration and fixtures allow each project to run from its own directory.
Core and adapter unit tests receive `unit`; host tests receive `api`; client
tests receive `client` and `unit`. Adapter integration tests receive `integration`;
root integration tests also receive `contract`. Fast checks receive `smoke`.
Use `pytest -m MARKER` to filter an already collected suite.
Configured-service tests require their documented opt-in environment settings.
Package helpers must not import root tests or another package's test helpers.
Root integration tests may compose those synthetic fixtures. Core fixtures supply
a deterministic test hashing port; MongoDB and API fixtures bind the real adapter
codec. Neither requires a global codec installed by another suite.
The optional Locust smoke suite under `tests/load` runs separately with its load
toolchain; it is excluded from default pytest discovery.

### Fast smoke checks

Run explicit smoke directories to avoid collecting the full test suite:

```bash
scripts/quality/run_package_tests.sh all --smoke
scripts/quality/run_package_tests.sh api --smoke
.venv/bin/python -m pytest -q tests/smoke
npm --prefix frontend run test:smoke
```

Python package smoke checks cover portable variant identity, settings projection,
the API health entry point, BSON/portable record conversion and authenticated client
preview transport. Root checks exercise the real client/API health request in
process, with synthetic session validation, and the host-bound record hashing port.
Frontend smoke checks exercise confirmation actions, focus, keyboard handling and
pending states with the actual shared component. Each selected test exists once
and remains part of its full suite.

Smoke checks use synthetic inputs, mocked authentication and in-process transports.
They do not connect to external services, build wheels, paginate PDFs or start
application services. Running them checks a small set of important behaviors;
full suites and configured-service integration tests remain required for releases.
No smoke CI jobs are configured. The commands can be called by future CI jobs.

### Independent package coverage

```bash
scripts/quality/run_package_tests.sh core
scripts/quality/run_package_tests.sh mongo --coverage
scripts/quality/run_package_tests.sh all --coverage
```

The runner changes to each package directory and uses its own pytest/coverage
configuration. Each Python package's `test` extra includes the test and coverage
tools. For an isolated installation, install `.[test]` from that package, then run
`python -m pytest --cov --cov-config=pyproject.toml --cov-report=xml` there.
The uv workspace keeps source editable; test changes do not require wheel builds.

Coverage measures each package's complete runtime namespace, including unexecuted
modules, with branch coverage. Reports stay separate in each project's `.coverage`
database and `coverage/coverage.xml`; HTML is available with `--cov-report=html`.
Root integration results do not contribute to these independent package reports.

| Package | Independent branch-aware floor |
| --- | ---: |
| Core | 62% |
| MongoDB adapter | 51% |
| API host | 75% |
| HTTP client | 81% |

Core and adapter floors record the measured baseline after separating test ownership.
Their remaining uncovered paths need package-local regression tests as those areas
are changed. These new floors preserve existing tests; the existing combined 75%
backend gate and family gates remain unchanged, including 100% for clinical
reporting rules. The repository quality runner checks both combined coverage and
independent package floors. Smoke runs do not enforce full-suite coverage floors.

### UI coverage organisation

Browser tests live in `frontend/tests/e2e`. They use deterministic intercepted
API responses, so they test route rendering and request dispatch without
depending on a live clinical database. API-documentation browser checks fetch
the pinned Swagger UI and ReDoc assets from their CDN before intercepting those
requests in the browser. Real-deployment smoke tests are a separate suite.

Most unit tests live beside the TypeScript modules they protect as
`*.test.ts`. Vitest writes terminal, JSON summary, and LCOV reports to
`frontend/coverage/`. The report includes frontend library modules even when a
module has no tests; coverage is calculated over the configured source scope.
The full Vitest suite also collects `frontend/tests/smoke`; those cases are not
duplicated beside their components.

Vitest runs at most four workers to bound simultaneous jsdom instances and avoid
CPU contention on shared runners. A developer can override the limit explicitly
with `npm --prefix frontend run test:coverage -- --maxWorkers=2` on a smaller machine.
Test timeouts and coverage thresholds remain independent of the worker limit.

Vitest enforces global non-regression floors over the complete declared source
scope: 75% statements, 60% branches, 65% functions, and 77% lines. These are
release gates rather than completion targets. New modules included in the
scope must bring tests with them, and the floors should rise only after the
measured suite has enough deterministic margin to remain stable across local
and CI environments.

The frontend suite uses five complementary levels:

| Level | Location | What it verifies |
| --- | --- | --- |
| Pure module | Colocated `*.test.ts` | Normalization, routing, formatting, storage, authorization, export, and request-key behavior without a browser DOM. |
| Component | Colocated `*.test.tsx` | Visible content, keyboard/mouse interaction, accessibility roles, callbacks, disabled states, confirmation flows, and loading/error/empty states in jsdom. |
| Page and route contract | Colocated page tests plus the UI route registry | Page composition, API request parameters, response-field consumption, navigation targets, mutations, query invalidation, and recoverable failures. |
| Browser workflow | `frontend/tests/e2e` | React Router behavior in Chromium, deferred data loading, modality/ASPC tab selection, intent-isolated requests, cross-page state, guarded modules, and mutation workflows. |
| Deployment smoke | `frontend/tests/e2e-real` | Running reverse proxy, `SCRIPT_NAME`, public APIs, login, dashboard, and sample workspace without intercepted requests. |

Component tests should render the real component wherever practical. When a
large shared component such as `DataTable` is replaced with a focused test
double, the double must still execute representative column accessors and cell
renderers. A count-only table stub does not validate clinical presentation or
navigation behavior.

| Browser contract | Protected behavior |
| --- | --- |
| Authentication routes | Provider display, failed sign-in, and password-reset feedback. |
| Sample analysis layouts | ASPC analysis selection, sample modality, intent visibility, combined Findings composition, tab presentation, and deferred endpoint requests. |
| Primary application workflows | Dashboard composition, live/reported sample state, disabled-module routing, matrix search, profile persistence, and notification broadcasting. |
| Route registry contracts | Every declared UI route identifies its backend dependencies and empty/error behavior. |

Frontend unit ownership is divided by behavior so regressions are attributable
to a clear boundary:

| Unit-test area | Protected behavior |
| --- | --- |
| API client | Typed envelope unwrapping, JSON and form requests, structured validation errors, non-JSON gateway failures, and expired-session redirects. |
| Finding actions | Single and bulk mutation endpoints, tier changes, per-finding CNV requests, cache keys, and empty-selection rejection. |
| Sample and finding normalization | Supported payload shapes, intent-specific filters, tab-to-analysis mapping, fusion/translocation fields, flags, tiers, and caller labels. |
| Notifications | Persistence limits, malformed storage recovery, duplicate suppression, and subscriber updates. |
| Clinical comment formatting | HTML escaping, safe links, headings, code, lists, quotes, tables, and horizontal rules. |
| External links and configured values | URL encoding, disabled integrations, case-insensitive metadata lookup, and semantic badge classes. |
| Shared tables and controls | Sorting state, multi-sort behavior, selection, pagination, exports, bulk actions, confirmation dialogs, split panes, themes, and accessible control labels. |
| Clinical pages | Representative SNV, CNV, fusion, translocation, coverage, report, comment, knowledgebase, and transcript payloads, including empty and failed responses. |
| Administration | Managed-resource list/view/create/edit behavior, system-managed restrictions, category filters, notification broadcasts, application controls, and route audit output. |

New clinical pages must add a browser contract for their primary successful,
empty, and failed states. New analysis views must verify that unavailable
analysis endpoints are not requested.

## Primary Execution Commands

Run the validation suite in an isolated virtual environment:

```bash
# Run the full test suite
PYTHONPATH=. python -m pytest -q

# Generate the unified backend coverage report
PYTHONPATH=. python -m pytest -q \
  --cov=coyote_api --cov=coyote --cov=coyote_mongo --cov-config=.coveragerc \
  --cov-report=term-missing --cov-report=xml:coverage.xml

# Execute static analysis and linting
PYTHONPATH=. python -m ruff check core api adapters clients tests scripts

# Check the configured strict type boundaries
PYTHONPATH=. python -m mypy

# Generate frontend unit coverage and LCOV
npm --prefix frontend run test:coverage

# Execute strict documentation build verification
.venv/bin/python -m mkdocs build --strict
```

## Unified Quality Gate

Use the repository quality command for a release candidate or a substantial
cross-layer change:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh
```

This runs backend and independent Python client tests, family coverage gates,
typing and contract checks, frontend lint/unit/browser tests, the OpenAPI-checked
build, and documentation checks. Browser tests start a local Vite server with
intercepted deterministic API responses. External knowledgebase calls use fixtures.

Database integration tests are on demand and require disposable MongoDB replicas.
The normal quality command does not start MongoDB. The explicit runner requires
`mongod` and enables transaction tests plus an authentication-enabled replica for
runtime-permission checks:

```bash
.venv/bin/python scripts/quality/run_transaction_tests.py -- \
  -q tests/integration
```

The runner starts two loopback-only replicas, supplies test database settings, and
terminates its child processes afterwards. It never connects to an existing
deployment. Do not point integration tests at production databases.

In GitHub Actions, manually run the `quality` workflow and select
**Run disposable MongoDB integration tests**. That job is disabled for automatic
push and pull-request runs and for manual runs without the option selected.
The separate `bootstrap-and-ingest-check` workflow is also manually triggered.

To validate rendered Docker Compose configuration as part of the same gate:

```bash
PYTHON_BIN=.venv/bin/python \
COMPOSE_FILES="deploy/compose/docker-compose.yml deploy/compose/docker-compose.dev.yml" \
COMPOSE_ENV_FILE=deploy/env/example.env \
bash scripts/quality/run_quality_suite.sh
```

> **Tip: Browser validation**
>
>
> This command verifies source and build behavior. Before promotion, follow
> the [Local disposable full-stack validation](disposable-stack-validation.md)
> procedure against an empty isolated database, followed by the separate
> [Browser and release validation](browser-and-release-validation.md)
> procedure against the intended deployment and approved synthetic fixtures.
>

## Running GitHub checks locally

The preferred local equivalent of the `quality` workflow is the repository
quality script:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh
```

It runs the same backend tests, coverage gates, type boundary, contract checks,
frontend lint/unit/browser/build checks, and strict documentation build used by
GitHub Actions. Add Compose rendering when deployment files changed:

```bash
PYTHON_BIN=.venv/bin/python \
COMPOSE_FILES="deploy/compose/docker-compose.yml deploy/compose/docker-compose.dev.yml" \
COMPOSE_ENV_FILE=deploy/env/example.env \
bash scripts/quality/run_quality_suite.sh
```

Use [`act`](https://github.com/nektos/act) only when the GitHub runner wrapper
itself must be tested locally:

```bash
act workflow_dispatch \
  -W .github/workflows/quality.yml \
  -j lint-and-test
```

`act` requires Docker and downloads a runner image. It approximates GitHub's
hosted runner but does not replace the repository quality script or the actual
GitHub check. The composed bootstrap-and-ingest workflow depends on Docker
networking and service lifecycle behavior; run it with GitHub's manual
`workflow_dispatch` or reproduce its documented target-center steps rather
than treating an `act` run as release evidence.

## Coverage Verification and Quality Gates

Coverage checks enforce minimum thresholds for key logic families.

```bash
# Execute multi-family coverage validation
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/quality/run_family_coverage_gates.sh
```

The system applies a **75% minimum** to `core/src/coyote/domain`, with separate
thresholds for `core/src/coyote/application` and `api/src/coyote_api/interfaces/http`. It also enforces a
**75% minimum** over the clinical query-policy modules: DNA SNV, CNV, and
translocation query builders and the RNA fusion query builder. This is a
combined branch-aware gate, not a line-count exclusion. It protects the code
that decides which findings enter clinical review.

When run directly, the gate collects coverage for all backend packages once,
then evaluates each family by filesystem scope. The repository quality
suite and CI collect the complete backend coverage database once and invoke
the gate with `--from-existing`. Reusing that database preserves the same
family thresholds without repeating the backend suites for each family.
This also prevents a stale or renamed Python module path from silently turning
a family gate into a repository-wide total.

CI publishes `coverage.xml` as the `backend-coverage` workflow artifact and
`frontend/coverage/lcov.info` as part of the `frontend-coverage` artifact on
default-branch and manually dispatched runs. Pull-request checks enforce the
same thresholds but do not upload coverage artifacts. Artifacts are retained
for seven days to keep storage use bounded. The backend XML is the
repository-wide observation report; family gates remain the release controls
for clinically important boundaries.

Clinical query policy has a separate coverage threshold. Repository-wide
coverage also includes adapters, deployment helpers and administrative code;
it does not replace the clinical, application or HTTP family gates.

## Python docstrings

Test names should identify the condition and expected behavior. Add a short
docstring when it explains a non-obvious clinical or security invariant. Avoid
parameter sections that repeat fixture names and return sections on tests that
return nothing.

Production Python modules, classes and named functions require docstrings,
including private helpers and nested callbacks. Use Google-style sections:

| Section | What to document |
| --- | --- |
| Summary | The operation and its result, in one precise sentence. |
| `Args:` | Each parameter's meaning, units, accepted values and relevant defaults; omit `self` and `cls`. |
| `Returns:` or `Yields:` | The result's structure and meaning, including empty or null cases. Omit for procedures that only return `None`. |
| `Raises:` | Expected failures callers need to handle. |
| `Notes:` | Relevant side effects, transaction boundaries, input mutation, ordering or external-service access. |
| `Examples:` | Short synthetic examples when they clarify behavior. |

Simple properties may use a precise one-line docstring. Document actual behavior:
constructing a document does not mean inserting it, and an empty result is not
necessarily an error. Do not copy type annotations into otherwise empty descriptions.

The backend suite includes an AST-based presence check for `api/`, `scripts/`,
`tests/load/`, Gunicorn configuration and root Python entry points. It does
not import the application, connect to MongoDB, or inspect clinical data. Run it with:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/integration/test_python_docstrings.py --no-cov
```

This check detects missing documentation, not inaccurate explanations. Ruff checks
the configured Google-style formatting; code review checks the content against the
implementation. Ordinary tests and fixtures are outside this presence check;
the executable load harness under `tests/load/` is included.

## Continuous Integration

### Documentation checks

Run documentation checks from the repository root:

```bash
npm run docs:lint
npm run docs:test
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
```

The Markdown runner checks repository documentation and GitHub guidance, excluding
the generated collection reference and issue/PR templates. Its tests cover file
selection, lint failures, and math rendering. See
[Writing documentation](../development/writing-documentation.md) for ownership,
generated references, and placement rules.

### Automated checks

CI should run these checks:

1. **Static analysis**: Ruff lint and formatting checks.
2. **Tests**: Backend and frontend test suites.
3. **Contract checks**: API and database schema consistency.
4. **Documentation**: Markdown lint, link checks, and an MkDocs build with warnings treated as errors.
5. **Compose validation**: Resolved Docker Compose configuration where relevant.
6. **UI/API route registry**: Every literal API operation declared by the
   React route registry must resolve to a FastAPI route. This detects stale
   page contracts before manual browser validation.
7. **Strict type boundary**: `mypy` checks the modules selected in root
   `pyproject.toml`, including domain contracts, selected ingest/reporting services,
   authentication, accounts, and the MongoDB base, transaction and assay-configuration
   repositories. The assay conformance test checks the concrete implementation against
   its core protocol. This is a selected boundary, not whole-application strict typing.
   Add modules only after they pass strict mode; do not weaken the boundary to admit them.
8. **Coverage artifacts**: Backend XML and frontend LCOV results are retained
   for seven days after default-branch and manually dispatched runs.

### GitHub Actions execution policy

Branch protection should require both `quality / lint-and-test` and
`quality / api-contracts`. The latter checks generated TypeScript contracts against
the backend revision and builds the frontend. The workflow limits runner usage:

| Policy | Behavior |
| --- | --- |
| Default branch | Pull requests and pushes target `master`, which is the repository default branch. |
| Draft pull requests | Expensive validation starts when the pull request is marked ready for review. |
| Superseded commits | A newer commit cancels the running quality job for the same pull request or branch. |
| Backend changes | Run Python lint, formatting, strict typing, the complete backend suite once, family coverage gates, and repository contract checks. |
| Frontend changes | Run frontend lint, Vitest coverage, the production build, and Playwright Chromium workflows. |
| API contract changes | Changes under `core/src/coyote/contracts/` or `api/src/coyote_api/interfaces/http/` also run frontend checks because they can change consumed payloads or routes. |
| Deployment changes | Compose, proxy, and container build changes run all scopes because they can alter every runtime surface. |
| Documentation changes | Run Markdown lint, internal-link validation, and a strict MkDocs build. |
| Workflow changes | Run all scopes so CI changes validate the complete execution path. |
| Manual full check | `workflow_dispatch` runs backend, frontend, and documentation checks regardless of changed paths. |
| Database integration | Select `database_integration` on a manual run to start the disposable MongoDB transaction job. Automatic runs do not start that job. |
| Browser installation | Cache the Chromium browser bundle; install only its system libraries on cache hits. |
| Artifacts | Do not upload coverage from pull requests. Retain default-branch and manual coverage artifacts for seven days. |

The changelog check is part of the same quality job, avoiding a second runner
for every pull-request update. A maintainer may apply the
`skip-changelog-update` label when a change has no release-facing effect.
Label changes trigger only the sensitive-data and changelog checks; they do
not repeat backend, frontend, or documentation suites. Repositories upgrading
from an earlier configuration should remove the retired
`CHANGELOG Reminder / changelog` check from branch protection.

The `bootstrap-and-ingest-check` workflow runs only on manual dispatch. It builds a complete
stage stack with a disposable MongoDB profile, validates the
`SCRIPT_NAME` reverse-proxy path, creates the initial account, imports baseline
collections, ingests the approved synthetic bundle, and verifies the ready
sample through the running API. Its container logs are uploaded only on
failure and retained for three days.

## Browser And External API Contracts

The quality suite and deployment checks cover these boundaries:

| Layer | Command or workflow | Responsibility |
| --- | --- | --- |
| Python contracts | `PYTHONPATH=. pytest -q` | Pydantic contracts, API routes, rule evaluation, authorization, persistence adapters, external-client payload handling, and UI route metadata. |
| Frontend units | `cd frontend && npm run test:coverage` | Pure frontend helpers with JSON-summary and LCOV output. |
| Browser routes | `cd frontend && npm run test:e2e` | React routing, rendered form behavior, and user-facing success/error states using deterministic API fixtures. |
| Deployment smoke | `cd frontend && COYOTE4_E2E_BASE_URL=https://host/prefix/ npm run test:e2e:real` | Real proxy-prefix routing and API integration; authenticated checks run when controlled credentials are supplied. |
| Composed workflow | `bootstrap-and-ingest-check` workflow | Docker networking, authentication, MongoDB, Celery ingestion, and ready-sample projection through the running API. |

The OncoKB and ClinPGx client tests use fixture responses for successful payloads,
unexpected payload shapes, and HTTP failures. Public knowledgebase responses are
never silently promoted to clinical evidence after a failed or malformed request.

### Required focused commands

```bash
# API, unit, and architecture-boundary tests
PYTHONPATH=. .venv/bin/pytest -q

# Full browser route suite with deterministic API fixtures
npm --prefix frontend run test:e2e

# One focused sample analysis availability contract
npm --prefix frontend run test:e2e -- sample-analysis-tabs.spec.ts

# Real deployment and reverse-proxy smoke checks
COYOTE4_E2E_BASE_URL=https://localhost/coyote4_dev/ \
npm --prefix frontend run test:e2e:real
```

## Standards for New Feature Development

- **Logic Separation**: Cover clinical decisions in `core/src/coyote/domain` with focused positive, negative and regression cases; the configured family coverage gate applies.
- **Boundary Mocking**: API and integration tests should isolate external network dependencies with focused fixtures.
- **Payload Alignment**: Validation fixtures must reflect the current Pydantic
  contracts and use deterministic, de-identified payloads. They must not rely
  on live database snapshots.

## Authorization and Permission Validation

All permission-gate testing must operate at the logical boundary being enforced:

- **API Access**: Use the `api_user` mocks to validate FastAPI `Depends` authentication and RBAC logic.
- **UI visibility**: Verify selective rendering in the React layer with API-shaped fixtures.
- **Constraint Matching**: Test datasets must define role-derived allow/deny permission arrays to verify both positive and negative authorization outcomes.
- **Shipped RBAC Matrix**: `api/tests/http/test_rbac_complete_route_matrix.py` must pass. It covers
  every active seeded permission, bundled role, and registered `require_access` API endpoint.

## Performance Checks

Use the optional [self-hosted Locust workflow](load-and-capacity-testing.md) for HTTP performance
measurements against an isolated synthetic deployment. It is separate from the normal
quality gate and does not render React; Playwright retains ownership of browser behavior.
Run through Nginx and the configured `SCRIPT_NAME` with ordinary sessions and CSRF.
Keep read workloads separate from explicitly enabled comment or ingest writes; do not
publish rules or finalize reports as load actions.

Record workload mix, concurrency, duration, dataset size, cache-cold and cache-warm
phases, p95/p99 latency, and errors including `429`. Async acceptance timing must be
paired with completion and queue measurements. The existence of this harness or a
passing unit suite is not evidence that a release has been load tested.

The separate CI `loadtest-smoke` job installs only `requirements-load.txt`
(Locust `2.46.5`, from the optional `load` dependency group) and runs
`python tests/load/smoke_test.py` against synthetic HTTP responses. It checks harness
behavior without a real application database; it is neither a deployment load run
nor a measurement of Coyote4 capacity.

See also:

- [System Relationships](../architecture/resource-relationships.md)
- [Browser And Release Validation](browser-and-release-validation.md)
