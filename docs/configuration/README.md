# Configuration and file formats

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Choose the reference for the item being edited. Installation and application
procedures link here for definitions and accepted values; these pages do not
replace the ordered procedures.

[File-format conventions](../reference/file-format-conventions.md) explains syntax,
required fields, defaults, nulls and examples across all supported boundaries.
[Operational files](../reference/operational-files.md) covers installed catalogs,
reference imports, migration inputs, backups and generated artifacts.

## Deployment and center files

For clinical selection, start with the [application base queries](../administration/query-rules.md#application-base-queries-by-analysis)
and [UI-managed query policies](../administration/query-rules.md#scope-and-inheritance).
The seed-file reference below is for installation criteria; editing it is not the
workflow for changing a running installation's rules.

| File or resource | Who edits it | Contents and detailed reference |
| --- | --- | --- |
| Private environment file, for example `production.env` | Deployment operator | [File syntax, precedence and validation](environment-file.md); [all supported environment keys and defaults](../deployment/configuration-reference.md#environment-variable-reference). |
| Compose definition or private storage override | Infrastructure operator | [Compose files](compose-files.md): services, mounts, networks, overlays and rebuild behavior. |
| External `contact.toml` | Center administrator | [Center identity and contact fields](contact-file.md). Public information only. |
| External `clinical_vocabulary.toml` | Clinical configuration owner | [Vocabulary fields and supported choices](../administration/clinical-vocabulary.md). |
| Application `clinical_query_seed.toml` | Software maintainers | [Installed query criteria and predicate grammar](clinical-query-policy-file.md). Live changes use the database query-rule editor. |
| External `filter_flag_metadata.yaml` | Clinical configuration owner | [Flag labels, severity, descriptions and optional caller overrides](filter-flag-metadata-file.md). |
| Application `collections.toml` | Software maintainers | [Logical collection mappings](collection-mapping-file.md). Centers do not edit it. |
| Core `core/src/coyote/config/factory_defaults.toml` | Software maintainers | [Factory defaults](#factory-defaults): domain capabilities, shared policy values, filters and clinical starter values. |
| API `api/src/coyote_api/config/factory_defaults.toml` | API maintainers | Deployment fallbacks and environment profiles. Not a center file. |
| Frontend `frontend/src/lib/defaults.ts` | Frontend maintainers | Presentation defaults: theme, layouts, page-size choices and nomenclature labels. |
| Bootstrap catalogs | Software release | [Baseline accounts, permissions and reference data](../deployment/bootstrap-data-flow.md). Do not edit release catalogs as a substitute for center administration. |

The [center configuration guide](../deployment/center-configuration.md) describes
where required and optional center files live, how local/Git releases are prepared,
and which processes load them. The environment filename is independent of this
center directory. Never place passwords in public contact or clinical-policy files.

Empty-section messages for modern reports are configured separately in the optional
[report presentation file](report-presentation-file.md). They do not require a new ASPC revision.

## Factory defaults

Defaults follow the component that owns their behavior:

| Owner and source | Contents |
| --- | --- |
| Core package: `core/src/coyote/config/factory_defaults.toml` | Reusable domain capabilities and defaults needed by models and clinical workflows. |
| API host: `api/src/coyote_api/config/factory_defaults.toml` | Sessions, cache, databases, mail, workers, HTTP clients, deployment profiles and public product metadata. |
| Frontend: `frontend/src/lib/defaults.ts` | Theme, layouts, table-size choices, default UI environment selection and nomenclature labels. |

The core package never imports the API or frontend. The API imports shared domain
values when it needs them: retention periods, for example, come from the core
application-controls policy rather than another runtime definition. Environment
variables keep their existing precedence over API factory fallbacks.

A shared setting has one definition and several consumers. SNV filter defaults are
used by somatic, germline and flat document contracts; reportable tiers are defined
once for all finding types. Repeated report messages share one entry. Assay families
inherit their modality's analyses, with explicit overrides for narrower families.
API profiles reuse the knowledgebase database name and production/non-production
mode settings. No custom reference syntax is needed in the TOML files.

Equal values are kept separate when they represent different policies. In particular,
clinical editor starter thresholds that differ from omitted-field defaults retain
those differences in `starter_defaults`. The browser's initial page size and the
backend's maximum query size belong to different owners and serve different purposes.

The API validates and persists explicit UI preferences; absent preferences remain
unset. The frontend applies its defaults on display and after preference saves.
Existing stored preferences remain effective, including explicit false values.
Backend validation retains a positive page-size bound without owning the browser's
selector choices. The OpenAPI generator generates API types only; it does not supply
frontend defaults or require a UI-default extension on the API schema.

For example, the supplied DNA analyses are in `capabilities.analysis.dna`, while
new DNA configurations use `starter_defaults.dna.analyses`. Adding a supported
analysis still requires its parser, schema and workflow support.

Catalogs load once per Python process and are packaged with their owner. Rebuild and
restart the affected backend after editing its defaults. Frontend defaults require a
frontend rebuild. Run `npm run api:generate` from `frontend/` when API contracts change.

Existing database records, approved clinical rules, center configuration and explicit
deployment overrides are not rewritten. Required deployment inputs remain required.
Empty collections, protocol discriminators, schema versions and lifecycle counters
remain part of their contracts. Collection names and module definitions retain their
dedicated typed registries.

## Clinical resources managed in the application

These are database resources edited through authorized application workflows;
they are not extra TOML files to create on the host.

| Item | Detailed reference | Procedure |
| --- | --- | --- |
| Assay / ASP and configuration / ASPC | [Resource definitions and missing prerequisites](../administration/clinical-configuration-resources.md), [analysis availability](../administration/assay-analysis-availability.md) | [Add an assay](../administration/assay-setup.md) |
| Assay group and named diagnoses | [Groups](../administration/assay-groups.md), [definitions and associations](../administration/assay-diagnoses.md) | [Setup order](../administration/assay-setup.md#when-order-matters) |
| Gene lists / ISGL | [List types and clinical scope](../user-guide/gene-lists-and-assay-context.md) | [Configure selected lists](../administration/assay-setup.md#4-prepare-the-gene-lists-that-filters-will-select) |
| Reporting rule set | [Rule syntax, validation and publication](../reference/clinical-reporting-rules.md) | [Optional assay rule preparation](../administration/assay-setup.md#5-optionally-publish-reporting-rules) |
| Finding query policy | [Base queries and inheritance](../administration/query-rules.md) | [Create and activate a policy](../administration/query-rules.md#create-and-activate-a-policy) |
| Reusable profiles and environment promotion | [Scope, precedence and reviewed publication](../administration/configuration-publication.md) | Assay configurations → Profiles and promotions |
| Users, roles and permissions | [Access model](../administration/permissions-and-access.md), [permission identifiers](../administration/permission-catalog.md) | [Administration](../administration/administration-guide.md) |
| Public assay catalog | [Fields, ownership and approval](../administration/public-assay-catalog.md) | Separate publication after clinical activation |

For exact persisted field types, required fields and schema defaults, consult the
[generated collection contracts](../reference/mongodb-collections.md). These describe
storage validation; they do not replace workflow permissions, reference validation
or clinical approval. Use normal administration/API workflows rather than direct
MongoDB edits.

The [clinical resource field reference](../administration/clinical-resource-fields.md)
provides ASP, ASPC and ISGL defaults and links to the complete persisted schemas.
[Application controls](../administration/application-controls.md) lists runtime
switches, retention limits and initialization behavior.

## Files submitted by pipelines and users

| Input | Reference | What the reference distinguishes |
| --- | --- | --- |
| Sample manifest | [Manifest contract](../reference/sample-manifest.md) | Sample identity, scope, paths and declared evidence. |
| Raw analysis inputs | [Raw ingest file formats](../reference/ingest-files/README.md) | One reference per file type, required fields and representative synthetic examples. |
| JSON collection imports | [Collection imports](../api/collection-imports.md) | Accepted collections, permissions, validation and errors. |
| API requests | [API routes and workflows](../api/routes-and-workflows.md) | Authentication, request/response contracts and operation-specific requirements. |

A configuration example is not clinical approval, and a valid file is not necessarily
a complete workflow. Follow the corresponding procedure to validate references,
permissions, evidence availability and publication state.

## Review, reporting and operational data

| Resource or output | Detailed reference | Authoring boundary |
| --- | --- | --- |
| Sample review filters | [Filter fields, bounds and defaults](../reference/filter-profile-fields.md) | ASPC initial defaults and explicit sample filter edits. |
| Finding annotations, classifications and comments | [Review actions](../user-guide/actions-and-record-changes.md), [annotation contract](../reference/mongodb-collections.md#annotation) | Authorized review workflows; finding identity and assay scope must match. |
| Report configuration, saved artifacts and finding snapshots | [Reporting reference](../reference/report-snapshots.md) | Report preview/save; generated evidence is not a raw input template. |
| User preferences and access records | [Identity fields and defaults](../administration/permissions-and-access.md#account-role-and-permission-fields) | Personal settings or authorized account/role administration. |
| Knowledgebase releases and updater policy files | [Snapshot inputs](../operations/knowledgebase-updates.md), [VEP importer policy](../operations/vep-metadata-updates.md#importer-policy-files) | Deliberate reference-data update, not sample ingestion. |
| Installed catalogs, backups, migration files and exports | [Operational file reference](../reference/operational-files.md) | Use the matching installer, importer, backup or export workflow. |
