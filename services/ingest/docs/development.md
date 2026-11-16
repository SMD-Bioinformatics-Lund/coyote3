# Development

From the repository root, install the uv workspace in editable mode:

```bash
uv sync --all-packages --group test --group dev --group docs
scripts/quality/run_package_tests.sh ingest --smoke
scripts/quality/run_package_tests.sh ingest --coverage
```

Source edits are immediately available to new Python processes. Restart a running
worker after editing worker code. Wheel rebuilds are for artifact verification and
deployment, not each local source edit.

This package's [pyproject.toml](../pyproject.toml) owns its pytest configuration,
complete-source branch coverage and coverage floor. Run the complete suite with
the `worker` and `test` extras installed:

```bash
cd services/ingest
python -m pytest -q
python -m pytest --cov --cov-report=term-missing
```

`tests/unit` checks submission receipts, transport failures, credential handling
and validation. `tests/worker` composes the core workflow with synthetic MongoDB
repositories and mocked server services. `tests/smoke` checks command parsing
without a live broker or database. No test connects to a remote
analysis host or submits a real sample.

Core-only execution and watcher regressions belong in `core/tests`; application
packaging, isolated installation and deployed integration belong in root tests.
Keep queue-name changes coordinated with API publication and beat scheduling.
