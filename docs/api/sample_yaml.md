# Sample YAML Guide

This page describes the YAML contract used when ingesting a sample bundle through the internal ingest APIs and helper scripts.

For the exact persisted `samples` collection contract, see [API / Collection Contracts](collection_contracts.md).
For endpoint usage, see [API / Ingestion API](ingestion_api.md).
For the raw VCF and JSON file shapes referenced by the YAML, see [API / Sample Input Files](sample_input_files.md).

## Purpose

The sample YAML is the top-level ingest manifest. It tells Coyote3:

- which sample is being ingested
- which assay/profile the sample belongs to
- whether the bundle is DNA or RNA
- which data files belong to the sample
- which VEP metadata version should be used for consequence translation and filtering

The YAML is parsed first, validated through the backend sample contract, and then written into the stored sample document. In other words, fields such as `vep_version` travel from the YAML into `samples` and are then used by downstream DNA/reporting code.

## Sample filter initialization

`samples.filters` is the runtime source of truth once a sample exists.

- If a sample is created without a `filters` document, ingest initializes `samples.filters` from the resolved ASPC defaults.
- If a user resets filters in the UI, the current ASPC defaults are written back into `samples.filters`.
- Otherwise, findings and reporting workflows use the stored `samples.filters` document exactly as saved.
- Empty lists inside `samples.filters` are treated as intentional values, not as a signal to fall back to ASPC defaults.

## General rules

- The YAML must decode to a single object.
- `omics_layer` controls which file keys are allowed.
- `DNA` samples must only use DNA file keys.
- `RNA` samples must only use RNA file keys.
- File paths must be readable from the API runtime environment.
- `profile` must be one of `production`, `development`, `testing`, or `validation`.
- `vep_version` should match a `vep_metadata.vep_id` document already seeded in Mongo.
- ASP controls which sample file keys are expected through `assay_specific_panels.expected_files`.
- During ingest, file keys not listed in the assay's `expected_files` are ignored.

## Shared top-level fields

These keys are common and usually make sense for both DNA and RNA sample bundles:

- `name`: sample name stored in `samples.name`
- `assay`: assay identifier
- `subpanel`: optional assay subpanel
- `profile`: assay environment/profile
- `case_id`: case sample identifier
- `control_id`: optional control sample identifier
- `sample_no`: `1` for single-sample, `2` for paired case/control
- `paired`: `true` for paired case/control, otherwise `false`
- `genome_build`: genome build, for example `38`
- `vep_version`: VEP metadata version, for example `"103"` or `"110"`
- `sequencing_scope`: `panel`, `wgs`, or `wts`
- `omics_layer`: `DNA` or `RNA`
- `sequencing_technology`: optional sequencing platform label
- `pipeline`: pipeline name
- `pipeline_version`: pipeline version string

Optional case/control metadata fields:

- `clarity_case_id`
- `clarity_control_id`
- `clarity_case_pool_id`
- `clarity_control_pool_id`
- `case_ffpe`
- `control_ffpe`
- `case_sequencing_run`
- `control_sequencing_run`
- `case_reads`
- `control_reads`
- `case_purity`
- `control_purity`

## DNA sample YAML

DNA bundles may include these file keys:

- `vcf_files`
- `cnv`
- `cnvprofile`
- `cov`
- `biomarkers`
- `transloc`

The assay can narrow that list through `assay_specific_panels.expected_files`. For example, if an ASP only expects `vcf_files`, `cov`, and `cnv`, then `cnvprofile`, `biomarkers`, and `transloc` paths in the YAML are ignored during ingest and do not show up in the sample edit page.

Example:

```yaml
subpanel: "hematology_myeloid"
name: "CASE_DEMO"
clarity_case_id: "GEN_DEMO_CASE"
clarity_control_id: "GEN_DEMO_CTRL"
clarity_case_pool_id: "POOL_DEMO_001"
clarity_control_pool_id: "POOL_DEMO_001"
genome_build: 38
vep_version: "103"
vcf_files: "tests/data/ingest_demo/generic_case_control.final.filtered.vcf"
sample_no: 2
case_id: "CASE_DEMO"
control_id: "CTRL_DEMO"
profile: "production"
assay: "assay_1"
sequencing_scope: "panel"
omics_layer: "DNA"
sequencing_technology: "Illumina"
pipeline: "SomaticPanelPipeline"
pipeline_version: "3.1.14"
case_ffpe: false
case_sequencing_run: "RUN_DEMO_001"
case_reads: 49039064
control_ffpe: false
control_sequencing_run: "RUN_DEMO_001"
control_reads: 45889968
paired: true
cnv: "tests/data/ingest_demo/generic_case_control.cnvs.merged.json"
cnvprofile: "tests/data/ingest_demo/generic_case_control.modeled.png"
cov: "tests/data/ingest_demo/generic_case_control.cov.json"
```

Notes:

- `vcf_files` is the primary SNV/indel input.
- `cov` is used for coverage/gene coverage views.
- `cnv` and `cnvprofile` are optional but common for panel DNA workflows.
- `vep_version` should match the annotation version used to produce the VCF.
- The raw file expectations for `vcf_files`, `cnv`, `cov`, `biomarkers`, and `transloc` are documented in [API / Sample Input Files](sample_input_files.md#dna-raw-input-files).

## RNA sample YAML

RNA bundles may include these file keys:

- `fusion_files`
- `expression_path`
- `classification_path`
- `qc`

As with DNA, the assay panel can narrow these through `assay_specific_panels.expected_files`, and only the configured RNA file keys are used by ingest and shown in the sample edit page.

Example:

```yaml
name: "RNA_DEMO"
case_id: "RNA_DEMO"
sample_no: 1
paired: false
genome_build: 38
vep_version: "110"
profile: "production"
assay: "assay_rna_1"
sequencing_scope: "wts"
omics_layer: "RNA"
sequencing_technology: "Illumina"
pipeline: "RnaFusionPipeline"
pipeline_version: "1.4.0"
case_ffpe: false
case_sequencing_run: "RUN_RNA_001"
case_reads: 58200431
fusion_files: "/data/rna_demo.fusions.json"
expression_path: "/data/rna_demo.expression.json"
classification_path: "/data/rna_demo.classification.json"
qc: "/data/rna_demo.qc.json"
```

Notes:

- `fusion_files` is the main RNA variant-like input.
- `expression_path`, `classification_path`, and `qc` are optional but recommended for richer RNA workflows.
- RNA samples still carry `vep_version` so the sample document stays consistent across omics layers and future downstream consumers.
- A repo-local example is available at `tests/data/ingest_demo/generic_rna_sample.yaml`.
- The raw JSON file expectations for `fusion_files`, `expression_path`, `classification_path`, and `qc` are documented in [API / Sample Input Files](sample_input_files.md#rna-raw-input-files).

## VEP version behavior

`vep_version` is stored on the sample document and used at runtime to:

- resolve consequence-group mappings from `vep_metadata`
- load VEP consequence translations
- load variant-class translations for sample views and reports

This means the sample keeps an explicit record of which VEP metadata version should be used when reopening or reporting the sample later.

DNA report generation reads `sample.vep_version` directly during consequence resolution.

## Validation reminders

- DNA sample YAML must not include RNA file keys.
- RNA sample YAML must not include DNA file keys.
- `case_id` is always required.
- `control_id` must be omitted for single-sample ingest.
- `sample_no` must match the pairing mode.
- `vep_version` should be seeded in `vep_metadata` before ingest.
- If `filters` is omitted entirely during ingest, ASPC defaults are initialized onto the sample.
- Once stored, `samples.filters` is used as-is until reset or explicit update.
