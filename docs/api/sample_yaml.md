# Sample YAML Guide

This page describes the pipeline YAML contract used when ingesting a DNA or RNA
sample bundle through the internal ingest APIs and watched-manifest workflow.

For the exact persisted `samples` collection contract, see [API / Collection Contracts](collection_contracts.md).
For endpoint usage, see [API / Ingestion API](ingestion_api.md).
For the raw VCF and JSON file shapes referenced by the YAML, see [API / Sample Input Files](sample_input_files.md).

## Purpose

The sample YAML is the top-level pipeline manifest. It tells Coyote3:

- which sample is being ingested
- which assay/profile the sample belongs to
- whether the bundle is DNA or RNA
- which data files belong to the sample
- which curated database versions should be used for consequence translation and filtering

The ingest boundary first converts supported pipeline field names into the
canonical sample contract. Validation, ASP/ASPC resolution, parsing, and storage
then use only canonical names. The original declared source paths are retained
in `samples.files.<key>.path` for traceability to the pipeline output.

For DNA, the VCF header is the normal source of curated annotation/database
versions. A manifest may include `database_versions` only to explicitly
override or supplement a value that the pipeline did not place in the VCF
header.

## Processing Protocol

1. The watcher finds a manifest in the configured ingest watch directory, or an
   operator submits one through the internal ingest API.
2. The YAML parser normalizes `null`, `"null"`, and other empty placeholders.
3. The pipeline field adapter maps supported external names to canonical sample
   names.
4. ASP and active ASPC are resolved from the canonical clinical scope.
5. The service validates every required resource and every optional resource
   declared by the manifest.
6. DNA or RNA parsers load the declared resources. A parsing or persistence
   failure prevents the sample from becoming ready.
7. The service persists the sample, linked analysis documents, ASPC lineage,
   and the ASPC-owned initial filter profiles.
8. The watcher appends `.done` after success or `.failed` after failure. Failed
   manifests are not retried until an operator corrects and restores them to the
   configured manifest filename.

## Filesystem and Symlink Contract

`COYOTE3_DATA_HOST_ROOT` is a Compose deployment setting. Compose mounts that
directory both at `/data` and at the same original absolute path in the API,
worker, and beat containers. This supports pipeline manifests that contain host
paths and preserves those paths in MongoDB.

For example, with:

```env
COYOTE3_DATA_HOST_ROOT='/srv/coyote3-data'
```

the pipeline path below is valid and remains unchanged when stored:

```yaml
vcf_files: /srv/coyote3-data/coyote3/copied_sample_files/gmshem/vcf/case.vcf
```

### External symlink targets

An in-root symlink works only when its resolved target is also visible to the
container. If a pipeline file under `/srv/coyote3-data` is a symlink to
`/mnt/sequencing/run_42/case.vcf`, deployment must bind-mount
`/mnt/sequencing` at `/mnt/sequencing` in API and Celery containers. Mount
external source roots read-only unless the application must write there.

| Situation | Result | Required action |
| --- | --- | --- |
| Regular file below `COYOTE3_DATA_HOST_ROOT` | Readable | No additional mount. |
| Relative symlink whose target remains below the mounted root | Readable | No additional mount. |
| Absolute or relative symlink resolving outside the mounted root | Broken inside container unless target root is mounted | Bind-mount the target root at the same absolute path. |
| Target file does not exist or lacks container read permission | Ingest fails | Restore file or permissions before retry. |

!!! warning "Do not rewrite pipeline provenance"

    Do not replace host source paths with `/data/...` merely to make a manifest
    work. The identical-path bind mount exists specifically so the stored sample
    record preserves the source path emitted by the pipeline.

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
- `profile`/`environment` must be one of `production`, `development`, `testing`, or `validation`.
- When a DNA VCF supplies `database_versions.vep`, it must match a
  `vep_metadata.vep_id` document already seeded in Mongo for DNA filtering and
  reporting to work.
- ASP controls which sample file keys are expected through `assay_specific_panels.expected_files`.
- File keys not listed in the assay's `expected_files` are rejected before parsing. Coyote3 does not silently remove declared resources.
- Required files listed in `assay_specific_panels.required_files` must be present and readable.
- Optional files may be omitted. When an optional expected file is declared, it becomes part of that ingest transaction and must be parsed and written successfully.
- A sample is only marked `ready` after all declared database-backed resources have been written.
- Pipeline-authored `filters` and `analysis_intents` are not used. Ingest derives
  both from the resolved active ASPC.

## Pipeline Field Mapping

Pipelines may continue to emit their established names. The adapter maps them
once, before ASP/ASPC lookup and before the sample schema is evaluated.

| Pipeline field | Canonical stored field | Applies to | Rule |
| --- | --- | --- | --- |
| `assay` | `asp_id` | DNA, RNA | Required clinical identity. Both names may be supplied only with the same value. |
| `subpanel` | `subpanel_id` | DNA, RNA | Optional clinical identity. Omit for the configured `base` subpanel. |
| `profile` | `environment` | DNA, RNA | Required deployment/clinical environment. |
| `sequencing_technology` | `platform` | DNA, RNA | Sequencing platform, such as `illumina`; read technology is derived from platform configuration. |

Pipeline-authored YAML must use the left-hand names consistently. The
right-hand names describe only the canonical internal representation after
ingest normalization. After normalization, no stored sample, ASPC lookup, or
downstream service uses `assay`, `subpanel`, `profile`, or
`sequencing_technology`.

## Shared top-level fields

These keys are common to DNA and RNA sample bundles.

| Key | Required | Applies to | Meaning |
| --- | --- | --- | --- |
| `name` | Yes | DNA, RNA | Unique sample name shown in the UI and stored in `samples.name`. |
| `assay` | Yes | DNA, RNA | Pipeline ASP identifier. Ingest normalizes it to internal `asp_id`, which resolves the active physical assay definition and its allowed, expected, and required file keys. |
| `subpanel` | No | DNA, RNA | Pipeline subpanel identifier. Ingest normalizes it to `subpanel_id`; omitting it resolves the configured `base` subpanel. |
| `profile` | Yes | DNA, RNA | Pipeline environment. Ingest normalizes it to internal `environment`. Allowed values are `production`, `development`, `testing`, and `validation`. |
| `case_id` | Yes | DNA, RNA | Case/sample identifier from the upstream pipeline or LIMS. |
| `control_id` | Paired only | DNA, RNA | Control sample identifier. Omit for single-sample ingest. |
| `sample_no` | Yes | DNA, RNA | `1` for single-sample ingest, `2` for paired case/control ingest. |
| `paired` | Yes | DNA, RNA | `true` when `control_id` is present, otherwise `false`. |
| `genome_build` | Recommended | DNA, RNA | Integer reference genome build, normally `38`. |
| `database_versions.vep` | No for DNA VCF ingest; optional override | DNA, RNA | VEP metadata version used to resolve consequence groups, display labels, transcript metadata, and report text. Normally extracted from the DNA VCF `##VEP=` header. Supply it only when an explicit manifest value must take precedence or the input has no usable header value. |
| `sequencing_scope` | Yes | DNA, RNA | Sequencing scope. Valid values are `panel`, `wgs`, or `wts`. |
| `omics_layer` | Yes | DNA, RNA | `dna` or `rna` (case-insensitive input). This controls which file keys are legal. |
| `sequencing_technology` | Recommended | DNA, RNA | Pipeline platform label, for example `Illumina`, `Nanopore`, or `PacBio`. Ingest normalizes it to internal `platform`; the ASP platform compatibility check then applies. |
| `read_mode` | Conditional | DNA, RNA | Platform-supported read mode, such as `PE` or `SE`; omit when the selected platform does not use read mode. |
| `pipeline` | Yes | DNA, RNA | Upstream pipeline name. |
| `pipeline_version` | Yes | DNA, RNA | Upstream pipeline version. Store as a string when possible. |
| `database_versions` | No | DNA, RNA | Optional canonical version override/supplement. For DNA VCF ingest, recognised values are extracted from the VCF header first; supplied manifest values then replace only matching extracted keys. |
| `<file_key>` | Supported | DNA, RNA | Flat pipeline file declaration, for example `vcf_files: /srv/coyote3-data/coyote3/incoming/case.vcf`. Each key must be valid for the selected omics layer and allowed by the ASP. Ingest stores it in canonical sample file metadata. |
| `filters` | Ignored | DNA, RNA | Pipelines must not author clinical filters. Ingest replaces this with the resolved ASPC filter profile. |
| `analysis_intents` | Ignored | DNA, RNA | Pipelines must not author somatic/germline scope. Ingest obtains it from the resolved ASPC. |

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
| `case_purity` | DNA | Optional tumor purity estimate between `0` and `1`. |
| `control_purity` | Paired DNA | Optional control purity estimate, normally empty. |

## Pipeline file declaration format

The concrete keys below are the current center profile from
`api/config/center/clinical_vocabulary.toml`. A deployment may use different names;
the authoritative configured DNA/RNA keys, family requirements, and
analysis-to-file bindings are documented in
[Center Vocabulary Configuration](../operations/clinical_vocabulary.md).

Pipeline YAML manifests always declare each source file as a flat top-level key.
The external pipeline contract therefore uses `vcf_files`, `cnv`, `cov`, and
the other configured names directly; it does not use a `files:` wrapper. Ingest
normalizes those paths into the stored `samples.files.<key>` structure.

```yaml
vcf_files: /srv/coyote3-data/coyote3/incoming/case_control.vcf
cov: /srv/coyote3-data/coyote3/incoming/case_coverage.json
```

| Field | Required | Meaning |
| --- | --- | --- |
| `<file_key>` | When required by ASP/ASPC | A source path readable from API and worker containers. It may be manifest-relative or under the identically mounted `COYOTE3_DATA_HOST_ROOT`. |
| `uploaded_file_checksums` | No | Optional mapping of file key to checksum, persisted with sample file metadata. |

!!! info "Declared optional files"

    Optional files may be omitted. If an optional flat file key is declared, it becomes part of the ingest transaction. The sample is not marked `ready` unless that declared file can be read, parsed, and written successfully.

!!! warning "Enabled analyses require complete data"

    The active ASPC is resolved from normalized `asp_id`, `subpanel_id`, and
    `environment`. Every analysis enabled in `analysis_types` requires its
    corresponding file resource. For example, `CNV`, `CNV_PROFILE`, and
    `COVERAGE` require `cnv`, `cnvprofile`, and `cov` respectively. The ASP
    must declare those keys in `expected_files`, and the manifest must provide
    them. A configuration mismatch or failed resource prevents the sample from
    entering the `samples` collection as `ready`.

## DNA sample YAML

DNA bundles may include these file keys:

- `vcf_files`
- `cnv`
- `cnvprofile`
- `cov`
- `biomarkers`
- `transloc`
- `pgx`

`lowcov` is not a DNA analysis file key. A low-coverage BED file cannot satisfy
the `COVERAGE` analysis, which requires the configured `cov` coverage resource.
Keep low-coverage BED handling in a separately approved analysis contract before
adding it to center configuration.

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

Pipeline-format example:

```yaml
subpanel: "hematology-myeloid"
name: "seed_case"
clarity_case_id: "seed_case_clarity"
clarity_control_id: "seed_control_clarity"
clarity_case_pool_id: "seed_pool"
clarity_control_pool_id: "seed_pool"
genome_build: 38
sample_no: 2
case_id: "seed_case"
control_id: "seed_control"
profile: "production"
assay: "hema_GMSv1"
sequencing_scope: "panel"
omics_layer: "DNA"
sequencing_technology: "Illumina"
pipeline: "SomaticPanelPipeline"
pipeline_version: "3.1.14"
case_ffpe: false
case_sequencing_run: "seed_run"
case_reads: 49039064
case_purity: null
control_ffpe: false
control_sequencing_run: "seed_run"
control_reads: 45889968
control_purity: null
paired: true
vcf_files: "/srv/coyote3-data/coyote3/incoming/seed_case.vcf"
cnv: "/srv/coyote3-data/coyote3/incoming/seed_case.cnvs.json"
cnvprofile: "/srv/coyote3-data/coyote3/incoming/seed_case.profile.png"
cov: "/srv/coyote3-data/coyote3/incoming/seed_case.coverage.json"
```

Notes:

- `vcf_files` is the primary SNV/indel input.
- `cov` is used for coverage/gene coverage views.
- `cnv` and `cnvprofile` are optional but common for panel DNA workflows.
- `cnvprofile` is an image resource attached to the sample. It is served in the CNV tab beside the CNV table, but it does not create dependent database rows.
- `transloc`, `biomarkers`, and `pgx` are optional expected DNA resources. If declared, they must load successfully so the corresponding clinical view reflects the manifest.
- The VCF `##VEP=` header supplies the database-version snapshot. This example
  intentionally does not repeat it in YAML.
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

Pipeline-format example:

```yaml
name: "RNA_DEMO"
case_id: "RNA_DEMO"
sample_no: 1
paired: false
genome_build: 38
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
fusion_files: "/srv/coyote3-data/coyote3/incoming/rna_demo.fusions.json"
expression_path: "/srv/coyote3-data/coyote3/incoming/rna_demo.expression.json"
classification_path: "/srv/coyote3-data/coyote3/incoming/rna_demo.classification.json"
qc: "/srv/coyote3-data/coyote3/incoming/rna_demo.qc.json"
```

Notes:

- `fusion_files` is the main RNA variant-like input.
- `expression_path`, `classification_path`, and `qc` are optional but recommended for richer RNA workflows.
- RNA samples may carry `database_versions.vep` when their pipeline emits VEP-compatible annotation metadata.
- A repo-local example is available at `tests/data/ingest_demo/generic_rna_sample.yaml`.
- The raw JSON file expectations for `fusion_files`, `expression_path`, `classification_path`, and `qc` are documented in [API / Sample Input Files](sample_input_files.md#rna-raw-input-files).

## Database-version extraction and override behavior

For DNA VCF ingest, Coyote3 reads the first `##VEP=` header line and retains
only recognised version fields. The retained values are written to
`samples.database_versions`; all other VEP-header details, including paths,
timestamps, and plugin-specific values, are discarded.

If the YAML includes `database_versions`, Coyote3 validates its keys and merges
the values after header extraction. Therefore a YAML value has precedence for
the same canonical key, while header-derived values remain for keys absent from
the YAML. If neither source supplies a recognised value, no placeholder is
written.

`database_versions.vep`, when present, is used at runtime to:

- resolve consequence-group mappings from `vep_metadata`
- load VEP consequence translations
- load variant-class translations for sample views and reports

This means the sample keeps an explicit record of which VEP metadata version should be used when reopening or reporting the sample later.

DNA report generation and all sample-bound DNA table/filter operations require
`sample.database_versions.vep` during consequence resolution. They do not fall
back to the newest `vep_metadata` document. A VCF without a usable VEP version
can be ingested as raw data, but DNA interpretation/reporting cannot proceed
until the sample has a valid VEP version linked to seeded `vep_metadata`.

## Database version metadata

The following are the only stored keys. Their labels may occur with different
punctuation or casing in a VCF header; the VCF parser normalizes recognised
external labels. A YAML override must use the canonical key exactly.

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

When YAML or API input supplies `database_versions`, it must use these canonical
keys exactly. Only external VCF-header labels are normalized before persistence.

## Validation reminders

- DNA sample YAML must not include RNA file keys.
- RNA sample YAML must not include DNA file keys.
- `case_id` is always required.
- `control_id` must be omitted for single-sample ingest.
- `sample_no` must match the pairing mode.
- DNA VCF headers should provide `vep`; a manifest override is available only
  for an explicit correction or an upstream pipeline that cannot emit it.
- `database_versions.vep`, when stored, must be seeded in `vep_metadata` before
  DNA filtering or reporting.
- If `filters` is omitted entirely during ingest, ASPC defaults are initialized onto the sample.
- Once stored, `samples.filters` is used as-is until reset or explicit update.
- A pipeline manifest may use `assay`, `subpanel`, `profile`, and
  `sequencing_technology`; they are normalized before clinical validation.
- Source file paths below `COYOTE3_DATA_HOST_ROOT` are retained unchanged in
  sample file records. Any symlink target outside that root requires its own
  same-path Compose bind mount.
