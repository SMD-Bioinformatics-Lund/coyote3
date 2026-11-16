# Develop the HTTP client

For isolated work, run from this project directory:

```bash
python -m pip install -e ".[test]"
python -m pytest tests
```

For shared repository work:

```bash
uv sync --all-packages --group dev --group test --group docs
scripts/quality/run_package_tests.sh client
uv build --package coyote-pyclient
```

Client tests use HTTPX transports and synthetic responses without a running
server. Shared contract tests check endpoints against the API specification.
The package must remain importable without the core, adapter or API installed.

Keep synchronous and asynchronous behavior aligned for authentication, timeouts,
pagination, mutations and error handling. Preserve response validation and additive
server fields. Source edits require restarting a consuming process; metadata
changes require reinstalling or synchronizing the environment.

Version and dependencies belong to `pyproject.toml`. Record changes in
`CHANGELOG.md`. Package-index publication is separate from local development.

## Test suites and coverage

`tests/unit` checks sync/async authentication, resource access, validation and transport
failures using HTTPX mock transports. `tests/smoke` checks authenticated report-preview
downloads without saving or contacting a server. Full runs include both suites.
Neither suite imports the API, database adapter, core library or repository tests.

From this directory, after installing `.[test]`:

```bash
python -m pytest -q tests/smoke
python -m pytest -q
python -m pytest -q --cov --cov-config=pyproject.toml --cov-report=xml
```

Coverage includes the complete `coyote_pyclient` namespace and branches with an 81%
baseline floor. Local outputs are `.coverage` and `coverage/coverage.xml`; add
`--cov-report=html` for `coverage/html/`. Smoke runs do not enforce full-suite coverage.
