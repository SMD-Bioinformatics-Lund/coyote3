# Center configuration files

Each deployment keeps its reviewed center configuration outside the application
checkout, either as local files or as a release staged from a separate Git
repository. Application upgrades reuse this directory. The files under
`api/config/center/` are bundled examples, not the center's persistent configuration.

> **Warning: Deploy the directory as one configuration unit**
>
>
> API, Celery worker, beat scheduler, and frontend-facing public endpoints
> must use the same center configuration release. Compose mounts it read-only
> at `/app/center-config`. Recreate these services together when changing releases;
> clinical vocabulary is loaded at process startup. Documentation includes center
> identity at build time, so rebuild the documentation image when contacts change.
>

## Ownership Boundary

| Location | Owner | Purpose | Edit for a center deployment? |
| --- | --- | --- | --- |
| External center directory | Deploying center | Clinical vocabulary, input field names, public contact content, and caller-specific flag wording. | Yes, through reviewed configuration releases. |
| `api/config/center/` | Coyote3 software | Complete example files for initial configuration. | Copy once; edit the external copy. |
| `api/config/collections.toml` | Coyote3 software | Physical collection mappings. | No. Centers select database names and URIs through the environment. |
| `api/config/application_metadata.py` | Coyote3 software | Product description, repository, licence, issue, and support-request URLs. | No. This identifies the Coyote3 codebase. |
| `api/config/constants.py` | Coyote3 software | Supported workflow semantics, data-model values, validators, permission categories, and sequencing-platform capabilities. | No. Extend the software when a new semantic capability is needed. |
| `api/config/runtime_settings.py` | Coyote3 software | Environment-derived runtime, security, cache, mail, and service settings. | No. Supply the documented environment values instead. |

## Directory Layout

```text
api/config/
  application_metadata.py       # repository-owned product metadata
  app_config.py                 # public runtime configuration facade
  runtime_settings.py           # environment-derived runtime setting classes
  constants.py                  # software-owned semantic constants
  collections.toml              # software-owned physical collection mappings
  loaders/                      # Python loaders for center-owned assets
  center/
    contact.toml                # public center identity and support contacts
    clinical_vocabulary.toml    # clinical policy and presentation metadata
    filter_flag_metadata.yaml   # human-facing VCF filter badge metadata
```

## Persistent local files or a Git configuration release

Copy the examples once into a private working directory outside the checkout,
then edit the three TOML files and the filter metadata YAML:

```bash
mkdir -p /srv/coyote3/center-config-work
cp api/config/center/{contact.toml,clinical_vocabulary.toml,filter_flag_metadata.yaml} \
  /srv/coyote3/center-config-work/

.venv/bin/python scripts/deployment/prepare_center_config.py \
  --source /srv/coyote3/center-config-work \
  --destination /srv/coyote3/center-releases/reviewed-001
```

Alternatively, stage the same files from a separate GitHub or other Git repository:

```bash
.venv/bin/python scripts/deployment/prepare_center_config.py \
  --source https://github.com/EXAMPLE/center-configuration.git \
  --revision FULL_40_CHARACTER_COMMIT_SHA \
  --subdirectory center \
  --destination /srv/coyote3/center-releases/reviewed-001
```

Replace the repository URL, commit ID, and paths. SSH repositories are supported;
use an SSH agent or Git credential helper for private access. Do not embed tokens
in URLs. The command retrieves only the three data files, validates them with the
installed application, writes a SHA-256 manifest, and refuses an existing destination.
A branch name, tag, or shortened commit ID is not accepted. No remote configuration
is downloaded during application startup or requests.

Set the private Compose environment file to the reviewed release:

```dotenv
COYOTE3_CENTER_CONFIG_HOST_DIR=/srv/coyote3/center-releases/reviewed-001
```

API, worker, beat, and monitor mount this directory read-only. The documentation
build receives the same directory as its `center_config` build context. Host-run
commands use `COYOTE3_CENTER_CONFIG_DIR` instead:

```bash
export COYOTE3_CENTER_CONFIG_DIR=/srv/coyote3/center-releases/reviewed-001
```

Compose supplies the documentation build context automatically. A standalone
documentation image build must supply it explicitly:

```bash
docker build -f docker/Dockerfile.docs \
  --build-context center_config=/srv/coyote3/center-releases/reviewed-001 \
  -t coyote3-docs:local .
```

An explicit directory must contain all three files; missing files fail startup
instead of falling back to bundled examples. `collections.toml` is always loaded
from the application package, even if the external directory contains a file with
that name. When no external directory is selected, development uses the bundled
examples. Host directory traversal and file-read permissions must permit the
configured container UID/GID; do not put credentials in these public configuration files.

On application upgrade, retain the environment setting and center release. Run
preflight with the new application version before deployment. If validation requires
new keys, add them to a new center release and review the diff; do not recopy the
examples over existing configuration. Rollback selects the previous compatible
application and center release together.

## New-center configuration review

Complete this review before building the production images. The shipped values
include example contacts, caller identifiers, and clinical policy; they require
review before use at a laboratory.

| File or setting | Required review | Deployment action |
| --- | --- | --- |
| `contact.toml` | Organization, department, support contacts, named recipients, and service hours. | Edit the external copy and keep `organization.name` aligned with `ORGANIZATION_NAME`. Rebuild documentation when identity changes. |
| `clinical_vocabulary.toml` | Fusion evidence terms and optional DNA caller metadata. | Review display effects and validate against the application's fixed capabilities. |
| `api/config/collections.toml` | Application-owned physical collection mappings. | Do not edit for a center. Set database names and connection strings in the environment file. |
| `filter_flag_metadata.yaml` | Labels, severity, descriptions, and hidden flags for the center's pipeline FILTER values. | Review explanations against actual pipeline output. These settings affect presentation, not finding admission. |
| Private environment file | All four MongoDB URI/name pairs, organization name, public URL, TLS proxy settings, authentication, mail, integrations, secrets, storage, and network. | Start from `deploy/env/example.env`; use separate values and storage for each deployment. |

ASP, ASPC, ISGL, assay groups, subpanels, clinical report rules, user accounts,
roles, and public assay catalog content are managed database resources. They are
not additional TOML files. Bootstrap the system catalogs and initial accounts,
then install the reviewed clinical configuration in the
[required creation sequence](required-data.md#required-creation-sequence).

Validate the edited files from a checkout with the development dependencies:

```bash
PYTHON_BIN=.venv/bin/python bash scripts/deployment/center_preflight.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml
```

The loaders check supported structures and values. Tests and preflight do not
establish that the selected clinical policy is appropriate for a center. Record
that review separately and complete the
[deployment acceptance checklist](acceptance-checklist.md).

## Configuration Model

Coyote3 separates deployment wiring, center-owned configuration, and software
contracts. This prevents a local deployment choice from silently changing a
clinical workflow or a security rule.

| Layer | Location | Owner | Typical contents | Change method |
| --- | --- | --- | --- | --- |
| Runtime settings | A copied `deploy/env/example.env` file | Platform administrator | Database connection, secrets, public mount, paths, resource limits, local timezone | Update the environment and recreate affected containers. Rebuild images when a changed value is also a build argument. |
| Center configuration | External directory selected by `COYOTE3_CENTER_CONFIG_HOST_DIR` | Center clinical and technical owners | Clinical policy, contacts, DNA caller metadata, filter explanations | Validate a reviewed release and recreate API, worker, beat, and monitor. Rebuild documentation for changed contact content. |
| Software contract | Python modules under `api/config/` and typed contracts | Coyote3 maintainers | Implemented analysis types, authentication mechanisms, permission semantics, persistence schemas | Change code, tests, and release documentation. |

The complete environment-variable table is maintained in
[Configuration and Environments](configuration-reference.md). This page
documents the center-owned TOML and YAML files.

> **Note: Keep referenced identifiers stable**
>
>
> An identifier referenced by an ASP, ASPC, ISGL, sample manifest, report,
> or historical sample is part of the clinical record. Do not rename it for
> presentation purposes. Create a reviewed replacement and plan a migration
> when a meaning must change.
>

## `contact.toml`

See the [contact.toml reference](../configuration/contact-file.md) for fields,
requirements, omission behavior, examples and validation.

## `clinical_vocabulary.toml`

This file configures center clinical policy and presentation metadata.
It is validated during API and worker startup. The full schema, supported
workflow options, validation rules, and change procedure are documented in
[Clinical Vocabulary Configuration](../administration/clinical-vocabulary.md).

Use it to change fusion-description categories or optional DNA caller display metadata. Families,
gene-list types, file keys and analysis bindings are application-owned. Choose
supported authentication providers through `AUTHENTICATION_PROVIDERS`, and select
assay capabilities through ASP/ASPC administration.

## Application-owned definitions

Python loads `api/config/clinical_capabilities.toml` and
`api/config/clinical_query_defaults.toml` from the application package. Neither
path can be redirected through the center directory. These are software release
assets, like `api/config/collections.toml`; centers must not edit or copy them.
New ASPs, groups, subpanels and gene lists remain center-managed database resources.

Before upgrading a deployment that has older center files:

1. Back up the current private configuration release.
2. Compare its technical definitions with the target application's capability file.
   Stop if custom identifiers or mappings are used by existing records or pipelines;
   resolve their compatibility and migration before deployment.
3. Remove `assay`, `environment`, `authentication`, `genelist`, `files` and `analysis`
   sections from the center `clinical_vocabulary.toml`. Remove `fusion.callers`,
   retaining `fusion.description_terms`. Remove the entire `reporting` section:
   transcript priority is application-owned. Preserve any annotation descriptors in
   the deployment record and configure them in approved reporting-rule successors
   under `terminology.automatic_annotation_tumor_type` before using automatic Tier III text.
4. Archive any older center `clinical_query_policy.toml` outside the active bundle.
   It is no longer loaded. Compare its criteria with the installed database rules;
   preserve required center differences through reviewed query-rule publications
   before reopening clinical access. Application defaults and seed criteria cannot
   be overridden with center files.
5. Validate the new center release with the target application's configuration
   preparation command, then follow the [upgrade procedure](application-upgrades.md).

Old protected entries fail validation even when their values match the release.
They are not silently ignored. This configuration change does not rewrite stored
samples, ASPs, ASPCs or reports, and does not publish new database-managed query rules.

> **Important: Assay groups are registered in the database**
>
>
> Assay groups are not TOML configuration. They define persisted access,
> annotation, query, ASP, ASPC, and ISGL scope. Manage system and custom groups
> through [Admin > Assay groups](../administration/assay-groups.md).
> Assay family (`panel-dna`, `wgs`, `panel-rna`,
> `wts`) and subpanel (for example `endometrie` or `breast`) are separate
> concepts.
>

## Query-rule installation definitions

`api/config/clinical_query_seed.toml` is application-owned and loaded by Python
bootstrap tools. Do not copy it into a center configuration release. Manage live
criteria through [query rules](../administration/query-rules.md); the
[seed and predicate reference](../configuration/clinical-query-policy-file.md)
describes supported fields and installation behavior.

## `collections.toml`

See the [collections.toml reference](../configuration/collection-mapping-file.md) for fields,
requirements, omission behavior, examples and validation.

## Public Assay Catalog

The public assay catalog is a validated `public_assay_catalog` document in the
primary database, not a `center/` file. Clinical assay records, ASPCs, and ISGLs
remain the authoritative source for active analysis configuration and gene
content.

### Catalog Key Reference

The catalog is a presentation layer. ASPs define assays, ASPCs define active
analysis configuration, and ISGLs define curated genes. Editing the catalog in
**Admin > Public Assay Catalog** changes public content only; it does not change
clinical filtering, ingest requirements, or report behavior. The workspace is
a structured builder: it selects ASP identifiers from `assay_specific_panels`,
ASPC identifiers from `asp_configs`, and gene-list identifiers from
`insilico_genelists`; it then stores public display hierarchy and wording in
the catalog document. JSON is a portable import/export format, not the normal
editing surface. A modality JSON export uses the
`coyote3.public_assay_catalog_modality` envelope and changes only that modality
in a new draft when imported. Drafts require independent approval and publication.
See the [catalog workflow](../administration/public-assay-catalog.md) for roles,
previews, notifications, revision history, and publication safeguards.

| JSON path | Required | Allowed value | Use and fallback behavior |
| --- | --- | --- | --- |
| `version` | System-managed | Positive integer | Public release version, incremented only on publication. |
| `maintainer` | Recommended | Text | Center team responsible for catalog content. |
| `header` | Recommended | Text | Catalog landing-page heading. |
| `description` | Recommended | Text, including multiline text | Catalog landing-page introduction. |
| `layout.order` | Recommended | Ordered list of modality keys | Display order. Modalities omitted from the list are appended after configured values. |
| `modalities.<modality>` | Yes for each modality | Mapping | A public modality, for example `dna` or `rna`. Its key is a stable presentation identifier. |
| `modalities.<modality>.label` | Yes | Text | Visible modality label. |
| `modalities.<modality>.title` | No | Text | Expanded title; falls back to `label`. |
| `modalities.<modality>.description` | No | Text | Modality explanatory text. |
| `modalities.<modality>.categories.<category>` | Yes for every catalog section | Mapping | One public assay/category section. |
| `category.catalog_id` | System-managed | Stable text identifier | Generated presentation identity, separate from the editable display name. |
| `category.label` | Yes | Text | Visible category heading. |
| `category.title` | No | Text | Expanded heading; falls back to `label`. |
| `category.description` | Recommended | Text | Public assay description; falls back to the ASP description where available. |
| `category.subheading` | No | Text | Supplemental heading. |
| `category.asp_id` | Recommended | Existing ASP `asp_id` | Links the catalog section to the physical assay definition. |
| `category.subpanel_id` | No | Existing ASPC subpanel identifier | Narrows the category to a subpanel. Use the configured base subpanel when no specific subpanel applies. |
| `category.aspc_id` | Required before submission unless `aspc_ids.production` is set | Active production ASPC identifier | Direct configuration reference for the selected assay. |
| `category.aspc_ids` | No | Production reference mapping | Only the `production` key is accepted for publication. |
| `category.family` / `category.asp_family` | No | Supported ASP family identifier | Optional public family override; normally inherited from the ASP. |
| `category.assay_group` | No | Existing center assay-group value | Optional public group override; normally inherited from the ASP. |
| `category.input_material` | No | List of display strings | Public sample/input badges. |
| `category.tat` | No | Positive integer or ascending range and day/week/month/year unit | Turnaround-time statement, for example `7-14 days`; blank means unspecified. |
| `category.sample_modes` | No | List of display strings | Sample-mode badges, for example `Tumor-only` or `Tumor-normal`. |
| `category.analysis` | No | List of display strings | Public analysis summary. If omitted, available analysis is derived from the ASPC. |
| `category.report_sections` | No | List of display strings | Public report-content summary. |
| `category.clinical_indications` | No | List of text values | Public clinical indication list. |
| `category.limitations`, `category.public_notes` | No | Text | Public limitations and supplementary notes. |
| `category.gene_lists` | No | Ordered list of mappings | Gene-list sections within the category. |
| `gene_lists[].key` or `gene_lists[].isgl_id` | Required for an ISGL-backed list | Existing ISGL `isgl_id` | Resolves active ISGL metadata and gene coverage. Remove blank placeholder entries in new catalog content. |
| `gene_lists[].label`, `description` | No | Text | List-specific visible text; label falls back to the ISGL display name. |
| `gene_lists[].diagnosis` | No | List of display strings | List-specific clinical context. |
| `gene_lists[].subpanel_id`, `list_type` | No | Existing subpanel ID or ISGL list type | List-specific context overrides. |
| `gene_lists[].tat`, `input_material`, `sample_modes`, `analysis` | No | Same forms as the category keys | List-level values override the corresponding category value. |

> **Info: Use ASP, ASPC, and ISGL for clinical truth**
>
>
> Catalog content is appropriate for descriptions, turnaround-time wording,
> public input labels, and display order. Use ASP, ASPC, and ISGL records for
> active assay behavior, required files, analytical settings, and genes.
> ASPC contributes only `catalog.is_public` to the public catalog. All other
> public catalog wording and presentation values belong in the database catalog.
>

## `filter_flag_metadata.yaml`

See the [filter_flag_metadata.yaml reference](../configuration/filter-flag-metadata-file.md) for fields,
requirements, omission behavior, examples and validation.

## Software-Owned Values

The following values are intentionally not configurable by a center. They are
application behavior and changing them requires a software change.

| Item | Defined in | Why it is software-owned |
| --- | --- | --- |
| Permission identifiers and permission categories | `api/config/constants.py` and authorization contracts | Centers assign existing permissions to roles; they do not define new authorization semantics. |
| Authentication implementation | `api/config/security.py` and authentication services | `AUTHENTICATION_PROVIDERS` selects supported providers; center vocabulary cannot add a protocol. |
| Supported analysis types | Typed contracts, parsers, repositories, UI, and reporting services | A new type requires end-to-end ingestion, storage, display, report, and test support. |
| Reporting-rule operators and rendering behavior | Reporting contracts and rule engine | Clinical content follows its own controlled reporting-rule release process. |
| Normalized database-version keys | `api/config/database_versions.py` | Keys such as `database_versions.vep` are stable software contracts; source parsing is not a center vocabulary setting. |
| Product, licence, repository, and issue URLs | `api/config/application_metadata.py` | These identify Coyote3 itself rather than the deploying center. |

## Safe Change Protocol

1. Identify whether the change is center vocabulary, presentation content, or
   a software capability. Only the first two belong in the external center directory.
2. Edit the smallest relevant file and retain stable identifiers already used
   by historical samples, ASPCs, ISGLs, or report releases.
3. Review the diff with clinical and technical owners.
4. Run configuration and contract validation in a non-production environment.
5. Select the reviewed external directory and recreate API, worker, beat, and monitor together.
   Rebuild and recreate documentation when center identity changes. Rebuild the
   frontend when changing its environment-derived build arguments, including
   organization name, URL prefix, or integration links.
6. Verify one representative public page and one representative ingest or
   report workflow affected by the change.

Center-file changes do not require rebuilding the API image. For the base
production definition, rebuild documentation and recreate the affected services:

```bash
scripts/deployment/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml build docs

scripts/deployment/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml up -d --force-recreate api worker beat monitor docs
```

Use the same project name and any reviewed overrides as the original deployment.
Schedule clinical-policy changes with the center so active review and ingest work
do not span different configuration revisions. Retain the previous images and
configuration revision for rollback; a collection-name or clinical-data migration
requires its own rollback procedure.

> **Tip: When not to edit a configuration file**
>
>
> Do not use center configuration to introduce a new analysis type, parser,
> authentication protocol, permission semantic, or report rule evaluator.
> Those are software capabilities and require a typed implementation,
> contracts, tests, and documentation update.
