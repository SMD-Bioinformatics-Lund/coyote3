# Demo data bundle

Demo samples use the same YAML manifest and raw analysis formats as pipeline
ingestion. The packaged source is `demo_data/clinical_workflows/`. The installer
reads these files through `InternalIngestService`; it does not import stored
sample or finding snapshots.

Use the [installation workflow](clinical-workflow-demo.md) to load the bundle
into an isolated deployment. All sample identities and measurements are synthetic.

## Files and ownership

| Path within the bundle | Content | Consumer |
| --- | --- | --- |
| `starter/manifests/` | Connected starter DNA and RNA sample manifests | Initial installation and the demo installation page |
| `manifests/` | Additional DNA/RNA workflow manifests | Demo installation page and offline replay |
| `raw/` | VCF, JSON and image inputs referenced by the manifests | Normal ingest parsers |
| `starter/setup/`, `setup/` | Assays, subpanels, configurations, gene lists and published demo rules | Validated demo configuration installation |
| `negative/` | Invalid bundles for rejection cases | Tests only |
| `scenarios/` | Finding labels and query draft requests | Review exercises and regression assertions |
| `expected/after_ingest/` | Generated, portable collection snapshots | Snapshot comparison and persisted-shape examples |
| `expected/after_review/` | Illustrative classifications and comments | Review assertions and contract examples |
| `expected/report_previews.json` | Generated report section output | Reporting regression assertions |

Keep source inputs in this bundle when adding scenarios. Tests that need parsed
clinical evidence replay the manifests; expected snapshots are comparison outputs.
Collection-level schema examples remain in `demo_data/collections/` and are not
installation inputs.

## Sample manifest format

This is the packaged `starter/manifests/rna_fusion.yaml` input. Paths are relative
to that manifest within the bundle; the demo installer resolves them to allowlisted
files inside the package before calling ingest.

```yaml
name: DEMO_STARTER_RNA
assay: demo_starter_rna
subpanel: demo_starter_fusion
profile: testing
genome_build: 38
case_id: DEMO_CASE
control_id: null
clarity_case_id: demo_rna_case_clarity
clarity_case_pool_id: demo_rna_pool
sample_no: 1
paired: false
sequencing_scope: panel
omics_layer: rna
sex: female
sequencing_technology: Illumina
read_mode: PE
pipeline: SyntheticFixture
pipeline_version: '1.0'
case_ffpe: false
case_sequencing_run: DEMO_RUN
case_reads: 1000000
case_purity: null
fusion_files: ../../raw/fusions.json
qc: ../../raw/qc.json
case_bam: null
case_bai: null
control_bam: null
control_bai: null
```

The [manifest reference](../reference/sample-manifest.md) defines required,
conditional and optional fields. Pipeline/API ingestion follows its own path and
upload contract; relative path resolution above belongs to the packaged demo
installer. Null BAM/BAI entries declare that this bundle has no alignment resources.

## Analysis file formats

| Packaged input | Manifest key | Format reference |
| --- | --- | --- |
| `raw/dna.vcf`, `raw/dna_unpaired.vcf` | `vcf_files` | [VEP-annotated small-variant VCF](../reference/ingest-files/small-variants-vcf.md) |
| `raw/cnvs.json` | `cnv` | [Copy-number JSON](../reference/ingest-files/copy-number-json.md) |
| `raw/translocations.vcf` | `transloc` | [SnpEff-annotated structural VCF](../reference/ingest-files/translocations-vcf.md) |
| `raw/coverage.json` | `cov` | [Gene and exon coverage JSON](../reference/ingest-files/coverage-json.md) |
| `raw/biomarkers.json` | `biomarkers` | [HRD, MSI and TMB JSON](../reference/ingest-files/biomarkers-json.md) |
| `raw/fusions.json` | `fusion_files` | [Fusion caller evidence JSON](../reference/ingest-files/fusions-json.md) |
| `raw/expression.json` | `expression_path` | [Expression JSON](../reference/ingest-files/expression-json.md) |
| `raw/classification.json` | `classification_path` | [Classification JSON](../reference/ingest-files/classification-json.md) |
| `raw/qc.json` | `qc` | [RNA QC JSON](../reference/ingest-files/quality-control-json.md) |
| `raw/pgx.json` | `pgx` | [Pharmacogenomics JSON](../reference/ingest-files/pharmacogenomics-json.md) |
| `raw/cnvprofile.png` | `cnvprofile` | [Image resources](../reference/ingest-files/images-and-alignments.md) |

Each format reference includes the accepted root structure, fields, units and a
synthetic example. Do not substitute collection exports for these producer files.

## Offline replay and mongomock

From the repository root, with development dependencies installed:

```bash
# Parse the raw bundle and compare generated snapshots with the checked-in outputs.
PYTHONPATH=. .venv/bin/python scripts/quality/export_demo_workflows.py --check

# Exercise query, transcript, installation and reporting behavior on those inputs.
PYTHONPATH=. .venv/bin/pytest -q \
  tests/unit/test_clinical_workflow_demo.py \
  tests/unit/test_demo_installation.py --no-cov
```

The exporter creates a fresh mongomock database, loads validated setup records and
the bundled reference genes, and ingests the positive manifests. Tests reuse that
replay. It reads no database URI or credentials and makes no MongoDB connection.
Negative manifests are exercised separately by rejection tests.

To update expected outputs after an intentional parser or contract change, run the
exporter without `--check` and review the snapshot diff. Generated snapshots replace
runtime IDs and timestamps consistently; their evidence comes from the raw files.

Mongomock replay covers parsing and application behavior. Replica-set tests cover
transactions and recovery; API and browser tests cover authorization and user flows.
See the [test strategy](test-strategy-and-quality-gates.md).
