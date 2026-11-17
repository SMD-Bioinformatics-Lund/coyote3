# Develop the API host

From the repository root:

```bash
uv sync --all-packages --group dev --group test --group docs
scripts/quality/run_package_tests.sh api
uv build --package coyote-server
```

For fast API and worker iteration, use native editable installs and the application's
`install.sh watch` command. Docker development mounts backend sources but requires
explicit service restarts after Python changes; rebuild and recreate services when
dependencies or image contents change. See [editable development](../../docs/sdk/uv-development.md).
A normal wheel build must
include host assets and run outside the checkout without source-path overrides.

Keep routes focused on transport and delegation. Changes to authentication,
permissions, center selection or startup order need success and failure tests.
Changes affecting clinical behavior also need the shared application regressions.

The root `pyproject.toml` owns the shared server version, dependencies and console
entry point. The API's `pyproject.toml` owns only its test and coverage settings.
Update the component `CHANGELOG.md` for API changes. The application release process
selects and verifies core, server, Relay, Atlas and Demo wheels. The independent
Python client is not installed by the application.

## Test suites and coverage

`tests/unit` owns host configuration, workers, security and report branding.
`tests/http` owns route behavior, validation and permissions. `tests/smoke` checks
the health entry point and settings projection without starting infrastructure.
All are included in a full run. Synthetic helpers belong to `tests/api_test_support`;
they use installed core and adapter code and packaged resources, without importing
another project's tests. Frontend/API contract checks belong at the repository root.

From this directory, with the repository virtual environment activated:

```bash
python -m pytest -q tests/smoke
python -m pytest -q
python -m pytest -q --cov --cov-config=pyproject.toml --cov-report=xml
```

Coverage measures the complete `coyote_api` namespace and branches with a 75% floor.
It writes `.coverage` and `coverage/coverage.xml` here; add `--cov-report=html` for
`coverage/html/`. Smoke runs do not enforce the full-suite coverage floor.
