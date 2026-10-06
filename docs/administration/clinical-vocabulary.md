# Center Vocabulary Configuration

`clinical_vocabulary.toml` in the external center directory is the vocabulary contract.
The bundled `api/config/center/clinical_vocabulary.toml` provides complete examples.
See [persistent configuration](../deployment/center-configuration.md#persistent-local-files-or-a-git-configuration-release)
for local files, pinned Git sources, deployment, and upgrade handling.
It is loaded and validated when the API or a worker starts. A malformed
configuration prevents startup rather than allowing an ingest or login flow to
run with an ambiguous contract.

> **Info: Configuration boundary**
>
>
> TOML configures names and enabled choices that differ between centers.
> Python implements the workflow and typed persistence. This TOML file owns
> the selectable values, manifest vocabulary, and center policy labels used
> by those workflows.
>

## Format, required values and defaults

TOML groups settings under headings such as `[environment]`. A quoted value is
text; square brackets after `=` contain a list. Dotted headings such as
`[assay.family_categories]` define nested mappings. The examples below are a
complete starting vocabulary, not implicit defaults for missing entries.

| Settings | Required? | Behavior when omitted |
| --- | --- | --- |
| `assay`, `environment`, `authentication`, `genelist` and their documented keys | Yes | Startup validation fails; no replacement identifiers are invented. |
| `files` and `analysis`, including per-category and per-family mappings | Yes | Startup validation fails. Mappings must agree with declared categories, families and analysis types. |
| `reporting.transcript_selection_order` | Yes | Startup validation fails. Every supported selector must appear exactly once. |
| `reporting.annotation_tumor_types` | Yes, table; entries may be empty | Omitting the table fails validation. A group without an entry has an empty annotation descriptor. |
| `fusion.callers` and `fusion.description_terms` | Yes | Startup validation fails. Description categories must be `important`, `not_important` and `context`. |
| `snv.callers`, `cnv.callers`, `translocation.callers` | No | Each defaults to an empty list; its entire table may be omitted. |

Unknown sections and unsupported keys fail validation. `environment.default` is
an explicitly configured clinical-profile default, not a fallback for an absent
configuration field. The field tables below describe accepted values and effects.
For caller-specific flag text, use the separate
[flag metadata reference](../configuration/filter-flag-metadata-file.md).

## Runtime consumers

Every supported vocabulary section has an application consumer. Configuration
does not implement a parser, finding type, authentication protocol, or sequencing
capability. Retain the software-supported semantics when changing identifiers.

| Vocabulary | Application consumer | Effect and limits |
| --- | --- | --- |
| `assay.categories`, `families`, `family_categories`, `family_scopes` | `api/config/constants.py`, assay/sample contracts, and ingest helpers | ASP choices, category validation, family-to-omics mapping, and sample sequencing scope. |
| `assay.base_subpanel_id` | `SUBPANEL_BASE_ID`, ASPC resolution, catalog and reporting services | Identifies the base configuration scope; changing it requires reviewing existing database references. |
| `environment.options`, `default` | Environment normalization, sample catalog defaults, ingest, user scopes, and public catalog | Defines clinical profiles and their default. This does not replace the deployment's `ENV_NAME`. |
| `authentication.providers` | Authentication constants and login configuration | Enables implemented local/LDAP providers; `AUTHENTICATION_PROVIDERS` can override it for a deployment. |
| `genelist.standard_types`, `adhoc_types` | Gene-list contracts, managed forms, and filter normalization | Curated and ad-hoc gene-list choices. |
| `files.*.keys`, `files.required_by_family` | Sample contracts, ASP required-file defaults, manifest normalization and ingest | Defines pipeline file keys and baseline required inputs. ASP records can specify their required files. |
| `analysis.*.types`, `file_keys`, `allowed_by_family` | Analysis constants, ingest preload bindings, ASPC validation and managed forms | Binds implemented analyses to files and assay families. Adding a name does not create ingest or review support. |
| `reporting.annotation_tumor_types` | `api/application/interpretation/report_summary.py` | Assay-group descriptors in automatic Tier III annotation text; absent groups yield an empty descriptor. |
| `reporting.transcript_selection_order` | `api/application/ingest/parsers.py` | Ordered selection of persisted transcript evidence during ingest. Existing findings are not reselected on configuration reload. |
| `fusion.callers` | Fusion contracts, query builder, managed filters, RNA view contexts and caller-specific flag validation | Normalizes caller IDs and validates supported fusion caller selections. |
| `fusion.description_terms` | RNA view contexts and fusion annotation badges | Categorizes caller evidence text for display; it is not a reporting-rule predicate. |
| `snv.callers`, `cnv.callers`, `translocation.callers` | Filter metadata validation and SNV/CNV/translocation flag display | Registers caller-specific explanations. Historical caller names are retained; these lists do not filter findings or reject stored provenance. |

## Caller registries and flag descriptions

Fusion supports the implemented caller IDs `arriba`, `fusioncatcher`, and
`starfusion`. Use only these values in `fusion.callers`; adding a name does not
implement another fusion workflow.

The SNV, CNV, and translocation registries are optional presentation settings.
They default to empty and their tables may be omitted. Combined inputs do not
need a list of every contributing caller in this file. The application reads
normalized records, rather than running or selecting native DNA callers:

```toml
[snv]
callers = []
[cnv]
callers = []
[translocation]
callers = []
[fusion]
callers = ["arriba", "fusioncatcher", "starfusion"]
```

### Caller filtering and provenance

| Analysis | Implemented caller behavior | Effect of the vocabulary registry |
| --- | --- | --- |
| SNV | Ingest splits the combined VCF's `INFO.variant_callers` on `\|` and preserves all callers. No caller query filter is implemented. | Optional caller-specific flag descriptions only. |
| CNV | Normalized JSON preserves `callers`. Query-policy exceptions can match this array; the ordinary CNV filters have no caller selector. | Optional caller-specific flag descriptions; it does not configure those query exceptions. |
| Translocation | Views can display recorded caller provenance. No caller query filter is implemented. | Optional caller-specific flag descriptions only. |
| Fusion | The `fusion_callers` filter and fusion query-policy exceptions match `calls[].caller`. | Defines the selectable subset of the three implemented caller IDs. |

An empty DNA registry does not discard provenance or exclude findings. It also
does not make raw input fields optional: the current SNV ingest parser requires
`INFO.variant_callers`. See the [combined VCF contract](../reference/ingest-files/small-variants-vcf.md).

### Optional flag descriptions

Leave `callers: {}` in `filter_flag_metadata.yaml` unless the center has reviewed
caller-specific descriptions. When needed, register only exact provenance IDs
from validated inputs in the corresponding optional DNA vocabulary list. These
are metadata identifiers, not claims of native caller support.

For example, after explicitly registering the synthetic ID `pipeline_caller` in
`cnv.callers`, this illustrates a scoped description:

```yaml
callers:
  cnv:
    pipeline_caller:
      terms:
        EXAMPLE_REVIEW:
          label: Review
          severity: info
          description: Replace with the approved explanation for this pipeline flag.
```

`pipeline_caller` and `EXAMPLE_REVIEW` are placeholders, not supported tool or flag names.
Use exact pipeline flag names and reviewed descriptions. Caller keys must exist in
the matching vocabulary registry. Unknown analysis/caller keys and unsupported
severity values fail validation. The public flag-metadata API exposes both the
caller options and scoped definitions.

Within a caller or the global metadata, matching order is `terms`, `exact`, then
the first matching `prefixes` entry. A caller-specific definition takes precedence
only when recorded provenance identifies it unambiguously. Caller name comparison
ignores case and separators. Multiple callers must agree on a definition; otherwise
global metadata applies, or a neutral flag is shown when no global definition exists.
No caller is inferred from an assay name or a structural-variant identifier.

SNV views read caller provenance from `INFO.variant_callers`; CNV views use `callers`;
translocation views use recorded `INFO.variant_callers` or `callers` when present.
Flags are shown only from recorded `FILTER` values. Missing flags are not generated
from caller names. These descriptions never change filtering thresholds, admission,
classification, or report wording.

External vocabulary files may omit the `snv`, `cnv`, and `translocation`
caller tables. Remove the obsolete
`reporting.required_aspc_fields` setting: reporting requirements are enforced by
the typed ASPC contract, not a configurable field-name list. Stage and validate the complete
configuration release before switching services.

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

[snv]
callers = []

[cnv]
callers = []

[translocation]
callers = []

[fusion]
callers = ["arriba", "fusioncatcher", "starfusion"]

[fusion.description_terms]
important = ["mitelman", "known", "oncogene", "cancer", "cosmic", "high"]
not_important = ["1000genomes", "banned", "matched-normal", "readthrough"]
context = ["distance100kbp", "duplicates", "healthy", "short_distance"]

[reporting]
transcript_selection_order = [
  "ncbi_mane_plus_clinical",
  "ensembl_mane_plus_clinical",
  "ncbi_mane_select",
  "ensembl_mane_select",
  "vep_canonical_protein_coding",
  "first_protein_coding",
  "first_available",
]

[files.dna]
keys = ["vcf_files", "cnv", "cnvprofile", "cov", "transloc", "hrd", "msi", "tmb", "pgx"]

[files.rna]
keys = ["fusion_files", "expression_path", "classification_path", "qc", "pgx"]

[files.required_by_family]
panel-dna = ["vcf_files"]
wgs = ["vcf_files"]
panel-rna = ["fusion_files"]
wts = ["fusion_files"]

[analysis.dna]
types = ["SNV", "CNV", "TRANSLOCATION", "HRD", "MSI", "CNV_PROFILE", "COVERAGE", "FUSION", "TMB", "PGX"]

[analysis.dna.file_keys]
SNV = ["vcf_files"]
CNV = ["cnv"]
TRANSLOCATION = ["transloc"]
HRD = ["hrd"]
MSI = ["msi"]
CNV_PROFILE = ["cnvprofile"]
COVERAGE = ["cov"]
FUSION = ["transloc"]
TMB = ["tmb"]
PGX = ["pgx"]

[analysis.rna]
types = ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC", "PGX"]

[analysis.rna.file_keys]
FUSION = ["fusion_files"]
EXPRESSION = ["expression_path"]
CLASSIFICATION = ["classification_path"]
QC = ["qc"]
PGX = ["pgx"]

[analysis.allowed_by_family]
panel-dna = ["SNV", "CNV", "CNV_PROFILE", "TRANSLOCATION", "HRD", "MSI", "COVERAGE", "FUSION", "TMB", "PGX"]
wgs = ["SNV", "CNV", "CNV_PROFILE", "TRANSLOCATION", "HRD", "MSI", "COVERAGE", "FUSION", "TMB", "PGX"]
panel-rna = ["FUSION", "QC", "PGX"]
wts = ["FUSION", "EXPRESSION", "CLASSIFICATION", "QC", "PGX"]
```

The ASPC editor applies this matrix dynamically. Selecting the DNA or RNA
configuration type first limits the available ASPs to that omics category.
Selecting an ASP then limits **Analysis types** to its sequencing family. For
example, an RNA fusion panel does not offer `EXPRESSION` or `CLASSIFICATION`,
while a WTS ASP does. If the selected ASP changes, options that are invalid for
the new family are removed from the pending form before it is saved. The API
validates the same matrix and rejects incompatible submitted values.

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
| `[fusion]` | `callers` | Unique lowercase caller IDs, for example `arriba`, `fusioncatcher`, and `starfusion` | Defines the canonical IDs accepted on ingested `fusions.calls[].caller`, persisted in `filters.somatic.fusion.fusion_callers`, offered by ASPC and sample filter forms, and used in MongoDB predicates. Input capitalization and separators are normalized to these IDs; unconfigured callers are rejected at typed write boundaries. |
| `[fusion.description_terms]` | `important`, `not_important`, `context` | Unique lowercase exact terms with no term repeated across groups | Categorizes comma-delimited caller annotations in both the fusion filter selector and table tooltips. Important terms are green, not-important/artifact terms are red, contextual terms are gray, and unlisted terms remain neutral. Selecting terms applies exact, case-insensitive token filters; these categories do not assign a clinical tier. |
| `[reporting]` | `transcript_selection_order` | Ordered array containing every selector in the table below exactly once | Determines the clinical transcript selection order during DNA VCF ingest. The first selector with a matching CSQ row wins; within that selector, VEP impact is ordered HIGH, MODERATE, LOW, then MODIFIER. |
| `[files.dna]` | `keys` | Non-empty unique manifest-key identifiers | Declares the accepted file keys for DNA sample YAML `files`. |
| `[files.rna]` | `keys` | Non-empty unique manifest-key identifiers | Declares the accepted file keys for RNA sample YAML `files`. |
| `[files.required_by_family]` | family arrays | Keys declared for that family's omics category | Establishes the baseline required input files for `panel-dna`, `wgs`, `panel-rna`, and `wts`. ASP-specific requirements can make additional configured keys mandatory. |
| `[analysis.dna]` / `[analysis.rna]` | `types` | Supported application analysis types | Enables the analysis types that the center intends to use for that omics category. |
| `[analysis.<omics>.file_keys]` | one array per enabled type | One or more configured keys for that omics category | Binds each analysis workflow to the manifest field(s) it reads. The first key is the primary path used by single-file consumers such as report images. |
| `[analysis.allowed_by_family]` | one array for every configured assay family | Analysis types declared by the family's omics category | Narrows implemented analysis types by sequencing family. Targeted `panel-rna` can enable fusion, QC, and PGX; only `wts` can enable expression and classification. ASPC create/update validation rejects incompatible selections. |

### Fusion Annotation Vocabulary

Fusion caller IDs have one representation throughout the application. For
example, pipeline values `FusionCatcher`, `fusion-catcher`, and
`fusioncaller_fusion_catcher` all resolve to the configured `fusioncatcher`
ID. The API returns the configured IDs to the filter UI instead of maintaining
a separate frontend list. This keeps checkbox state, persisted sample filters,
and `calls.caller` query values identical. Add a new released caller to
`fusion.callers` before ingesting records produced by it.

Fusion descriptions and frame effects are supplied by the upstream fusion
caller. They do not pass through VEP, the DNA transcript-selection order, or
the `anno_vep` collection.

The application splits each caller description on commas, normalizes terms for
exact case-insensitive comparison, and looks them up in
`fusion.description_terms`. A center may extend these lists when a released
caller database introduces new documented terms. A term must occur in exactly
one group; startup fails on duplicates so the same evidence cannot receive two
meanings. Unknown terms are preserved and displayed neutrally.

Fusion effect display follows one fixed workflow rule: normalized `in-frame`
means in-frame, while every other non-empty effect means out-of-frame. The
TOML vocabulary controls description evidence only; it does not redefine that
frame rule.

### Analysis Availability by Family

`analysis.<omics>.types` defines the implemented vocabulary for an omics
layer. `analysis.allowed_by_family` applies the narrower sequencing-family
contract used by ASPC forms and API validation. This prevents an RNA label
from implying that every RNA assay produces every RNA resource.

| Family | Default allowed analysis | Operational meaning |
| --- | --- | --- |
| `panel-dna` | DNA analysis types listed in TOML | Targeted DNA panels may enable only analyses implemented for DNA. |
| `wgs` | DNA analysis types listed in TOML | WGS uses the DNA workflow vocabulary but may select a different subset per ASPC. |
| `panel-rna` | `FUSION`, `QC`, `PGX` | Targeted fusion panels do not expose expression or classification. |
| `wts` | `FUSION`, `EXPRESSION`, `CLASSIFICATION`, `QC`, `PGX` | Whole-transcriptome configurations may enable expression and classification. |

The resolved ASPC still determines which allowed analyses are active for a
specific sample. A family allowance makes an option valid; it does not enable
that option automatically.

### Transcript Selection Selectors

`reporting.transcript_selection_order` is ordered policy, not an arbitrary
numeric priority. It must contain each selector below exactly once. The default
puts RefSeq/NCBI sources before their Ensembl equivalents.

| Selector | Stored source fields and collections | Candidate requirement | Default position | Notes |
| --- | --- | --- | --- | --- |
| `ncbi_mane_plus_clinical` | `hgnc_genes.refseq_mane_plus_clinical` | An `NM_...` or `NR_...` VEP `Feature` matching the HGNC RefSeq MANE Plus Clinical accession | 1 | Native RefSeq clinical transcript. |
| `ensembl_mane_plus_clinical` | `hgnc_genes.ensembl_mane_plus_clinical` | An `ENST...` VEP `Feature` matching the HGNC Ensembl MANE Plus Clinical accession | 2 | Used only when no native NCBI clinical row is present. |
| `ncbi_mane_select` | `hgnc_genes.refseq_mane_select` | An `NM_...` or `NR_...` VEP `Feature` matching the HGNC RefSeq MANE Select accession | 3 | Native RefSeq MANE Select fallback. |
| `ensembl_mane_select` | `hgnc_genes.ensembl_mane_select` | An `ENST...` VEP `Feature` matching the HGNC Ensembl MANE Select accession | 4 | Used only when no native RefSeq MANE Select row is present. |
| `vep_canonical_protein_coding` | VEP/`anno_vep.CSQ.CANONICAL`, `anno_vep.CSQ.BIOTYPE` | VEP `CANONICAL=YES` and `BIOTYPE=protein_coding` | 5 | Prevents a non-coding VEP canonical row from replacing a protein-coding fallback. |
| `first_protein_coding` | VEP/`anno_vep.CSQ.BIOTYPE` | Any protein-coding VEP CSQ row | 6 | Deterministic biological fallback. |
| `first_available` | VEP/`anno_vep.CSQ[]` | Any VEP CSQ row | 7 | Required terminal fallback. |

### Selection Result Storage

The configured selector is applied during ingest, before analytical filtering.
The selected result is persisted in the following collection fields:

| Collection | Field | Stored value | Relationship to the selector order |
| --- | --- | --- | --- |
| `variants` | `INFO.selected_CSQ` | The compact selected VEP transcript row: `Feature`, `MANE`, `MANE_PLUS_CLINICAL`, HGNC fields, HGVS, consequence, impact, and predictor values. | The row selected by the first matching selector. NCBI selector results use a native RefSeq `Feature`; Ensembl selector results use a native `ENST...` `Feature`. |
| `variants` | `INFO.selected_CSQ_criteria` | One selector identifier from `reporting.transcript_selection_order`. | Records exactly which configured selector selected the row, for example `ncbi_mane_plus_clinical`. |
| `anno_vep` | `CSQ[]` | Every parsed VEP transcript row for the sample VEP version. | Supplies alternate transcript review; it is not re-ranked by the SNV query. |
| transcript detail payload | `transcript_tags` | Current HGNC/MANE and VEP-canonical display markers derived for one returned transcript row. | Allows the UI to display NCBI/Ensembl MANE and VEP canonical badges without persisting mutable HGNC interpretation data in `anno_vep`. |
| transcript detail payload | `canonical_source` and `is_canonical` | Current VEP canonical display provenance. | Derived from stored VEP `CANONICAL=YES` evidence when the payload is read. |

Changing this order changes future-ingest selected transcript provenance and
can alter filtering and report content. Review it as a clinical configuration
change, restart API and workers together, and re-ingest representative
non-production samples before release. Linked VEP MANE accessions remain stored
for review, but they do not change the namespace of the selected `Feature`.

There is no separate center canonical-transcript collection. HGNC/MANE is the
only curated transcript authority; VEP supplies the two deterministic fallback
selectors.

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
9. `reporting.transcript_selection_order` contains every supported selector
   exactly once, including `first_available` as its terminal fallback.
10. `fusion.description_terms` must contain three disjoint exact-term groups.
11. `analysis.allowed_by_family` must define every assay family and may only
    reference analysis types implemented for that family's omics category.

## Assay-Group Registry

Assay groups are deliberately absent from this TOML file. They are not local
labels: an assay group is a persistent clinical scope used by ASPs, ASPCs,
ISGLs, annotations, user access assignments, dashboards, and future
cross-assay queries. System and center-owned groups are registered in the
[application database](assay-groups.md). Existing keys must
remain stable; display names are not clinical join keys.

| Identifier | Workflow scope | Use it for | Do not use it for |
| --- | --- | --- | --- |
| `tumwgs` | Tumour whole-genome workflow | WGS design panels and their annotations/query behaviour | The `wgs` family identifier. |
| `wts` | Whole-transcriptome workflow | WTS design panels and their annotations/query behaviour | The `wts` family identifier. |
| `hematology` | General haematology workflow | Broad haematology panels and their annotations/query behaviour | A physical design panel ID. |
| `myeloid` | Myeloid haematology workflow | Myeloid-specific assay designs and clinical logic | A sequencing family. |
| `lymphoid` | Lymphoid haematology workflow | Lymphoid-specific assay designs and clinical logic | A sequencing family. |
| `solid` | Solid-tumour workflow | Solid tumour panel designs and their annotations/query behaviour | A subpanel such as endometrial or breast. |
| `fusion` | Fusion workflow | RNA fusion assay designs | A particular RNA design panel. |
| `pgx` | Pharmacogenomic workflow | PGX assay designs and their annotations/query behaviour | The `PGX` analysis type. |

The related fields have different responsibilities:

| Field | Examples | Meaning |
| --- | --- | --- |
| `asp_group` | `hematology`, `solid`, `tumwgs`, `myeloid` | Registered assay/workflow scope used to link ASPs, ASPCs, ISGLs, annotations, user access, and query logic. |
| `asp_family` | `panel-dna`, `wgs`, `panel-rna`, `wts` | Sequencing design family. It is not an assay group. |
| `asp_category` | `dna`, `rna` | Omics category that selects the allowed manifest and analysis vocabulary. |
| `subpanel_id` | `base`, `endometrie`, `breast`, `colon` | In-silico clinical target subset within a design panel. `base` means no named subpanel. |

Administrators register additional groups in **Admin > Assay groups** before
selecting them in ASP, ISGL and user-scope forms. ASPCs inherit their ASP's group.
New groups use existing default clinical query behavior unless an explicit
group-specific query policy is configured and reviewed.

## Runtime Resolution

The application exposes `analysis_file_keys(omics, analysis)` and
`primary_analysis_file_key(omics, analysis)` from
`api/config/constants.py`. Ingest parsers, sample file status cards, CNV plot
delivery, report rendering, and sample-omics inference use these accessors;
they do not depend on a hardcoded center file-field name.

Internal collection names are deliberately separate. For example, a center can
rename the DNA coverage manifest key from `cov` to `coverage_json`, while the
parsed data still writes to the software-owned `d4_coverage` collection.

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

> **Warning: Renaming an active manifest key**
>
>
> Existing sample documents retain their historical `files` keys. Plan a
> controlled data migration or retain the old data until historical samples
> no longer require it. Do not change the TOML while active workers are
> ingesting the same watch directory.
>

## Authorization Model

Centers configure permission display categories here. Authorization remains
role-based: permission IDs are assigned to roles and roles are assigned to
users. A category only organizes the administration UI and never grants access
on its own.
