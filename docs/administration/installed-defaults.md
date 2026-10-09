# Installed defaults and demonstration configuration

This reference describes the catalogs supplied by Coyote3 and their behavior on a
fresh installation. Follow [First installation](../deployment/first-installation.md)
to install them. A registered assay group is an organizational scope; it does not
create an assay, enable an analysis, or grant users access to samples.

## Installation contents

| Installation component | Supplied records | Availability |
| --- | --- | --- |
| Assay groups | Nine registered groups, listed below | Standard bootstrap |
| Finding query rules | Eight published SNV sets across four groups, with immutable baseline revisions | Standard bootstrap |
| System roles | 31 role definitions for clinical, configuration, governance and operational responsibilities | Standard bootstrap |
| Initial accounts | One named system administrator and one separate emergency superuser | Operator supplies identities and temporary passwords during bootstrap |
| Demonstration configuration | Two ASPs, two ASPCs, one ISGL, one named subpanel and its assay association, and two published report-rule sets | Only with `--with-demo-center` |
| Knowledgebase references | HGNC genes, VEP metadata and associated diagrams | Separate optional reference installation |

Installed versioned catalogs start at version 1 and are attributed to the named
initial administrator. Query sets start at version 1, revision 1 and carry
`system_installed`; other supported catalogs use `system_managed`. Report-rule
content versions and revisions also start at 1. Reference release identifiers are
preserved. Installation provenance does not establish independent clinical approval.

Bootstrap skips populated collections rather than replacing their contents. The
[installation operations reference](../deployment/installation-operations.md)
describes stage selection and standalone commands. Existing installations use the
documented synchronization workflows; rerunning bootstrap does not reset catalogs.

## Assay groups

| Group ID | Display name | Intended scope | Installed query sets |
| --- | --- | --- | --- |
| `hematology` | Hematology | Hematological assays | Somatic SNV FLT3 extensions; three germline admissions |
| `myeloid` | Myeloid | Myeloid assays | Somatic SNV FLT3 extensions; three germline admissions |
| `lymphoid` | Lymphoid | Lymphoid assays | None; application query defaults apply |
| `solid` | Solid tumors | Solid tumor assays | Somatic SNV regulatory extensions; GERMLINE-filter admission |
| `pgx` | Pharmacogenomics | Pharmacogenomic assays | None; application query defaults apply |
| `tumwgs` | Tumor WGS | Tumor whole-genome assays | Somatic SNV FLT3 extensions; three germline admissions |
| `wts` | Whole transcriptome | Whole-transcriptome assays | None; application query defaults apply |
| `fusion` | Fusion | RNA fusion assays | None; application RNA fusion query defaults apply |
| `demo` | Demo | Demonstration and training assays | None; application query defaults apply |

Groups are independent identifiers, not a hierarchy: `myeloid` and `lymphoid` do
not inherit from `hematology`. The `fusion` group contains RNA fusion assays;
RNA analyses do not include SNVs.
The optional demo assays belong to `hematology` and `wts`, not to `demo`.
See [Assay groups](assay-groups.md) for registration and access-scope management.

## Finding query sets

### Application defaults and group scope

The software supplies a base query even without a database rule document. The base
SNV evidence modes are `paired` for somatic intent and `exception_only` for germline
intent. Population-frequency fields are `gnomad_frequency`, `gnomad_max`,
`exac_frequency` and `thousandG_frequency`; thresholds come from the active sample
filters. No global `default__all__base__germline_snvs` publication is installed.

For paired evidence, a `case` genotype must meet allele-frequency, depth and
alternate-read thresholds. When control genotypes exist, at least one must satisfy
the control-frequency and depth criteria. Absence of a control genotype does not
itself exclude a record. Ordinary population-frequency and consequence criteria
also apply. `exception_only` has no ordinary evidence branch; without admission
exceptions it selects no findings.

Query scope resolves from application defaults through published global, group,
assay and named-subpanel policies. The installed group sets cover all assays and
subpanels in their group unless a more specific policy changes the composition.
`all` means no specific assay; `base` in these query IDs means no specific subpanel.
It is not a named subpanel. No assay-specific or named-subpanel query sets ship.

### Published set identifiers

Each row below represents two separate documents, each with one data type and intent.
Somatic sets use `paired` evidence; germline sets resolve to `exception_only`.

| Group | Somatic set ID | Germline set ID |
| --- | --- | --- |
| `hematology` | `hematology__all__base__somatic_snvs` | `hematology__all__base__germline_snvs` |
| `myeloid` | `myeloid__all__base__somatic_snvs` | `myeloid__all__base__germline_snvs` |
| `tumwgs` | `tumwgs__all__base__somatic_snvs` | `tumwgs__all__base__germline_snvs` |
| `solid` | `solid__all__base__somatic_snvs` | `solid__all__base__germline_snvs` |

### Hematology, myeloid and tumor WGS

Each of these three groups receives the same two somatic exceptions and three germline
exceptions. Conditions within a row are combined with AND; alternative exception rows
can independently match.

| Exception ID | Intent and action | Exact matching criteria |
| --- | --- | --- |
| `flt3_svtype` | Somatic: extend consequence eligibility | `INFO.selected_CSQ.SYMBOL` is `FLT3` and `INFO.SVTYPE` exists. Existence does not require a particular SVTYPE value. |
| `flt3_large_insertion` | Somatic: extend consequence eligibility | `INFO.selected_CSQ.SYMBOL` is `FLT3` and `ALT` matches the regex `[A-Za-z0-9_]{10,200}`. |
| `germline_myeloid_marker` | Germline: admit | `INFO.MYELOID_GERMLINE` equals numeric `1`. |
| `germline_cebpa_filter` | Germline: admit | `INFO.selected_CSQ.SYMBOL` is `CEBPA` and `FILTER` contains `GERMLINE`. |
| `germline_chr1_interval` | Germline: admit | `CHROM` equals the string `1` and numeric `POS` is between `115256521` and `115256537`, inclusive. |

The ALT regex is unanchored: it tests for a matching substring, not an exact
10–200-base insertion length. It does not calculate insertion size or require a
particular caller. The chromosome predicate requires `1`, not `chr1`. The interval
rule contains no reference-genome condition or coordinate conversion; validate its
meaning against the assay's reference build before clinical use.

### Solid tumors

| Exception ID | Intent and action | Exact matching criteria |
| --- | --- | --- |
| `solid_regulatory_tert_nfkbie` | Somatic: extend consequence eligibility | `INFO.selected_CSQ.SYMBOL` is `TERT` or `NFKBIE`, and `consequence_terms` contains `regulatory_region_variant` or `TF_binding_site_variant`. |
| `solid_germline_filter` | Germline: admit | `FILTER` contains `GERMLINE`; no gene condition is imposed by this exception. |

Solid tumors do not receive the myeloid-marker, CEBPA or chromosome-1 admissions.

### Effect on retrieved findings

`extend_consequence` broadens the accepted consequence branch while retaining
ordinary evidence requirements. `admit` adds an alternative to the ordinary
evidence/consequence branch. Neither action removes sample identity, applicable
gene/position restrictions, false-positive/irrelevant exclusions or access checks.
Explicit exclusion exceptions still apply to admitted findings.

!!! warning "Somatic SNV results can include germline findings"
    The dedicated germline workflow is not fully implemented. Effective germline
    admission exceptions also contribute to somatic SNV retrieval for the same
    scope. The three hematology-related scopes above and solid tumors therefore
    include their respective germline admissions in somatic results. Germline
    evidence settings do not replace somatic evidence settings. Inclusion in the
    somatic table does not establish somatic origin.

Lymphoid, PGX, WTS, fusion, demo and newly registered groups receive none of these group
exceptions automatically. No CNV, translocation or RNA fusion rule publications
are included in the standard seed; their implemented base queries remain active.

Use [Finding query rules](query-rules.md) for inherit, extend and replace semantics,
independent review, sample testing and effective-policy previews. Published seed
sets are changed through that governed workflow. Seed sources are
`api/config/bootstrap/reference/query_rule_sets.seed.ndjson` and
`api/config/clinical_query_seed.toml`; the latter supplies installation criteria,
not a runtime center-editable policy.

## Optional demonstration configuration

Pass `--with-demo-center` to the center installer to include this configuration on
a fresh target. It supplies configuration and synthetic report-rule test cases,
not ingested samples or findings. Without this option, bootstrap creates no ASP,
ASPC, ISGL, named subpanel or clinical report-rule set.

### Assays and configurations

| Resource | DNA demonstration | RNA demonstration |
| --- | --- | --- |
| ASP ID and label | `assay_1` — Hema GMS v1 | `assay_rna_1` — Demo RNA WTS |
| Group / family / category | `hematology` / `panel-dna` / `dna` | `wts` / `wts` / `rna` |
| Covered genes | UBA1, APOB, EGFR, PHIP, ASXL2, ASXL1, FLT3, KMT2D, GNB1, TP53 | BCR, ABL1, ETV6, RUNX1 |
| Germline genes | BRCA1 | Empty |
| Expected file keys | `vcf_files`, `cnv`, `cnvprofile`, `cov`, `transloc`, `hrd`, `msi` | `fusion_files`, `expression_path`, `classification_path`, `qc` |
| Required file keys | `vcf_files` | `fusion_files` |
| ASPC ID | `assay_1_base_production` | `assay_rna_1_base_production` |
| Enabled analyses | SNV, CNV, COVERAGE | FUSION, EXPRESSION, CLASSIFICATION, QC |
| Report sections | SNV, CNV | FUSION, EXPRESSION, CLASSIFICATION, QC |

Both ASPs and ASPCs are active. Both configurations use `GRCh38`, `Illumina`,
environment `production`, intent `somatic`, and the unscoped `base` context.
Expected files do not enable analyses by themselves: the DNA ASP, for example,
expects HRD/MSI files but its demo ASPC does not enable those analyses.

The DNA filter defaults are:

| Filter area | Values |
| --- | --- |
| SNV allele fractions | Minimum `0.03`, maximum `1`, maximum control `0.05` |
| SNV evidence | Minimum depth `100`, minimum alternate reads `5`, maximum population frequency `0.01` |
| SNV consequence groups | `splicing`, `stop_gained`, `stop_lost`, `start_lost`, `frameshift`, `inframe_indel`, `missense`, `other_coding` |
| CNV size | Minimum `100`, maximum `1000000` |
| CNV effects and cutoffs | `gain` and `loss`; gain `0.3`, loss `-0.3` |
| Coverage thresholds | Warning `500`, error `100` |

DNA SNV/CNV gene-list selections are empty. RNA fusion caller, description, effect
and gene-list selections are empty; minimum spanning pairs and spanning reads are
both `0`, with no ad hoc gene criteria. Consult
[Filter profile fields](../reference/filter-profile-fields.md) for field semantics.

Both ASPCs have empty verification-sample mappings and demonstration report header,
method and description text. Reporting language is `sv`, plot path is `/tmp`, and
report folders are `demo` and `demo-rna`. These values are examples, not a validated
center reporting configuration. Only production ASPCs are installed; embedded
rule-test fixtures referencing testing contexts do not create testing ASPCs.

### Gene list and named subpanel

The ISGL `hematology_myeloid`, labelled **List A**, is active, public and non-ad-hoc.
It supports `snv`, `cnv` and `fusion`, contains the ten DNA covered genes listed
above, and is associated with group `hematology`, assay `assay_1` and diagnosis
`hematology_myeloid`.

Bootstrap derives one shared named-subpanel definition, `hematology_myeloid`, and
one association to `assay_1` from that diagnosis mapping. It does not create a
separate ASPC or report-rule set for this named subpanel. `base` represents no
specific subpanel and is not registered as another subpanel definition. Review
[Assay setup](assay-setup.md) before configuring a named-subpanel workflow.

### Demonstration report rules

| Published set | Scope | Output behavior |
| --- | --- | --- |
| `assay_1__base__sv` | DNA, `assay_1`, unscoped subpanel, language `sv` | An unconditional introduction evaluated once; an SNV block evaluated per finding emits the gene followed by “contains a reportable small variant.” when the tier is 1, 2 or 3. CNV narrative is declared `none`. |
| `assay_rna_1__base__sv` | RNA, `assay_rna_1`, unscoped subpanel, language `sv` | An unconditional fusion-summary block evaluated once. Expression, classification and QC narrative are declared `none`. |

Each set includes one synthetic no-findings test case. Although their language
scope is `sv`, the supplied demonstration sentences are English. These published
examples exercise report rendering; they are not approved center report wording.
The bootstrap captures their immutable revision baselines. Use
[Clinical reporting rules](../reference/clinical-reporting-rules.md) to prepare,
test, review and publish center-specific content.

## Default roles and initial accounts

Role definitions are installed without creating an account for every role.
The operator supplies a named account assigned `sys_admin` and a separate account
assigned `superuser`. Both require a password change on first sign-in. There are
no bundled usernames or passwords. Routine clinical and governance users require
explicit role and assay/environment scope assignments.

| Responsibility | Installed roles | Intended use |
| --- | --- | --- |
| Platform administration | `sys_admin`, `superuser` | System administration manages accounts, access, controls and operations. Superuser bypasses normal access policies and is reserved for emergency setup/recovery. |
| Account administration | `user_account_manager` | Manage identities and role/scope assignments; password changes use dedicated security workflows. |
| Clinical administration | `admin`, `manager` | Admin manages clinical configuration and reporting/catalog governance. Manager handles samples and configuration within assigned groups. Neither is the general system-administrator role. |
| Resource management | `asp_manager`, `aspc_manager`, `isgl_manager` | Maintain assay definitions, environment-specific configurations and in-silico gene lists respectively. |
| Clinical use | `user`, `intern`, `viewer`, `external` | Standard sample interaction, limited analysis access, read-only sample/report access, and more restricted external read-only access respectively. |
| Development and validation | `developer`, `tester` | Configuration/testing work and functional testing respectively; these are not user-account administration roles. |
| Operations | `operations_viewer`, `app_control_operator`, `monitoring_group` | Read operational/audit diagnostics; change runtime controls and run permitted maintenance; receive system-error notifications respectively. Monitoring membership grants no application operations. |
| Report-rule governance | `clinical_rule_author`, `clinical_rule_reviewer`, `clinical_rule_publisher`, `clinical_rule_tester`, `clinical_rule_viewer` | Author/submit drafts; independently review; publish/retire; validate and preview with samples; inspect content and history. |
| Query-rule governance | `query_rule_author`, `query_rule_reviewer`, `query_rule_publisher`, `query_rule_tester`, `query_rule_viewer` | Create/edit drafts; independently approve; publish/retire; test with scoped samples; inspect versions and effective previews. |
| Public catalog governance | `catalog_author`, `catalog_reviewer`, `catalog_publisher`, `catalog_viewer` | Author, review, publish or read catalog content according to the assigned responsibility. |

Author, reviewer and publisher roles support distinct responsibilities. Assigning
multiple roles does not waive independent-review checks. Query-rule roles and
report-rule roles are separate; access to one editor does not imply access to the
other. The generated [System role catalog](system-role-catalog.md) is the complete
role-by-role reference. Permission definitions are maintained separately in the
[permission catalog](permission-catalog.md).

## Other bundled defaults and references

Application-owned capabilities define DNA families `panel-dna`, `wes`, `wgs` and
RNA families `panel-rna`, `wts`; environments are `production`, `development`,
`testing`, `validation`. Supported analysis IDs, ingest file keys, caller support
and transcript precedence are software contracts, not editable database catalogs.
See [Clinical vocabulary](clinical-vocabulary.md),
[Sample manifest](../reference/sample-manifest.md) and
[Clinical query policy](../configuration/clinical-query-policy-file.md).

Optional reference installation loads the bundled HGNC snapshot and VEP releases
98–116, including their diagram assets. Source attribution and release hashes are
recorded under `api/config/bootstrap/reference/`. These snapshots do not install
every external knowledgebase used by the application; follow the relevant
[knowledgebase operations guides](../operations/README.md) for separate updates.

The baseline contains no patient samples, findings, annotations, classifications,
saved reports or published public assay catalog. Configure and publish the catalog
separately. Center configuration templates provide editable examples; complete
the [clinical configuration sequence](clinical-configuration-resources.md) and
validate each assay before using it for clinical work.
