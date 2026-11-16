# Clinical workflow test fixtures

<!-- badges:start -->
![Scope: Tests and fixtures](https://img.shields.io/badge/Scope-Tests%20and%20fixtures-4F46A5?style=flat)
<!-- badges:end -->

These files validate the installable [demo bundle](../../../services/demo/src/coyote_demo/data/clinical_workflows/README.md).
The application installer does not read this directory.

- `negative/`: invalid manifests referencing the shared demo raw files.
- `scenarios/`: finding labels and query-rule requests used by regression checks.
- `expected/`: deterministic ingest, review and report-preview outputs.

Replay and compare the expected results from the repository root:

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit/test_clinical_workflow_demo.py
```

`support.py` exercises the normal ingest parsers in an isolated in-memory database.
Review expected results against the intended clinical behavior when contracts change.
Expected records are comparison artifacts; do not import them into a deployment.
