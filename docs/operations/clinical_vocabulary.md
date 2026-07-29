# Center Vocabulary Configuration

`api/config/center/clinical_vocabulary.toml` is the center-owned vocabulary contract.
It is loaded and validated when the API or a worker starts. A malformed
configuration prevents startup rather than allowing an ingest or login flow to
run with an ambiguous contract.

!!! info "Configuration boundary"

    TOML configures names and enabled choices that differ between centers.
    Python implements the workflow and typed persistence. This TOML file owns
    the selectable values, manifest vocabulary, and center policy labels used
    by those workflows.

## File Layout

```toml
[assay]
categories = ["dna", "rna"]
families = ["panel-dna", "panel-rna", "wgs", "wts"]
base_subpanel_id = "base"

[assay.family_categories]
panel-dna = "dna"
panel-rna = "rna"
wgs = "dna"
wts = "rna"

[assay.family_scopes]
panel-dna = "panel"
panel-rna = "panel"
wgs = "wgs"
wts = "wts"

[environment]
options = ["production", "development", "testing", "validation"]
default = "production"

[authentication]
providers = ["local", "ldap"]

[genelist]
standard_types = ["snv", "cnv", "fusion", "expression", "pgx"]
adhoc_types = ["adhoc_snv", "adhoc_cnv", "adhoc_fusion", "adhoc_expression", "adhoc_pgx"]

[reporting]
required_aspc_fields = ["report_header", "report_method", "general_report_summary"]

[files.dna]
keys = ["vcf_files", "cnv", "cnvprofile", "cov", "transloc", "biomarkers", "pgx"]

[files.rna]
keys = ["fusion_files", "expression_path", "classification_path", "qc", "pgx"]

[files.required_by_family]
panel-dna = ["vcf_files"]
wgs = ["vcf_files"]
panel-rna = ["fusion_files"]
wts = ["fusion_files"]

[analysis.dna]
types = ["SNV", "CNV", "TRANSLOCATION", "BIOMARKER", "CNV_PROFILE", "COVERAGE", "FUSION", "TMB", "PGX"]

[analysis.dna.file_keys]
SNV = ["vcf_files"]
CNV = ["cnv"]
TRANSLOCATION = ["transloc"]
BIOMARKER = ["biomarkers"]
CNV_PROFILE = ["cnvprofile"]
COVERAGE = ["cov"]
FUSION = ["transloc"]
TMB = ["biomarkers"]
PGX = ["pgx"]

[analysis.rna]
types = ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC", "PGX"]

[analysis.rna.file_keys]
FUSION = ["fusion_files"]
EXPRESSION = ["expression_path"]
CLASSIFICATION = ["classification_path"]
QC = ["qc"]
PGX = ["pgx"]
```

## Center-Owned Tables

| TOML table | Key | Allowed value form | How the application uses it |
| --- | --- | --- | --- |
| `[assay]` | `categories` | Non-empty unique lowercase identifiers | Defines the omics categories used by ASPs and the `files.<category>` and `analysis.<category>` tables. |
| `[assay]` | `families` | Non-empty unique lowercase identifiers | Defines selectable ASP families and the required family mapping tables. |
| `[assay]` | `base_subpanel_id` | One lowercase identifier | The synthetic subpanel identifier used for an assay-wide ASPC when no named subpanel applies. |
| `[assay.family_categories]` | one value per family | A configured assay category | Maps every family to the omics category that owns its file-key vocabulary. |
| `[assay.family_scopes]` | one value per family | One non-empty identifier | Maps every family to the sequencing scope stored with samples. |
| `[environment]` | `options`, `default` | Unique identifiers; default must be one listed option | Defines selectable ASPC/sample environments and the initial environment used where none is provided. |
| `[authentication]` | `providers` | One or both of `local`, `ldap` | Defines the enabled values permitted in a user's `auth_type` list. `local` uses username and local password; `ldap` uses email and directory credentials. |
| `[genelist]` | `standard_types`, `adhoc_types` | Non-empty unique identifiers with no overlap | Defines selectable ISGL list types and determines which options appear when the ISGL ad-hoc switch is enabled. |
| `[reporting]` | `required_aspc_fields` | Non-empty unique ASPC reporting field identifiers | Names the reporting values administrators must supply for an active report-capable ASPC. |
| `[files.dna]` | `keys` | Non-empty unique manifest-key identifiers | Declares the accepted file keys for DNA sample YAML `files`. |
| `[files.rna]` | `keys` | Non-empty unique manifest-key identifiers | Declares the accepted file keys for RNA sample YAML `files`. |
| `[files.required_by_family]` | family arrays | Keys declared for that family's omics category | Establishes the baseline required input files for `panel-dna`, `wgs`, `panel-rna`, and `wts`. ASP-specific requirements can make additional configured keys mandatory. |
| `[analysis.dna]` / `[analysis.rna]` | `types` | Supported application analysis types | Enables the analysis types that the center intends to use for that omics category. |
| `[analysis.<omics>.file_keys]` | one array per enabled type | One or more configured keys for that omics category | Binds each analysis workflow to the manifest field(s) it reads. The first key is the primary path used by single-file consumers such as report images. |

## Software-Owned Sequencing Capability

Platform semantics are a software contract, rather than center TOML. The
application supports `illumina`, `iontorrent`, `pacbio`, and `nanopore`.
`read_technology` is derived automatically: Illumina and Ion Torrent are
`short_read`; PacBio and Nanopore are `long_read`. Only Illumina currently
offers selectable `read_mode` values (`SE` and `PE`). The ASP form filters the
read-mode choices after a platform is selected; incompatible combinations are
also rejected by the API contract.

Permission categories are likewise software-owned presentation semantics.
Centers assign permissions to roles and roles to users, but do not redefine
the application's permission categories through deployment configuration.

## Analysis Labels and Workflow Support

The `analysis.<category>.types` arrays determine the analysis labels exposed
in ASPC administration and their manifest-file bindings. The application does
not maintain a second hardcoded allowlist for these labels.

Adding a label alone does not create a parser or report section. When a center
introduces a genuinely new analysis workflow, it must add the corresponding
typed ingest, storage, API, UI, and report implementation in the same release.
For an existing workflow, changing the source-file key is a configuration-only
change.

`FUSION` and `TRANSLOCATION` may intentionally reference the same physical
DNA input if a pipeline emits both interpretations from one structural-variant
VCF. They remain distinct analysis sections downstream.

## Validation Rules

1. Every table shown above is required.
2. Values must be unique, non-empty, and use identifier-safe file-key names.
3. Every configured assay family requires a category and sequencing-scope mapping.
4. Every configured assay family requires a baseline file declaration.
5. A required file key must belong to the matching category `keys` array.
6. Every enabled analysis type must have one `file_keys` entry, and no extra
   entries are accepted.
7. An analysis binding may only reference keys declared for the same omics
   category.
8. Authentication providers are limited to the application's supported
   `local` and `ldap` mechanisms.

## Fixed Assay-Group Taxonomy

Assay groups are deliberately absent from this TOML file. They are not local
labels: an assay group is a persistent clinical scope used by ASPs, ASPCs,
ISGLs, annotations, user access assignments, dashboards, and future
cross-assay queries. Changing one without a software release would create
ambiguous historical data.

| Identifier | Workflow scope | Use it for | Do not use it for |
| --- | --- | --- | --- |
| `tumwgs` | Tumour whole-genome workflow | WGS design panels and their annotations/query behaviour | The `wgs` family identifier. |
| `wts` | Whole-transcriptome workflow | WTS design panels and their annotations/query behaviour | The `wts` family identifier. |
| `hematology` | General haematology workflow | Broad haematology panels and their annotations/query behaviour | A physical design panel ID. |
| `myeloid` | Myeloid haematology workflow | Myeloid-specific assay designs and clinical logic | A sequencing family. |
| `lymphoid` | Lymphoid haematology workflow | Lymphoid-specific assay designs and clinical logic | A sequencing family. |
| `solid` | Solid-tumour workflow | Solid tumour panel designs and their annotations/query behaviour | A subpanel such as endometrial or breast. |
| `fusion` | Fusion workflow | RNA fusion assay designs | A particular RNA design panel. |
| `fusionrna` | Fusion/exon-skipping workflow | RNA fusion plus exon-skipping designs | A particular RNA design panel. |
| `pgx` | Pharmacogenomic workflow | PGX assay designs and their annotations/query behaviour | The `PGX` analysis type. |

The related fields have different responsibilities:

| Field | Examples | Meaning |
| --- | --- | --- |
| `asp_group` | `hematology`, `solid`, `tumwgs`, `myeloid` | Fixed assay/workflow scope used to link ASPs, ASPCs, ISGLs, annotations, user access, and query logic. |
| `asp_family` | `panel-dna`, `wgs`, `panel-rna`, `wts` | Sequencing design family. It is not an assay group. |
| `asp_category` | `dna`, `rna` | Omics category that selects the allowed manifest and analysis vocabulary. |
| `subpanel_id` | `base`, `endometrie`, `breast`, `colon` | In-silico clinical target subset within a design panel. `base` means no named subpanel. |

Administrators select an assay group from this fixed list in the ASP, ASPC,
ISGL, and user-scope forms. A new group is introduced only through a reviewed
software release with schema validation, query-policy review, tests, and a
data migration for any affected documents.


## Runtime Resolution

The application exposes `analysis_file_keys(omics, analysis)` and
`primary_analysis_file_key(omics, analysis)` from
`api/config/constants.py`. Ingest parsers, sample file status cards, CNV plot
delivery, report rendering, and sample-omics inference use these accessors;
they do not depend on a hardcoded center file-field name.

Internal collection names are deliberately separate. For example, a center can
rename the DNA coverage manifest key from `cov` to `coverage_json`, while the
parsed data still writes to the software-owned `panel_coverage` collection.

## Change Procedure

1. Add the required input file name to `[files.dna]` or `[files.rna]`.
2. Bind it to the selected analysis label under `[analysis.<omics>.file_keys]`.
3. Update the center's sample YAML producers and seed examples to use the new
   key.
4. Review baseline requirements for affected assay families and any
   ASP-specific `required_files` settings.
5. Restart API and worker services together so every process has the same
   validated contract.
6. Ingest a representative non-production sample and verify the source-file
   card, parsed collection, analysis tab, and report section.

!!! warning "Renaming an active manifest key"

    Existing sample documents retain their historical `files` keys. Plan a
    controlled data migration or retain the old data until historical samples
    no longer require it. Do not change the TOML while active workers are
    ingesting the same watch directory.

## Authorization Model

Centers configure permission display categories here. Authorization remains
role-based: permission IDs are assigned to roles and roles are assigned to
users. A category only organizes the administration UI and never grants access
on its own.
