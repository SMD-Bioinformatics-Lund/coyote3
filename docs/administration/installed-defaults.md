# Installed defaults and demonstration configuration

This reference describes the catalogs supplied by Coyote3 and their behavior on a
fresh installation. Follow [First installation](../deployment/first-installation.md)
to install them. A registered assay group is an organizational scope; it does not
create an assay, enable an analysis, or grant users access to samples.

## Installation contents

| Installation component | Supplied records | Availability |
| --- | --- | --- |
| Assay groups | Five registered biological groups, listed below | Default first installation; disable with `--skip-application` |
| Finding query rules | Six published SNV sets across hematology, myeloid and solid, with immutable baseline revisions | Default first installation; disable with `--skip-application` |
| System roles | 32 role definitions for clinical, configuration, governance and operational responsibilities | Standard bootstrap |
| Initial accounts | One named system administrator and one separate emergency superuser | Operator supplies identities and temporary passwords during bootstrap |
| Starter demonstration | One connected resource bundle: 11 assays, six diagnoses, eight lists, 39 configurations, query and reporting rules, 15 catalog offerings and two default samples. The catalog is published if no public catalog exists; otherwise it remains a draft. | Default first installation; disable with `--skip-demo`. Later additions use authenticated maintenance or Administration → Demo installation |
| Knowledgebase references | HGNC genes, VEP metadata and associated diagrams | Default first installation; disable with `--skip-knowledgebase` |

Installed versioned catalogs start at version 1 and are attributed to `system`.
Maintenance updates identify the authenticated administrator. Query sets start at version 1, revision 1 and carry
`system_installed`; protected baseline catalogs use `system_managed`. Starter demo
configuration records carry `system_installed` and are read-only in the UI and API.
Demo samples remain usable for review and reporting. See
[record attribution](record-attribution.md) for creator/updater fields and historical data.
Report-rule
content versions and revisions also start at 1. Reference release identifiers are
preserved. Installation provenance does not establish independent clinical approval.

Existing deployments skip initial bootstrap completely. Populated reference collections
on fresh deployments are preserved. The
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

Biological groups define registration and access scope. `myeloid` and `lymphoid`
remain available for legacy samples. New demo assays use `hematology` or `solid`;
sequencing family and enabled analyses are configured separately. The
[synthetic workflow bundle](../testing/clinical-workflow-demo.md) demonstrates
shared diagnoses and gene lists across panel, WGS and RNA assays.
See [Assay groups](assay-groups.md) for registration and access management.

## Finding query sets

### Application defaults and group scope

For the complete selection conditions for SNVs, CNVs, RNA fusions and DNA
translocations, see [application base queries by analysis](query-rules.md#application-base-queries-by-analysis).
The group publications listed below are applied on top of those application defaults.

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
assay and named-diagnosis policies. The installed group sets cover all assays and
diagnoses in their group unless a more specific policy changes the composition.
`all` means no specific assay; `base` in these query IDs means no specific diagnosis.
It is not a named diagnosis. No assay-specific or named-diagnosis query sets ship.

### Published set identifiers

Each row below represents two separate documents, each with one data type and intent.
Somatic sets use `paired` evidence; germline sets resolve to `exception_only`.

These are additional group policies. Application defaults also provide the base
SNV, CNV, fusion and translocation queries for groups without published policies.
Registering a new group does not require a code change; configure its exceptions
in [Finding query rules](query-rules.md).

| Group | Somatic set ID | Germline set ID |
| --- | --- | --- |
| `hematology` | `hematology__all__base__somatic_snvs` | `hematology__all__base__germline_snvs` |
| `myeloid` | `myeloid__all__base__somatic_snvs` | `myeloid__all__base__germline_snvs` |
| `solid` | `solid__all__base__somatic_snvs` | `solid__all__base__germline_snvs` |

### Hematology and retained myeloid scope

Hematology and myeloid receive two somatic exceptions and three germline
exceptions. Conditions within a row are combined with AND; alternative exception rows
can independently match.

| Exception ID | Intent and action | Exact matching criteria |
| --- | --- | --- |
| `flt3_svtype` | Somatic: extend consequence eligibility | `genes` contains `FLT3` and `INFO.SVTYPE` exists. Existence does not require a particular SVTYPE value. |
| `flt3_large_insertion` | Somatic: extend consequence eligibility | `genes` contains `FLT3` and `ALT` matches the regex `[A-Za-z0-9_]{10,200}`. |
| `germline_myeloid_marker` | Germline: admit | `INFO.MYELOID_GERMLINE` equals numeric `1`. |
| `germline_cebpa_filter` | Germline: admit | `genes` contains `CEBPA` and `FILTER` contains `GERMLINE`. |
| `germline_chr1_interval` | Germline: admit | `CHROM` equals the string `1` and numeric `POS` is between `115256521` and `115256537`, inclusive. |

The ALT regex is unanchored: it tests for a matching substring, not an exact
10–200-base insertion length. It does not calculate insertion size or require a
particular caller. The chromosome predicate requires `1`, not `chr1`. The interval
rule contains no reference-genome condition or coordinate conversion; validate its
meaning against the assay's reference build before clinical use.

### Solid tumors

| Exception ID | Intent and action | Exact matching criteria |
| --- | --- | --- |
| `solid_regulatory_tert_nfkbie` | Somatic: extend consequence eligibility | `genes` contains `TERT` or `NFKBIE`, and `consequence_terms` contains `regulatory_region_variant` or `TF_binding_site_variant`. |
| `solid_germline_filter` | Germline: admit | `FILTER` contains `GERMLINE`; no gene condition is imposed by this exception. |

`solid` does not receive the myeloid-marker, CEBPA or chromosome-1 admissions.

### Effect on retrieved findings

`extend_consequence` broadens the accepted consequence branch while retaining
ordinary evidence requirements. `admit` adds an alternative to the ordinary
evidence/consequence branch. Neither action removes sample identity, applicable
gene/position restrictions, false-positive/irrelevant exclusions or access checks.
Explicit exclusion exceptions still apply to admitted findings.
SNV `exclude_flags` selections also apply after admission.
Their choices come from the [configured flag metadata](../configuration/filter-flag-metadata-file.md#snv-flag-filtering-and-rule-conditions).

Somatic and germline SNV review use separate filter profiles. During configuration
compilation, the resolver also adds effective germline exceptions to the somatic
SNV policy for the same scope. The somatic evidence mode remains unchanged.
This applies to the hematology, myeloid and solid policies above. Appearing in a
workspace does not establish a finding's biological origin.

Lymphoid, PGX and newly registered groups receive none of these group
exceptions automatically. No CNV, translocation or RNA fusion rule publications
are included in the standard seed; their implemented base queries remain active.

Use [Finding query rules](query-rules.md) for inherit, extend and replace semantics,
independent review, sample testing and effective-policy previews. Published seed
sets are changed through that governed workflow. Seed sources are
`api/bootstrap/catalogs/reference/query_rule_sets.seed.ndjson` and
`api/bootstrap/catalogs/reference/clinical_query_seed.toml`; the latter supplies installation criteria,
not a runtime center-editable policy.

## Low-level bootstrap configuration examples

`api/bootstrap/catalogs/demo_center/` contains configuration fixtures for isolated
bootstrap and collection-import checks. These fixtures are not installed by the
starter demo workflow and do not describe its catalog.

For installed assay names, diagnosis associations, gene lists, configurations and
sample scenarios, use the [synthetic workflow reference](../testing/clinical-workflow-demo.md#demo-resource-relationships).
The [demo bundle reference](../testing/demo-data-bundle.md) describes the raw files
and expected database records used by ingest and offline validation.

## Default roles and initial accounts

Role definitions are installed without creating an account for every role.
Bootstrap creates `coyote3.sysadmin` assigned `sys_admin` and `coyote3.superuser`
assigned `superuser`. Independent temporary passwords are generated and printed once
after successful account creation; there are no fixed passwords. Both require a
password change on first sign-in. Routine clinical and governance users require
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

Center setup (`--setup-center`) loads the bundled HGNC snapshot and VEP releases
98–116, including their diagram assets. Source attribution and release hashes are
recorded under `api/bootstrap/catalogs/reference/`. These snapshots do not install
every external knowledgebase used by the application; follow the relevant
[knowledgebase operations guides](../operations/README.md) for separate updates.

The application baseline contains group and query catalogs, without samples or
assay offerings. The separately installed starter demo adds synthetic samples,
findings and catalog offerings as described above. Neither supplies patient data
or clinically approved assay configurations. Complete the
[clinical configuration sequence](clinical-configuration-resources.md) and validate
each assay before using it for clinical work.
