# Supported application capabilities

Coyote3 supports defined analysis workflows. Centers organize those workflows
using their own biological groups, assays, diagnoses and gene lists. There is no
fixed list of supported group names or assay names.

The application ingests pipeline results for review and reporting. It does not
perform sequencing alignment, variant calling or biomarker calculation. Software
support does not establish clinical validation of a center's assay.

## Application and center responsibilities

| Definition | Owner | Meaning |
| --- | --- | --- |
| Biological groups | Center | Organize clinical context, associations, annotation scope and access. |
| Assays | Center | Define sequencing offerings and select compatible implemented analyses. |
| Diagnoses and gene lists | Center | Define the clinical question and applicable gene selection. |
| Configurations and governed rules | Center | Set enabled analyses, thresholds, filtering and report content within supported capabilities. |
| Modalities, sequencing families and analyses | Application release | Define implemented workflows and their permitted combinations. |
| Input contracts and supported parsers | Application release | Define which pipeline results the application can consume. |

`src/coyote3/config/clinical_capabilities.toml` is the application capability registry.
Center vocabulary configuration cannot override it. A new group or assay can reuse
implemented analyses through configuration. A new analysis requires software
implementation and a release; adding its name to a configuration is insufficient.

## Modality and sequencing family

| Modality | Family | Available analyses |
| --- | --- | --- |
| DNA | `panel-dna`, `wes`, `wgs` | SNV, CNV, TRANSLOCATION, CNV_PROFILE, COVERAGE, HRD, MSI, TMB, PGX |
| RNA | `panel-rna` | FUSION, QC |
| RNA | `wts` | FUSION, EXPRESSION, CLASSIFICATION, QC |

Family determines modality. An assay's accepted files and `supported_analyses`
can narrow these choices. An ASPC enables a subset of its assay's capabilities;
its report sections must be enabled analyses. Invalid selections are rejected on
creation and update, including JSON imports.

## Result-handling workflows

| Analysis | Modality | Input key | Implemented behavior |
| --- | --- | --- | --- |
| `SNV` | DNA | `vcf_files` | SNV/indel ingestion, filtering, annotation, classification, review and reporting. |
| `CNV` | DNA | `cnv` | Copy-number result ingestion, filtering, annotation, review and reporting. |
| `TRANSLOCATION` | DNA | `transloc` | Structural breakend and DNA fusion evidence, partner review, annotation and reporting. |
| `CNV_PROFILE` | DNA | `cnvprofile` | Display and report use of a pipeline-produced copy-number profile artifact. |
| `COVERAGE` | DNA | `cov` | Gene/region coverage review and low-coverage evaluation within resolved sample scope. |
| `HRD` | DNA | `biomarkers` | Ingested HRD measurements, review and configured report rules. |
| `MSI` | DNA | `biomarkers` | Ingested single/paired MSI measurements, review and configured report rules. |
| `TMB` | DNA | `biomarkers` | Ingested mutation-burden measurements, review and configured report rules. |
| `PGX` | DNA | `pgx` | Storage and reporting of supplied pharmacogenomic results; no pharmacogenomic inference engine. |
| `FUSION` | RNA | `fusion_files` | Fusion calls, evidence filtering, selected-call review, annotation, classification and reporting. |
| `EXPRESSION` | RNA WTS | `expression_path` | Ingestion and presentation of supplied expression results. |
| `CLASSIFICATION` | RNA WTS | `classification_path` | Ingestion and presentation of supplied classifier results; no model training or inference. |
| `QC` | RNA | `qc` | Ingestion and presentation of supplied quality metrics. |

DNA fusions are `TRANSLOCATION` findings. DNA assays cannot enable `FUSION`;
that identifier belongs to RNA fusion calls. The two workflows retain their own
input formats, finding identities and filters.

RNA report preparation centers on fusion findings. Expression, classification and
QC capability does not imply a dedicated structured report-finding section or
snapshot for those result types.

HRD, MSI and TMB are independently enabled analyses sharing one input document.
Missing measurements are not represented as zero. Pipeline-produced inputs must
follow the [raw file contracts](../reference/ingest-files/README.md).

## Intents and callers

Somatic review is available for the supported DNA/RNA workflows. Germline intent
is implemented for DNA SNVs only. It has separate filters and report context.
The query resolver also composes effective germline exceptions into somatic SNV
policies; see [query-rule composition](query-rules.md#runtime-scope-resolution).
Review intent does not establish a finding's biological origin.

Supported RNA fusion caller identifiers are `arriba`, `fusioncatcher` and
`starfusion`. Caller labels and descriptions do not install a new parser.

## Biological groups and assay configuration

The bundled groups are hematology, solid and PGX, with myeloid and lymphoid as
children of hematology. These are installed definitions, not a software allowlist.
Bundled group-specific query policies cover hematology,
myeloid and solid. Registering another group does not automatically supply clinical
query exceptions or reporting rules.

Group names do not gate the general analysis handlers. A center-defined group can
use supported workflows through explicitly associated assays, diagnoses and
configurations. Parent groups provide annotation fallback evidence; they do not
automatically associate assays or grant permissions.

For example, an MPN diagnosis can use a DNA panel assay or a WGS assay in hematology.
Both resolve their own configuration and eligible gene scope. WGS does not remove
the sample's gene-scope restrictions.

## Adding a capability

Methylation and other unlisted modalities or analyses cannot be enabled by center
configuration. A new capability requires a software release with input validation,
ingestion, persistence contracts, analysis handlers, review UI, reporting behavior
and regression coverage. The release-owned registry must match those implementations.

Use [assay setup](assay-setup.md) to configure an existing workflow and
[analysis availability](assay-analysis-availability.md) for file-dependent choices.
