# Clinical resource fields and defaults

ASP, ASPC and ISGL records are maintained through application forms and governed
workflows. They are not files that a deploying center must place in the configuration
directory. Use [assay setup](assay-setup.md) for creation order and
[resource responsibilities](clinical-configuration-resources.md) for dependencies.

The tables describe the typed record contract and important normalization behavior.
Forms may supply explicit values; those values take precedence over omission defaults.
Passing field validation does not bypass active-resource, permission, scope or
publication checks. The linked generated schemas list every persisted field,
including lifecycle metadata that operators should not author.

## Assay / ASP

An ASP defines the physical assay and its input policy. Full contract:
[`assay_specific_panels`](../reference/mongodb-collections.md#assay_specific_panels).

| Field | Requirement / omission behavior | Meaning and effect |
| --- | --- | --- |
| `asp_id` | Required; no default | Stable assay identifier referenced by configurations and samples. |
| `asp_group` | Required; no default | Registered active group, not the sequencing family. |
| `asp_family`, `asp_category` | Required; no default | Compatible family and DNA/RNA category from the vocabulary. |
| `display_name` | Required; no default | Human-readable assay name. |
| `description` | Optional; null | Assay description. |
| `expected_files` | Omitted selects category defaults; explicit `[]` remains empty | Allowed input keys. Expected does not by itself mean mandatory. |
| `required_files` | Contract default `[]` | Mandatory keys, all of which must also be expected. Review the setup form's explicit selections. |
| `covered_genes`, `germline_genes` | Optional; each `[]` | Physical gene scope; missing genes do not imply genome-wide validation. |
| `accredited` | Optional; `false` | Center-declared accreditation status, not approval conferred by the application. |
| `kit_name`, `kit_type`, `kit_version`, `capture_method` | Optional; null | Producer/design descriptions; no names are inferred. |
| `platform`, `read_mode` | Optional at the record boundary; null | Supported platform and compatible read mode. Read technology is derived when platform is present. |
| `read_length`, `target_region_size` | Optional; null | Design read length and target size; preserve unknown values rather than zero. |
| `igv` | Optional; null | Alignment viewer paths, detailed in [alignment references](../reference/sample-manifest.md#alignment-references-for-igv). |
| `is_active` | Contract default `true` | Availability is also subject to the group and setup activation checks. |

Changing file policy affects subsequent validation. It does not manufacture missing
sample evidence. Changing display text does not change the stable assay identity.

## Assay configuration / ASPC

An ASPC binds review and reporting settings to an assay, subpanel and clinical
environment. Full contract: [`asp_configs`](../reference/mongodb-collections.md#asp_configs).

| Field | Requirement / omission behavior | Meaning and effect |
| --- | --- | --- |
| `aspc_id`, `asp_id`, `asp_group`, `asp_category`, `environment`, `display_name` | Required; no default | Configuration identity, parent assay and clinical scope. Related identities must agree. |
| `subpanel_id` | Defaults to the configured Base ID | Named scopes need an eligible definition and assay association. |
| `analysis_types` | Contract default `[]`, followed by workflow validation | Analyses enabled for review; selections must fit the assay's files and family. |
| `analysis_intents` | Contract default `['somatic']`, then normalized for the assay | DNA analysis intent; use the form's applicable choices and [filter field reference](../reference/filter-profile-fields.md). |
| `filters` | Required; no universal filter object | [DNA/RNA field defaults](../reference/filter-profile-fields.md); initializes sample filters at ingest. |
| `reporting` | Required | Report content configuration; detailed below. |
| `use_diagnosis_genelist` | Optional; `false` | Enables the diagnosis-dependent gene-list behavior. |
| `verification_samples` | Optional; `{}` | Configured verification references; an empty map supplies none. |
| `description`, `reference_genome`, `platform` | Optional; null | Configuration metadata; applicable vocabulary and compatibility checks remain enforced. |
| `catalog.is_public` | Defaults to `true` | Visibility eligibility only; does not publish a catalog entry. |
| `is_active` | Contract default `true` | Active configuration must satisfy the relevant workflow checks. |

### Reporting fields

| Field within `reporting` | Required / default | Effect |
| --- | --- | --- |
| `report_sections` | Optional; `[]` | Selected analysis sections, constrained by enabled analyses. |
| `reportable_tiers.SNV`, `reportable_tiers.FUSION` | Optional; each `[1, 2, 3]` | Accepted values 1–4. Explicit `[]` excludes that type; it does not restore defaults. |
| `language` | Optional; `sv` | Normalized language tag, 2–16 characters; selects compatible published rules. |
| `report_header`, `report_method`, `report_description` | Required, nonempty | Approved report metadata; not generated from an assay's name. |
| `plots_path`, `report_folder` | Required, nonempty | Report locations; saving additionally constrains the output folder to the report root. |

Creating a new ASPC revision does not silently replace a sample's recorded revision
or saved filters. Follow the explicit sample workflow for an intended configuration
change. Saved reports retain their captured context. See [report snapshots](../reference/report-snapshots.md).

## Gene list / ISGL

An ISGL selects genes for supported analyses. Full contract:
[`insilico_genelists`](../reference/mongodb-collections.md#insilico_genelists).

| Field | Requirement / omission behavior | Meaning and effect |
| --- | --- | --- |
| `isgl_id`, `name`, `displayname` | Required; no default | Stable key, name and displayed label. Note the exact `displayname` spelling. |
| `list_type` | Supply explicitly | Omission/null initially selects all configured types, which can fail the standard/ad-hoc compatibility check. Use only the intended supported types. |
| `adhoc` | Optional; `false` | Chooses standard versus ad-hoc type validation. |
| `genes`, `germline_genes` | Optional; each `[]` | Selected genes; an empty array adds no genes. |
| `asp_ids`, `asp_groups` | Contract default `[]`; eligibility validated by workflow | Assay/group bindings. Explicit `asp_ids` and `asp_groups` must each be nonempty and contain valid identifiers; unrelated lists are not offered. |
| `diagnosis`, `aliases` | Optional; each `[]` | Diagnosis scope and alternate lookup/display names. |
| `is_public` | Optional; `false` | Public-list eligibility; independent from clinical selection. |
| `is_active` | Optional; `true` | Whether the list can be selected, subject to eligibility. |

Creating a list does not select it for any ASPC or existing sample. Configure that
selection separately. The [gene-list guide](../user-guide/gene-lists-and-assay-context.md)
explains standard, ad-hoc and diagnosis-based selection.

## Other clinical and access records

| Resource | Field and behavior reference | Creation/change procedure |
| --- | --- | --- |
| Assay groups | [Group fields](assay-groups.md), [stored contract](../reference/mongodb-collections.md#assay_groups) | Group registration and availability changes. |
| Subpanel definitions and associations | [Subpanel fields](assay-subpanels.md) | Create shared definitions, then enable assay associations; Base is implicit. |
| Clinical rule sets | [Rule document, blocks and tests](../reference/clinical-reporting-rules.md) | Draft, validate, independently review and publish. |
| Public catalog | [Catalog fields and identity](public-assay-catalog.md) | Separate draft, review and publication. |
| Users, roles and permissions | [Access model](permissions-and-access.md), [permission catalog](permission-catalog.md) | [Account and role administration](administration-guide.md#1-users-roles-and-permissions). |
| Application controls | [Control keys and defaults](application-controls.md) | Authorized runtime-control edits. |

Revision numbers, actors, timestamps, system ownership and retirement metadata
are maintained by the relevant service. Do not copy them from another center's
export or reset them to make a clinical revision appear newly installed.
