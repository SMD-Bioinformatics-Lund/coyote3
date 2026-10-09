# Center Vocabulary Configuration

`clinical_vocabulary.toml` in the external center directory is the vocabulary contract.
The bundled `api/config/center/clinical_vocabulary.toml` provides complete examples.
See [persistent configuration](../deployment/center-configuration.md#persistent-local-files-or-a-git-configuration-release)
for local files, pinned Git sources, deployment, and upgrade handling.
It is loaded and validated when the API or a worker starts. A malformed
configuration prevents startup rather than allowing an ingest or login flow to
run with an ambiguous contract.

## Format, required values and defaults

The center file contains clinical policy and presentation metadata. Application
capabilities are loaded separately from `api/config/clinical_capabilities.toml`.
That release-owned file defines categories, families, scopes, the base subpanel,
environments, authentication providers, gene-list types, supported fusion callers,
manifest keys, required-file baselines, transcript selection order and analysis mappings. Center configuration
cannot redefine these sections, even with identical values.

| Center setting | Required? | Behavior when omitted |
| --- | --- | --- |
| `fusion.description_terms` | Yes | Requires disjoint `important`, `not_important` and `context` term lists. |
| `snv.callers`, `cnv.callers`, `translocation.callers` | No | Empty presentation registries; historical provenance is preserved. |

TOML dotted headings group fields. Unknown keys and application-owned sections
in the center file prevent startup. Authentication is selected separately through
`AUTHENTICATION_PROVIDERS`; assay capabilities are selected through ASP/ASPC records.
For caller-specific flag text, see the
[flag metadata reference](../configuration/filter-flag-metadata-file.md).

## Runtime consumers

The combined application vocabulary and center policy have the following consumers. Configuration
does not implement a parser, finding type, authentication protocol, or sequencing
capability. Retain the software-supported semantics when changing identifiers.

| Vocabulary | Application consumer | Effect and limits |
| --- | --- | --- |
| `assay.categories`, `families`, `family_categories`, `family_scopes` | `api/config/constants.py`, assay/sample contracts, and ingest helpers | ASP choices, category validation, family-to-omics mapping, and sample sequencing scope. |
| `assay.base_subpanel_id` | `SUBPANEL_BASE_ID`, ASPC resolution, catalog and reporting services | Identifies the application-owned base configuration scope. |
| `environment.options`, `default` | Environment normalization, sample catalog defaults, ingest, user scopes, and public catalog | Defines application-owned clinical profiles and their default. This does not replace the deployment's `ENV_NAME`. |
| `authentication.providers` | Authentication constants and login configuration | Defines implemented local/LDAP providers; `AUTHENTICATION_PROVIDERS` can override it for a deployment. |
| `genelist.standard_types`, `adhoc_types` | Gene-list contracts, managed forms, and filter normalization | Curated and ad-hoc gene-list choices. |
| `files.*.keys`, `files.required_by_family` | Sample contracts, ASP required-file defaults, manifest normalization and ingest | Defines pipeline file keys and baseline required inputs. ASP records can specify their required files. |
| `analysis.*.types`, `file_keys`, `allowed_by_family` | Analysis constants, ingest preload bindings, ASPC validation and managed forms | Binds implemented analyses to files and assay families. Adding a name does not create ingest or review support. |
| Application `reporting.transcript_selection_order` | `api/application/ingest/parsers.py` | Fixed order for persisted transcript evidence during ingest. Not editable by centers; existing findings retain their selected transcript. |
| `fusion.callers` | Fusion contracts, query builder, managed filters, RNA view contexts and caller-specific flag validation | Normalizes caller IDs and validates supported fusion caller selections. |
| `fusion.description_terms` | RNA view contexts and fusion annotation badges | Categorizes caller evidence text for display; it is not a reporting-rule predicate. |
| `snv.callers`, `cnv.callers`, `translocation.callers` | Filter metadata validation and SNV/CNV/translocation flag display | Registers caller-specific explanations. Historical caller names are retained; these lists do not filter findings or reject stored provenance. |

## Whole-exome family

The bundled vocabulary defines `wes` with DNA category and sequencing scope `wes`.
Its baseline required input is `vcf_files`. The family permits implemented DNA
analyses; the ASP and ASPC select the analyses actually provided by the pipeline.
This permission does not establish that every analysis is validated for exome data.

Define the ASP's `covered_genes` from its capture design. Gene-list coverage uses
those declared genes; WES does not inherit the whole-genome assumption that every
selected gene is covered. Existing WGS-specific CNV query behavior is unchanged.
WES is supplied by the application release; centers create ASPs using this family
without adding vocabulary entries.

## Caller registries and flag descriptions

Fusion supports the implemented caller IDs `arriba`, `fusioncatcher`, and
`starfusion`. These IDs are supplied by the application; do not add `fusion.callers`
to the center file. Select from them through assay and sample filter settings.

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
```

### Caller filtering and provenance

| Analysis | Implemented caller behavior | Effect of the vocabulary registry |
| --- | --- | --- |
| SNV | Ingest splits the combined VCF's `INFO.variant_callers` on `\|` and preserves all callers. No caller query filter is implemented. | Optional caller-specific flag descriptions only. |
| CNV | Normalized JSON preserves `callers`. Query-policy exceptions can match this array; the ordinary CNV filters have no caller selector. | Optional caller-specific flag descriptions; it does not configure those query exceptions. |
| Translocation | Views can display recorded caller provenance. No caller query filter is implemented. | Optional caller-specific flag descriptions only. |
| Fusion | The `fusion_callers` filter and fusion query-policy exceptions match `calls[].caller`. | Application-owned caller IDs; centers select supported callers in assay/sample filters. |

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
# Center clinical policy and presentation metadata. Technical identifiers are application-owned.

[snv]
callers = []

[cnv]
callers = []

[translocation]
callers = []

[fusion.description_terms]
important = [
  "mitelman", "18cancers", "known", "oncogene", "cgp", "cancer", "cosmic",
  "gliomas", "oesophagus", "tumor", "pancreases", "prostates", "tcga", "ticdb", "high",
]
not_important = [
  "1000genomes", "banned", "bodymap2", "cacg", "conjoing", "cortex", "cta", "ctb",
  "ctc", "ctd", "distance1000bp", "ensembl_fully_overlapping",
  "ensembl_same_strand_overlapping", "gtex", "hpa", "matched-normal", "mt",
  "non_cancer_tissues", "non_tumor_cells", "pair_pseudo_genes", "paralogs",
  "readthrough", "refseq_fully_overlapping", "rp11", "rp", "rrna", "similar_reads",
  "similar_symbols", "ucsc_fully_overlapping", "ucsc_same_strand_overlapping",
]
context = [
  "distance100kbp", "distance10kbp", "duplicates", "ensembl_partially_overlapping",
  "fragments", "healthy", "short_repeats", "long_repeats", "partial-matched-normal",
  "refseq_partially_overlapping", "short_distance", "ucsc_partially_overlapping",
]

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
| `[fusion.description_terms]` | `important`, `not_important`, `context` | Unique lowercase exact terms with no term repeated across groups | Categorizes comma-delimited caller annotations in both the fusion filter selector and table tooltips. Important terms are green, not-important/artifact terms are red, contextual terms are gray, and unlisted terms remain neutral. Selecting terms applies exact, case-insensitive token filters; these categories do not assign a clinical tier. |

### Fusion Annotation Vocabulary

Fusion caller IDs have one representation throughout the application. For
example, pipeline values `FusionCatcher`, `fusion-catcher`, and
`fusioncaller_fusion_catcher` all resolve to the configured `fusioncatcher`
ID. The API returns the configured IDs to the filter UI instead of maintaining
a separate frontend list. This keeps checkbox state, persisted sample filters,
and `calls.caller` query values identical. Supporting another caller requires an
application release with validated ingestion and query behavior; editing center
configuration cannot add that support.

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
| `wes` | DNA analysis types defined by the release | Exome capture uses the ASP’s declared covered genes. |
| `wgs` | DNA analysis types listed in TOML | WGS uses the DNA workflow vocabulary but may select a different subset per ASPC. |
| `panel-rna` | `FUSION`, `QC` | Targeted fusion panels do not expose expression or classification. |
| `wts` | `FUSION`, `EXPRESSION`, `CLASSIFICATION`, `QC` | Whole-transcriptome configurations may enable expression and classification. |

The resolved ASPC still determines which allowed analyses are active for a
specific sample. A family allowance makes an option valid; it does not enable
that option automatically.

### Transcript Selection Selectors

`reporting.transcript_selection_order` belongs to the application release in
`api/config/clinical_capabilities.toml`. Centers cannot change its order. It puts
RefSeq/NCBI sources before their Ensembl equivalents. Within a selector, VEP impact
is ordered HIGH, MODERATE, LOW, then MODIFIER.

Tumor-type wording for automatic Tier III annotations belongs to published
[reporting rules](../reference/clinical-reporting-rules.md), under
`terminology.automatic_annotation_tumor_type`. It is not vocabulary configuration.

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

1. Required center policy tables must be present; application-owned tables must be absent.
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
| `asp_family` | `panel-dna`, `wes`, `wgs`, `panel-rna`, `wts` | Sequencing design family. It is not an assay group. |
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

Manifest identifiers and collection names are separate application contracts.
For example, `cov` maps to the D4 coverage ingest workflow and `d4_coverage`
storage. Centers cannot rename that manifest key through vocabulary configuration.

## Change Procedure

1. Edit only center policy fields in a private configuration release.
2. Review evidence categorization and caller display metadata with the clinical owner.
3. Validate the release against the target application version.
4. Recreate API, worker, beat and monitor together.
5. Verify affected ingest, review and reporting workflows with synthetic fixtures.

Creating an ASP, assay group, subpanel or ISGL uses administration workflows and
supported application identifiers; it does not require editing the capability file.
See [configuration upgrade](../deployment/center-configuration.md#application-owned-definitions)
for removing technical definitions from older center files.

## Authorization Model

Centers configure permission display categories here. Authorization remains
role-based: permission IDs are assigned to roles and roles are assigned to
users. A category only organizes the administration UI and never grants access
on its own.
