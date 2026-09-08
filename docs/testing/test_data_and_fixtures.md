# Validation Datasets and Test Fixtures

Use synthetic fixtures to test ingestion, API responses and collection contracts.

## Fixture Infrastructure

Test data lives in these directories:

- `demo_data/ingest/`: Synthetic input files for ingest tests.
- `demo_data/collections/`: Example documents for collection contract tests.
- `tests/fixtures/api/`: API fixtures and payload snapshots.

## Canonical Ingestion Datasets

The `demo_data/ingest` directory contains synthetic ingest inputs:

- VCF files for small variants.
- JSON files for copy-number and coverage data.
- PNG images for report tests.
- YAML ingest manifests.

**Repository rule**: Public test data must be synthetic or fully de-identified.
It must not contain protected health information (PHI) or clinical patient
identifiers.

The pre-commit `sensitive-data` guard scans staged content before every commit.
It blocks common credential formats, private environment and key files, known
clinical sample identifiers, Swedish personal identity numbers, local user
paths, and non-synthetic sample metadata in test data. It also reads compressed
`.gz` fixtures. Run a full tracked-file scan with:

```bash
python3 scripts/check_staged_sensitive_data.py --all-files
```

The guard is part of the tracked Git hook chain. Enable that chain once per
clone with `git config core.hooksPath .githooks && chmod +x .githooks/pre-commit`;
do not use `pre-commit install`, which would replace the repository wrapper.

The guard is a prevention control, not proof of de-identification. Fixture
owners must still document synthetic provenance and reviewers must reject
clinical source data even when it does not match a detection pattern.

## Application Bootstrap And Demo Collections

Application bootstrap and test fixtures have separate ownership:

| Location | Purpose | Production bootstrap |
| --- | --- | --- |
| `api/config/bootstrap/rbac` | Application permissions and built-in roles | Yes; installed for an empty deployment |
| `api/config/bootstrap/reference` | Compressed HGNC and VEP reference snapshots | Yes; each collection is loaded only when empty |
| `api/config/bootstrap/demo_center` | Synthetic ASP, ASPC, and ISGL definitions | Optional validation baseline only |
| `demo_data/collections/all_collections_dummy` | Synthetic documents spanning collection contracts | No; tests and demonstrations only |
| `demo_data/ingest` | Synthetic DNA/RNA manifests and artifacts | No; ingest validation only |

The first-deployment flow and empty-collection protection are described in
[Initial Deployment Checklist](../operations/initial_deployment_checklist.md).

### Validation Commands

Validate the example collection documents with:

```bash
PYTHONPATH=. python -m pytest -q tests/unit/test_db_dummy_fixture.py
```

## Contract checks

Run the repository's contract checks after changing schemas or fixtures:

```bash
# Execute contract consistency validation
PYTHON_BIN="$(command -v python)" bash scripts/check_contract_integrity.sh
```

The script checks:

- Runtime dependency exports against `pyproject.toml`.
- Prohibited imports, debug output and transitional code markers.
- Shell scripts and internal documentation links.
- Generated collection contracts and the permission catalog against their sources.

It does not connect to MongoDB or inspect samples. Fixture validity and relationships
between assay records are covered by the relevant tests and seed validation tools.

## Maintaining fixtures

When adding or changing fixtures:

1. Include only the records needed for the test.
2. Use synthetic data, not copied or renamed patient records.
3. Keep nested fields consistent with the current contracts.
4. Run the relevant fixture tests and `check_contract_integrity.sh` before merging.

## Browser Validation Fixtures

Maintain a small, approved fixture set that supports browser release checks
without external network dependencies or patient data:

| Fixture capability | Required for validating |
| --- | --- |
| Paired DNA sample with SNVs and indels | filtering, sorting, tiers, comments, reporting, and exports |
| CNV sample with profile image | CNV table, resizable image pane, rotation, and reporting actions |
| Coverage data with probes/exons | gene click-through, low coverage, and blacklist workflow |
| Fusion/translocation sample | structural tables, detail context, and table-specific bulk actions |
| Biomarker input | overview/header biomarker presentation and reporting sections |
| Report template | preview, save, HTML, PDF, artifact metadata, and immutable snapshots |
| Restricted/admin accounts | denied actions, role visibility, audit events, and application controls |

The browser protocol and expected checks are defined in
[Browser And Release Validation](browser_and_release_validation.md).
