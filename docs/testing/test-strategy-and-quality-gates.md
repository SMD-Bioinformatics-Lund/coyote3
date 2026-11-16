# Test strategy and quality gates

Tests protect clinical behavior, permissions, contracts and recovery. Each component
owns its tests; root tests verify application composition and cross-component behavior.
Use focused checks during development and comprehensive validation for a release.

## Test boundaries

![Test layers and quality gates](../assets/diagrams/test-coverage-map.svg)

### Python suite ownership

| Location | Scope |
| --- | --- |
| `core/tests` | Clinical rules, filtering, portable contracts and application workflows |
| `api/tests` | Host configuration, authentication, HTTP contracts and permission scope |
| `adapters/mongo/tests` | Query compilation, repositories and persistence integration |
| `clients/python/tests` | HTTP transport, authentication, client resources and failures |
| `services/relay/tests` | Submission tools, manifests and ingestion worker composition |
| `services/atlas/tests` | Reference validation, resources and publication |
| `services/demo/tests` | Synthetic resources and isolated installation safeguards |
| Root `tests/` | Package composition, transactions, architecture and operational tooling |
| `frontend/` | Vitest component/unit tests and Playwright application workflows |

Root `pytest.ini` collects the maintained Python suites. Package-local configuration
allows each component to run independently with its own coverage report. Package
helpers do not import another component's test helpers; root integration fixtures
may compose component behavior. Use explicit test paths to avoid unnecessary collection.

### Fast smoke checks

Run from the repository root after [editable installation](../sdk/uv-development.md):

```bash
bash scripts/quality/run_package_tests.sh all --smoke
.venv/bin/python -m pytest -q tests/smoke --no-cov
npm --prefix frontend run test:smoke
```

These checks cover basic contracts, configuration, API/client composition, package
resources and shared confirmation behavior. They use synthetic inputs and in-process
transports. They do not start application services or contact a deployment database.
Each smoke test also belongs to its component's full suite.

The GitHub `quality` workflow runs these commands, Python lint, release metadata
validation and the sensitive-file guard. It runs for PRs into `dev` and `master`,
pushes to `master`, and manual dispatch. One job uses cached dependencies and cancels
superseded runs. It has no full coverage, browser, container, load or database jobs.

Smoke success is early feedback, not release approval or complete clinical validation.

### Independent package coverage

```bash
bash scripts/quality/run_package_tests.sh core
bash scripts/quality/run_package_tests.sh mongo --coverage
bash scripts/quality/run_package_tests.sh all --coverage
```

The runner changes to each component directory and uses its own pytest and coverage
configuration. It accepts `core`, `api`, `mongo`, `client`, `relay`, `atlas`, `demo`
or `all`. Source remains editable; no wheel rebuild is needed for a test change.

Each component's `pyproject.toml` defines its coverage floor and runtime scope.
Coverage includes unexecuted modules and branches; root integration observations
do not contribute to an independent component report. Keep reports local to their
component, and do not lower a threshold to conceal a regression.

## Primary execution commands

Use `.venv/bin/python -m pytest -q PATH` for an affected Python suite. For frontend changes:

```bash
npm --prefix frontend run lint
npm --prefix frontend run test:unit
npm --prefix frontend run build:verified
npm --prefix frontend run test:e2e
```

Vitest covers state, formatting and component behavior. Playwright covers user flows
with controlled API fixtures. Use the separate real-deployment browser configuration
only with an explicitly isolated acceptance environment. See
[browser and release validation](browser-and-release-validation.md).

## Unified quality gate

Run the comprehensive local gate for a release candidate or a substantial cross-component change:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh
```

It runs backend and client suites, package and clinical-family coverage, typing and
contract checks, frontend lint/coverage/build/browser tests and documentation checks.
Install the development dependencies and Playwright browser first, as described in
[developer setup](../getting-started/developer-environment.md). The gate does not start
MongoDB or prove a deployed center's acceptance criteria.

Render deployment configuration as part of the gate when Compose files change:

```bash
COMPOSE_FILES="deploy/compose/docker-compose.yml deploy/compose/docker-compose.stage.yml" \
COMPOSE_ENV_FILE=deploy/env/example.env \
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh
```

### Database integration

With `mongod` installed, the explicit runner creates disposable loopback-only replicas:

```bash
.venv/bin/python scripts/quality/run_transaction_tests.py -- -q tests/integration
```

It supplies test settings and terminates its child processes afterwards. These tests
cover transaction and authenticated runtime-permission behavior that an in-memory
store cannot prove. They are not part of GitHub CI. Never point them at production.
Check skipped tests in release evidence and explain whether their required environment
was available. See [deployment acceptance](browser-and-release-validation.md) for
real service and report checks.

## Coverage verification and quality gates

The repository coverage configuration and component configurations define the
required floors. Clinically important query, application and HTTP boundaries also
have family gates in `scripts/quality/run_family_coverage_gates.sh`:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_family_coverage_gates.sh
```

The comprehensive quality runner reuses the backend coverage database with
`--from-existing`; standalone execution collects coverage before evaluating families.
Aggregate coverage cannot replace checks for clinical selection and report behavior.
CI does not upload coverage artifacts. Retain release reports with the candidate's
version and artifact identifiers in the release validation record.

## Documentation checks

```bash
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python scripts/docs/check_operational_examples.py
.venv/bin/python -m mkdocs build --strict
.venv/bin/python scripts/docs/check_built_site.py
```

Review relevant generated references when contracts change. Read rendered pages for
clarity and inspect changed SVG assets in both themes. Do not maintain separate test
suites for logo generation, documentation phrasing or coding-session scaffolding.
Google-style docstrings should describe actual behavior; code review checks their
accuracy and Ruff checks formatting.

## Release evidence

Record the candidate commit, component versions, commands and results, required
approvals, known limitations and recovery procedure. A skipped or unperformed check
is not a pass. Clinical wording, classification rules, report selection and assay
configuration require the center's validation and approval before use.

See the [release workflow](../project/releasing.md) and
[upgrade procedure](../deployment/application-upgrades.md).
