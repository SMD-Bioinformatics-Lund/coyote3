# Develop the core

For isolated package work, run from this package directory:

```bash
python -m pip install -e ".[test]"
python -m pytest tests
```

For integrated work in the repository, use the shared editable workspace:

```bash
uv sync --all-packages --group dev --group test --group docs
scripts/quality/run_package_tests.sh core
uv build --package coyote-core
```

Restart a consuming process after changing imported Python modules. Dependency,
version and entry-point changes require reinstalling or synchronizing metadata.

Keep clinical logic independent of web frameworks, database drivers and task
queues. Add regression coverage for changed clinical conditions and failure
boundaries. Shared application tests verify the core with real adapter and host
implementations; package tests alone do not establish those integration guarantees.

The version and dependencies belong to this project's `pyproject.toml`.
Record package changes in `CHANGELOG.md`; application adoption is handled by
the repository release process.

## Test suites and coverage

`tests/unit` owns portable contracts, clinical rules, filtering, ingest and reporting
behavior. `tests/smoke` is a fast subset for settings and canonical variant identity.
Both are collected by a full package run. Synthetic helpers in `tests/core_test_support`
use core contracts and fake ports; they do not import a host, adapter or root tests.
The test hashing port is scoped to each case. Real persistence codecs are checked
by adapter and application integration suites.

From this directory, after installing `.[test]`:

```bash
python -m pytest -q tests/smoke
python -m pytest -q
python -m pytest -q --cov --cov-config=pyproject.toml --cov-report=xml
```

Coverage includes the entire `coyote` namespace, including unexecuted modules, and
branches. The independent baseline floor is 62%. Reports are local `.coverage` and
`coverage/coverage.xml`; add `--cov-report=html` for `coverage/html/`. Application
integration coverage and the stricter clinical gates are checked separately at
the repository root. Smoke runs do not enforce the full-suite coverage floor.
