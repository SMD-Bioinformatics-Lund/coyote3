# Develop the API host

From the repository root:

```bash
uv sync --all-packages --group dev --group test --group docs
scripts/quality/run_package_tests.sh api
uv build --package coyote-api
```

Use editable installs for Python work and reload the API after changes. Restart
workers separately when their imported code changes. A normal wheel build must
include host assets and run outside the checkout without source-path overrides.

Keep routes focused on transport and delegation. Changes to authentication,
permissions, center selection or startup order need success and failure tests.
Changes affecting clinical behavior also need the shared application regressions.

The package's `pyproject.toml` owns its version, dependencies and console entry
point. Update `CHANGELOG.md` for package changes. The application release process
selects and verifies the complete core/adapter/API combination.

## Test suites and coverage

`tests/unit` owns host configuration, workers, security and report branding.
`tests/http` owns route behavior, validation and permissions. `tests/smoke` checks
the health entry point and settings projection without starting infrastructure.
All are included in a full run. Synthetic helpers belong to `tests/api_test_support`;
they use declared core/adapter dependencies and packaged resources, without importing
another project's tests. Frontend/API contract checks belong at the repository root.

From this directory, after installing `.[test]`:

```bash
python -m pytest -q tests/smoke
python -m pytest -q
python -m pytest -q --cov --cov-config=pyproject.toml --cov-report=xml
```

Coverage measures the complete `coyote_api` namespace and branches with a 75% floor.
It writes `.coverage` and `coverage/coverage.xml` here; add `--cov-report=html` for
`coverage/html/`. Smoke runs do not enforce the full-suite coverage floor.
