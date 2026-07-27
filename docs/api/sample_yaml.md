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
- which curated database versions should be used for consequence translation and filtering

The YAML is parsed first, validated through the backend sample contract, and then written into the stored sample document. The VEP version is always supplied as `database_versions.vep` and is used by downstream DNA/reporting code.

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
- `database_versions.vep` should match a `vep_metadata.vep_id` document already seeded in Mongo when the sample has DNA small variants.
- ASP controls which sample file keys are expected through `assay_specific_panels.expected_files`.
- File keys not listed in the assay's `expected_files` are rejected before parsing. Coyote3 does not silently remove declared resources.
- Required files listed in `assay_specific_panels.required_files` must be present and readable.
- Optional files may be omitted. When an optional expected file is declared, it becomes part of that ingest transaction and must be parsed and written successfully.
- A sample is only marked `ready` after all declared database-backed resources have been written.

## Shared top-level fields

These keys are common to DNA and RNA sample bundles.

| Key | Required | Applies to | Meaning |
| --- | --- | --- | --- |
| `name` | Yes | DNA, RNA | Unique sample name shown in the UI and stored in `samples.name`. |
| `assay` | Yes | DNA, RNA | ASP business identifier. The ASP controls allowed, expected, and required file keys. |
| `subpanel` | No | DNA, RNA | Optional clinical subpanel. In storage this becomes `subpanel_id`. |
| `profile` | Yes | DNA, RNA | Runtime environment/profile. Allowed values are `production`, `development`, `testing`, and `validation`. |
| `case_id` | Yes | DNA, RNA | Case/sample identifier from the upstream pipeline or LIMS. |
| `control_id` | Paired only | DNA, RNA | Control sample identifier. Omit for single-sample ingest. |
| `sample_no` | Yes | DNA, RNA | `1` for single-sample ingest, `2` for paired case/control ingest. |
| `paired` | Yes | DNA, RNA | `true` when `control_id` is present, otherwise `false`. |
| `genome_build` | Recommended | DNA, RNA | Reference genome build, normally `38`. |
| `database_versions.vep` | DNA required for reporting | DNA, RNA | VEP metadata version used to resolve consequence groups, display labels, and report text. |
| `sequencing_scope` | Yes | DNA, RNA | Sequencing scope. Valid values are `panel`, `wgs`, or `wts`. |
| `omics_layer` | Yes | DNA, RNA | `DNA` or `RNA`. This controls which file keys are legal. |
| `sequencing_technology` | Recommended | DNA, RNA | Sequencing platform label, for example `Illumina`, `Nanopore`, or `PacBio`. |
| `pipeline` | Yes | DNA, RNA | Upstream pipeline name. |
| `pipeline_version` | Yes | DNA, RNA | Upstream pipeline version. Store as a string when possible. |
| `database_versions` | No | DNA, RNA | Optional curated reference/software versions. DNA ingest also extracts these from the VCF header when present. |
| `filters` | No | DNA, RNA | Optional initial filter state. If omitted, defaults are initialized from ASPC. |
| `files` | Yes | DNA, RNA | Manifest file map. Each declared file must use one of the keys allowed for the selected omics layer. |

Optional case/control metadata fields:

| Key | Applies to | Meaning |
| --- | --- | --- |
| `clarity_case_id` | DNA, RNA | Case sample Clarity/LIMS identifier. |
| `clarity_control_id` | Paired DNA/RNA | Control sample Clarity/LIMS identifier. |
| `clarity_case_pool_id` | DNA, RNA | Case pool identifier. |
| `clarity_control_pool_id` | Paired DNA/RNA | Control pool identifier. |
| `case_ffpe` | DNA, RNA | Whether the case sample is FFPE material. |
| `control_ffpe` | Paired DNA/RNA | Whether the control sample is FFPE material. |
| `case_sequencing_run` | DNA, RNA | Sequencing run identifier for the case sample. |
| `control_sequencing_run` | Paired DNA/RNA | Sequencing run identifier for the control sample. |
| `case_reads` | DNA, RNA | Number of reads for the case sample. |
| `control_reads` | Paired DNA/RNA | Number of reads for the control sample. |
| `case_purity` | DNA | Optional tumor purity estimate. |
| `control_purity` | Paired DNA | Optional control purity estimate, normally empty. |

## File declaration format

The concrete keys below are the current center profile from
`api/config/center/clinical_vocabulary.toml`. A deployment may use different names;
the authoritative configured DNA/RNA keys, family requirements, and
analysis-to-file bindings are documented in
[Center Vocabulary Configuration](../operations/clinical_vocabulary.md).

Use the canonical nested `files` object for all new manifests:

```yaml
files:
  vcf_files:
    path: /path/to/case_control.vcf
    checksum: optional-sha256
  cov:
    path: /path/to/coverage.json
```

| Field | Required | Meaning |
| --- | --- | --- |
| `files.<key>.path` | Yes | File path readable from the API and worker runtime. In Docker, this must be inside a mounted ingest/data root. |
| `files.<key>.checksum` | No | Optional checksum recorded on the sample file entry. |
| `files.<key>.size_bytes` | No | Optional size metadata. If omitted, the UI may show only path/availability. |

!!! info "Declared optional files"

    Optional files may be omitted. If an optional file is declared in `files`, it becomes part of the ingest transaction. The sample is not marked `ready` unless that declared file can be read, parsed, and written successfully.

!!! warning "Enabled analyses require complete data"

    The active ASPC is resolved from `assay`, `subpanel_id`, and `profile`. Every analysis enabled in `analysis_types` requires its corresponding file resource. For example, `CNV`, `CNV_PROFILE`, and `COVERAGE` require `cnv`, `cnvprofile`, and `cov` respectively. The ASP must declare those keys in `expected_files`, and the manifest must provide them. A configuration mismatch or failed resource prevents the sample from entering the `samples` collection as `ready`.

## DNA sample YAML

DNA bundles may include these file keys:

- `vcf_files`
- `cnv`
- `cnvprofile`
- `cov`
- `biomarkers`
- `transloc`
- `pgx`

The assay narrows that list through `assay_specific_panels.expected_files`. For example, if an ASP expects `vcf_files`, `cov`, and `cnv`, those are the only DNA files accepted for that assay. If `cnv` is also listed in `required_files`, missing or unreadable CNV JSON fails the ingest before the sample is published as ready.

| File key | Default requirement | Data type | Consumed by | Meaning |
| --- | --- | --- | --- | --- |
| `vcf_files` | Required for `panel-dna` and `wgs` unless ASP overrides `required_files` | VEP-annotated VCF | Small variants, reports, OncoKB enrichment, database-version extraction | SNV and small indel calls for the sample. |
| `cnv` | Required when ASPC enables `CNV`, otherwise optional unless required by ASP | JSON | CNV tab, reports | Copy-number calls such as gains, losses, and size/effect metadata. |
| `cnvprofile` | Required when ASPC enables `CNV_PROFILE`, otherwise optional unless required by ASP | Image | CNV tab | Visual CNV profile displayed beside the CNV table. It is stored as sample file metadata and does not create CNV collection rows. |
| `cov` | Required when ASPC enables `COVERAGE`, otherwise optional unless required by ASP | JSON | Coverage tab, overview QC | Gene/exon/probe coverage metrics. Coverage and `CNV_PROFILE` are independent resources. |
| `transloc` | Required when ASPC enables `TRANSLOCATION` or DNA `FUSION`, otherwise optional unless required by ASP | VCF or parser-supported translocation file | Translocations tab, reports | Structural/translocation calls. |
| `biomarkers` | Required when ASPC enables `BIOMARKER` or `TMB`, otherwise optional unless required by ASP | JSON | Header biomarkers, overview, reports | Sample-level biomarkers such as MSI, HRD, TMB, or assay-specific markers. |
| `pgx` | Required when ASPC enables `PGX`, otherwise optional unless required by ASP | Parser-supported PGX data | PGX workflows and reports | Pharmacogenomic calls or annotations. |

Ingest publication is atomic from the user's perspective:

1. Resolve ASP and active ASPC contracts.
2. Validate every required and declared path.
3. Parse and validate all configured analysis resources.
4. Write the sample and dependent collections in one transaction where supported.
5. Mark the sample `ready` only after every dependent write succeeds.
6. Remove partial sample data when any step fails.

Example:

```yaml
subpanel: "hematology_myeloid"
name: "seed_case"
clarity_case_id: "seed_case_clarity"
clarity_control_id: "seed_control_clarity"
clarity_case_pool_id: "seed_pool"
clarity_control_pool_id: "seed_pool"
genome_build: 38
database_versions:
  vep: "103"
sample_no: 2
case_id: "seed_case"
control_id: "seed_control"
profile: "production"
assay: "assay_1"
sequencing_scope: "panel"
omics_layer: "DNA"
sequencing_technology: "Illumina"
pipeline: "SomaticPanelPipeline"
pipeline_version: "3.1.14"
case_ffpe: false
case_sequencing_run: "seed_run"
case_reads: 49039064
control_ffpe: false
control_sequencing_run: "seed_run"
control_reads: 45889968
paired: true
files:
  vcf_files:
    path: "tests/data/ingest_demo/generic_case_control.final.filtered.vcf"
  cnv:
    path: "tests/data/ingest_demo/generic_case_control.cnvs.merged.json"
  cnvprofile:
    path: "tests/data/ingest_demo/generic_case_control.modeled.png"
  cov:
    path: "tests/data/ingest_demo/generic_case_control.cov.json"
```

Notes:

- `vcf_files` is the primary SNV/indel input.
- `cov` is used for coverage/gene coverage views.
- `cnv` and `cnvprofile` are optional but common for panel DNA workflows.
- `cnvprofile` is an image resource attached to the sample. It is served in the CNV tab beside the CNV table, but it does not create dependent database rows.
- `transloc`, `biomarkers`, and `pgx` are optional expected DNA resources. If declared, they must load successfully so the corresponding clinical view reflects the manifest.
- `database_versions.vep` should match the annotation version used to produce the VCF.
- The raw file expectations for `vcf_files`, `cnv`, `cov`, `biomarkers`, `transloc`, and `pgx` are documented in [API / Sample Input Files](sample_input_files.md#dna-raw-input-files).

## RNA sample YAML

RNA bundles may include these file keys:

- `fusion_files`
- `expression_path`
- `classification_path`
- `qc`
- `pgx`

As with DNA, the assay panel can narrow these through `assay_specific_panels.expected_files`, and only the configured RNA file keys are used by ingest and shown in the sample edit page.

| File key | Default requirement | Data type | Consumed by | Meaning |
| --- | --- | --- | --- | --- |
| `fusion_files` | Required for `panel-rna` and `wts` unless ASP overrides `required_files` | JSON | Fusions tab, RNA reports | Fusion calls and supporting evidence. |
| `expression_path` | Optional unless ASP marks it required | JSON | Expression/review workflows | Expression measurements or expression-derived features. |
| `classification_path` | Optional unless ASP marks it required | JSON | RNA classification workflows | Classifier output for RNA workflows. |
| `qc` | Optional unless ASP marks it required | JSON | RNA QC/overview | RNA quality-control metrics. |
| `pgx` | Required when ASPC enables `PGX`, otherwise optional unless required by ASP | Parser-supported PGX data | PGX workflows and reports | Pharmacogenomic calls or annotations. |

Example:

```yaml
name: "RNA_DEMO"
case_id: "RNA_DEMO"
sample_no: 1
paired: false
genome_build: 38
database_versions:
  vep: "110"
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
files:
  fusion_files:
    path: "/data/rna_demo.fusions.json"
  expression_path:
    path: "/data/rna_demo.expression.json"
  classification_path:
    path: "/data/rna_demo.classification.json"
  qc:
    path: "/data/rna_demo.qc.json"
```

Notes:

- `fusion_files` is the main RNA variant-like input.
- `expression_path`, `classification_path`, and `qc` are optional but recommended for richer RNA workflows.
- RNA samples may carry `database_versions.vep` when their pipeline emits VEP-compatible annotation metadata.
- A repo-local example is available at `tests/data/ingest_demo/generic_rna_sample.yaml`.
- The raw JSON file expectations for `fusion_files`, `expression_path`, `classification_path`, and `qc` are documented in [API / Sample Input Files](sample_input_files.md#rna-raw-input-files).

## VEP version behavior

`database_versions.vep` is stored on the sample document and used at runtime to:

- resolve consequence-group mappings from `vep_metadata`
- load VEP consequence translations
- load variant-class translations for sample views and reports

This means the sample keeps an explicit record of which VEP metadata version should be used when reopening or reporting the sample later.

DNA report generation and all sample-bound DNA table/filter operations read
`sample.database_versions.vep` during consequence resolution. They do not fall
back to the newest `vep_metadata` document when the sample value is missing.

## Database version metadata

During DNA ingest, Coyote3 reads the VEP header in the case VCF and stores a
curated version snapshot in `samples.database_versions`. Only clinically useful
reference/software version fields are retained. Transient header fields such as
cache paths, run timestamps, and plugin-specific values are ignored.

| Stored key | Display label | Example |
| --- | --- | --- |
| `assembly` | Assembly | `GRCh38.p13` |
| `clinvar` | ClinVar | `202008` |
| `cosmic` | COSMIC | `92` |
| `dbsnp` | dbSNP | `154` |
| `ensembl` | Ensembl | `103.4c8d44a` |
| `gencode` | GENCODE | `GENCODE 37` |
| `genebuild` | Genebuild | `2014-07` |
| `gnomad` | gnomAD | `r2.1` |
| `hgmd_public` | HGMD Public | `20194` |
| `polyphen` | PolyPhen | `2.2.2` |
| `sift` | SIFT | `sift5.2.2` |
| `vep` | VEP | `103` |

YAML and API input must use `database_versions` with these canonical keys exactly.
Only external VCF header labels are normalised before they are persisted.

## Validation reminders

- DNA sample YAML must not include RNA file keys.
- RNA sample YAML must not include DNA file keys.
- `case_id` is always required.
- `control_id` must be omitted for single-sample ingest.
- `sample_no` must match the pairing mode.
- `database_versions.vep` should be seeded in `vep_metadata` before DNA ingest.
- If `filters` is omitted entirely during ingest, ASPC defaults are initialized onto the sample.
- Once stored, `samples.filters` is used as-is until reset or explicit update.
