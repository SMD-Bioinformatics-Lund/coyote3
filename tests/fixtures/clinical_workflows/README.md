# Clinical workflow test fixtures

These files validate the installable [demo bundle](../../../demo_data/clinical_workflows/README.md).
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
