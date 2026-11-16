# Clinical workflow test fixtures

<!-- badges:start -->
![Scope: Tests and fixtures](https://img.shields.io/badge/Scope-Tests%20and%20fixtures-4F46A5?style=flat)
<!-- badges:end -->

These files validate the installable [demo bundle](../../../api/src/coyote_api/bootstrap/demo_data/clinical_workflows/README.md).
The application installer does not read this directory.

- `negative/`: invalid manifests referencing the shared demo raw files.
- `scenarios/`: finding labels and query-rule requests used by regression checks.
- `expected/`: deterministic ingest, review and report-preview outputs.

Replay and compare the expected results from the repository root:

```bash
PYTHONPATH=. .venv/bin/python scripts/quality/export_demo_workflows.py --check
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_clinical_workflow_demo.py
```

Run the exporter without `--check` to regenerate expected results after a deliberate
contract change. It uses an isolated in-memory database and the normal ingest parsers.
Expected records are comparison artifacts; do not import them into a deployment.
