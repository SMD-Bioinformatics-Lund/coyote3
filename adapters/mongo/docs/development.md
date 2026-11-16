# Develop the MongoDB adapter

From the repository root:

```bash
uv sync --all-packages --group dev --group test --group docs
scripts/quality/run_package_tests.sh mongo
uv build --package coyote-server
```

Adapter tests use synthetic records and do not require a running database.
They cover connection ownership, portable identities and driver-result conversion.
Shared integration tests cover the adapter with clinical workflows.

Changes to transactions, indexes, leases or concurrent revisions also require the
documented tests against a disposable transaction-capable MongoDB deployment.
Mocks do not establish real commit, rollback or retry guarantees.

Keep imports directed toward the core. The adapter must not import the API,
HTTP client or web framework. Preserve query scope, missing/null handling,
array correlation, numeric comparisons, audit evidence and saved snapshots.

The root `pyproject.toml` owns the shared server version, dependencies and build
configuration. The adapter's `pyproject.toml` owns only its test and coverage settings.
Record adapter changes in the component `CHANGELOG.md` and adopt the server wheel
through the application release selection.

## Test suites and coverage

`tests/unit` owns repository methods, query compilation, settings and transactions
using synthetic collections. `tests/integration` exercises the adapter's core-port
implementations with real core services and in-memory Mongo-style collections.
`tests/smoke` checks driver results, portable identities and integrity projection.
The full run includes all three suites. Helpers in `tests/mongo_test_support` use
explicit synthetic audit ownership and never import API settings or root fixtures.
Real commit, rollback, replication and authorization still require the application's
explicitly configured disposable-MongoDB integration suite.

From this directory, with the repository virtual environment activated:

```bash
python -m pytest -q tests/smoke
python -m pytest -q
python -m pytest -q --cov --cov-config=pyproject.toml --cov-report=xml
```

Coverage includes every module in `coyote_mongo`, including unexecuted modules, and
branches. Its independent baseline floor is 51%. Reports are local `.coverage` and
`coverage/coverage.xml`; add `--cov-report=html` for `coverage/html/`. Root integration
results do not contribute to this report. Smoke runs have no full-coverage gate.
