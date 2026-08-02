# Quality Engineering and Validation Standards

Repository Markdown is validated from the repository root with
`npm run docs:lint`. The root `.markdownlint-cli2.yaml` and root Node package
are intentionally repository-level tooling because their scope includes
`README.md`, `docs/`, and `.github/`; they do not belong to the frontend build.

## Testing Boundary Diagram

```text
Unit tests
  -> pure logic, contracts, helpers

API router tests
  -> request validation, auth dependencies, response shapes

Integration tests
  -> selected multi-component seams

Frontend unit tests
  -> pure formatting, routing, and UI helper behavior with LCOV output

Frontend browser tests
  -> route rendering and API contracts in Chromium

Docs build / lint / coverage gates
  -> repo-wide quality checks
```

This document defines the test and validation expectations for Coyote3.

## Formal Testing Tiers

The test suite is grouped by runtime boundary:

- **Unit Logic (`tests/unit`)**: pure functions, domain logic, contracts, and services.
- **REST Interface (`tests/api/routers`)**: HTTP boundary behavior and typed payload handling.
- **Integration Layer (`tests/integration`)**: cross-component checks that are still worth keeping.
- **Frontend (`frontend`)**: TypeScript build, linting, Vitest unit coverage,
  and Playwright route/API contract checks.

### API coverage organisation

API tests are grouped by the behavior they protect rather than by temporary
implementation or migration work:

| Location | Scope |
| --- | --- |
| `tests/unit` | Query construction, filter normalisation, schema contracts, reporting, ingest, and service behavior. |
| `tests/api/routers` | Route payloads, validation, permissions, and domain-specific endpoint behavior. |
| `tests/api` | Cross-router authentication, authorization matrices, OpenAPI taxonomy, route contracts, audit behavior, and rate limits. |
| `tests/integration` | Architecture boundaries and selected multi-component seams. |

The backend architecture guardrail is intentionally named for the boundary it
protects. It prevents new direct persistence coupling in HTTP and domain-core
layers; it is not a migration test and does not preserve retired migration
behavior.

### UI coverage organisation

Browser tests live in `frontend/tests/e2e`. They use deterministic intercepted
API responses, so they test route rendering and request dispatch without
depending on a live clinical database or external services.

Unit tests live beside the TypeScript modules they protect as
`*.test.ts`. Vitest writes terminal, JSON summary, and LCOV reports to
`frontend/coverage/`. The report includes frontend library modules even when a
module currently has no tests, so the percentage remains an honest expansion
metric rather than only measuring files that already have coverage.

Vitest enforces global non-regression floors over the complete declared source
scope: 75% statements, 60% branches, 65% functions, and 77% lines. These are
release gates rather than completion targets. New modules included in the
scope must bring tests with them, and the floors should rise only after the
measured suite has enough deterministic margin to remain stable across local
and CI environments.

The frontend suite uses four complementary levels:

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
| Sample analysis tabs | ASPC analysis selection, sample modality, intent visibility, and deferred endpoint requests. |
| Primary application workflows | Dashboard composition, live/reported sample state, disabled-module routing, matrix search, profile persistence, and notification broadcasting. |
| Route registry contracts | Every declared UI route identifies its backend dependencies and empty/error behavior. |

Frontend unit ownership is divided by behavior so regressions are attributable
to a clear boundary:

| Unit-test area | Protected behavior |
| --- | --- |
| API client | Typed envelope unwrapping, JSON and form requests, structured validation errors, non-JSON gateway failures, and expired-session redirects. |
| Finding actions | Single and bulk mutation endpoints, tier changes, per-finding CNV requests, cache keys, and empty-selection rejection. |
| Sample and finding normalization | Current and legacy payload shapes, intent-specific filters, tab-to-analysis mapping, fusion/translocation fields, flags, tiers, and caller labels. |
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
  --cov=api --cov-config=.coveragerc \
  --cov-report=term-missing --cov-report=xml:coverage.xml

# Execute static analysis and linting
PYTHONPATH=. python -m ruff check api tests scripts

# Check the strict typed security/account boundary
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
PYTHON_BIN=.venv/bin/python bash scripts/run_quality_suite.sh
```

This runs the backend unit/API/integration suites, scoped family coverage gates,
contract integrity checks, frontend linting, production build, browser tests,
and the strict documentation build. Browser tests start a local Vite server
with intercepted deterministic API responses. The quality suite does not
contact external knowledgebases or write to MongoDB.

To validate rendered Docker Compose configuration as part of the same gate:

```bash
PYTHON_BIN=.venv/bin/python \
COMPOSE_FILE=deploy/compose/docker-compose.dev.yml \
bash scripts/run_quality_suite.sh
```

!!! tip "Browser validation"

    This command verifies source and build behavior. Before promotion, follow
    the separate [Browser And Release Validation](browser_and_release_validation.md)
    procedure against a deployed environment and approved synthetic fixtures.

## Coverage Verification and Quality Gates

Coverage checks enforce minimum thresholds for key logic families.

```bash
# Execute multi-family coverage validation
PYTHON_BIN="$(command -v python)" PYTHONPATH=. bash scripts/run_family_coverage_gates.sh
```

The system applies a **75% minimum** to `api/domain/core`, with separate
thresholds for `api/application` and `api/interfaces/http`. It also enforces a
**75% minimum** over the clinical query-policy modules: DNA SNV, CNV, and
translocation query builders and the RNA fusion query builder. This is a
combined branch-aware gate, not a line-count exclusion. It protects the code
that decides which findings enter clinical review.

The gate first collects coverage for the `api` package, then evaluates each
family by its filesystem scope. This prevents a stale or renamed Python module
path from silently turning a family gate into a repository-wide total.

CI also publishes `coverage.xml` as the `backend-coverage` workflow artifact
and `frontend/coverage/lcov.info` as part of the `frontend-coverage` artifact.
The backend XML is the repository-wide observation report; family gates remain
the release controls for clinically important boundaries.

!!! note "Why the repository-wide percentage is not the clinical gate"

    A repository-wide percentage mixes clinical decisions with generated
    adapters, deployment helpers, administrative forms, and rarely used error
    paths. The quality gate therefore measures the clinical query policy as its
    own accountable unit. Broader family gates remain in place for application
    and HTTP code.

## Continuous Integration

CI should run these checks:

1. **Static Analysis**: Linting and formatting verification via the Ruff engine.
2. **Functional Validation**: Execution of the complete localized test suite.
3. **Boundary Verification**: Contract and schema consistency evaluation.
4. **Documentation Accuracy**: Strict-mode build verification of operational manuals.
5. **Compose Validation**: verification of Docker Compose configuration where relevant.
6. **UI/API Contract Registry**: every literal API operation declared by the
   React route registry must resolve to a FastAPI route. This detects stale
   page contracts before manual browser validation.
7. **Strict Type Boundary**: `mypy` strict mode covers authentication,
   password, notification-email, and user-management modules. New modules are
   added to the configured boundary only after they pass strict mode; the
   boundary must not be weakened to admit a module.
8. **Coverage Artifacts**: backend XML and frontend LCOV results are retained
   with each workflow run for review and trend integration.

## Browser And External API Contracts

The quality suite combines three distinct validation layers:

| Layer | Command or workflow | Responsibility |
| --- | --- | --- |
| Python contracts | `PYTHONPATH=. pytest -q` | Pydantic contracts, API routes, rule evaluation, authorization, persistence adapters, external-client payload handling, and UI route metadata. |
| Frontend units | `cd frontend && npm run test:coverage` | Pure frontend helpers with JSON-summary and LCOV output. |
| Browser routes | `cd frontend && npm run test:e2e` | React routing, rendered form behavior, and user-facing success/error states using deterministic API fixtures. |
| Deployment smoke | `cd frontend && COYOTE3_E2E_BASE_URL=https://host/prefix/ npm run test:e2e:real` | Real proxy-prefix routing and API integration; authenticated checks run when controlled credentials are supplied. |
| Composed workflow | `bootstrap-and-ingest-check` workflow | Docker networking, authentication, MongoDB, Celery ingestion, and ready-sample projection through the running API. |

The OncoKB and ClinPGx client tests use fixture responses for successful payloads,
unexpected payload shapes, and HTTP failures. Public knowledgebase responses are
never silently promoted to clinical evidence after a failed or malformed request.

### Required focused commands

```bash
# API, unit, and architecture-boundary tests
PYTHONPATH=. .venv/bin/pytest tests/unit tests/api tests/integration -q

# Full browser route suite with deterministic API fixtures
cd frontend && npm run test:e2e

# One focused sample analysis availability contract
cd frontend && npm run test:e2e -- sample-analysis-tabs.spec.ts

# Real deployment and reverse-proxy smoke checks
cd frontend && \
COYOTE3_E2E_BASE_URL=https://localhost/coyote3_dev/ \
npm run test:e2e:real
```

## Standards for New Feature Development

- **Logic Separation**: Pure algorithmic logic within `api/domain/core` must maintain 100% test coverage through isolated unit tests.
- **Boundary Mocking**: API and integration tests should isolate external network dependencies with focused fixtures.
- **Payload Alignment**: Validation fixtures must reflect the current Pydantic
  contracts and use deterministic, de-identified payloads. They must not rely
  on live database snapshots.

## Authorization and Permission Validation

All permission-gate testing must operate at the logical boundary being enforced:

- **API Access**: Use the `api_user` mocks to validate FastAPI `Depends` authentication and RBAC logic.
- **UI visibility**: Verify selective rendering in the React layer with API-shaped fixtures.
- **Constraint Matching**: Test datasets must define role-derived allow/deny permission arrays to verify both positive and negative authorization outcomes.

## Performance Checks

Use dedicated profiling or staged environment testing when you need performance numbers.

See also:

- [System Relationships](../architecture/system_relationships.md)
- [Browser And Release Validation](browser_and_release_validation.md)
