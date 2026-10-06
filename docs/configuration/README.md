# Configuration and file formats

Choose the reference for the item being edited. Installation and application
procedures link here for definitions and accepted values; these pages do not
replace the ordered procedures.

[File-format conventions](../reference/file-format-conventions.md) explains syntax,
required fields, defaults, nulls and examples across all supported boundaries.
[Operational files](../reference/operational-files.md) covers installed catalogs,
reference imports, migration inputs, backups and generated artifacts.

## Deployment and center files

| File or resource | Who edits it | Contents and detailed reference |
| --- | --- | --- |
| Private environment file, for example `production.env` | Deployment operator | [File syntax, precedence and validation](environment-file.md); [all supported environment keys and defaults](../deployment/configuration-reference.md#environment-variable-reference). |
| Compose definition or private storage override | Infrastructure operator | [Compose files](compose-files.md): services, mounts, networks, overlays and rebuild behavior. |
| External `contact.toml` | Center administrator | [Center identity and contact fields](contact-file.md). Public information only. |
| External `clinical_vocabulary.toml` | Clinical configuration owner | [Vocabulary fields and supported choices](../administration/clinical-vocabulary.md). |
| External `clinical_query_policy.toml` | Clinical configuration owner | [Query-policy keys, scopes, defaults and examples](clinical-query-policy-file.md). |
| External `filter_flag_metadata.yaml` | Clinical configuration owner | [Flag labels, severity, descriptions and optional caller overrides](filter-flag-metadata-file.md). |
| Application `collections.toml` | Software maintainers | [Logical collection mappings](collection-mapping-file.md). Centers do not edit it. |
| Bootstrap catalogs | Software release | [Baseline accounts, permissions and reference data](../deployment/bootstrap-data-flow.md). Do not edit release catalogs as a substitute for center administration. |

The [center configuration guide](../deployment/center-configuration.md) describes
where the four editable center files live, how local/Git releases are prepared,
and which processes load them. The environment filename is independent of this
center directory. Never place passwords in public contact or clinical-policy files.

## Clinical resources managed in the application

These are database resources edited through authorized application workflows;
they are not extra TOML files to create on the host.

| Item | Detailed reference | Procedure |
| --- | --- | --- |
| Assay / ASP and configuration / ASPC | [Resource definitions and missing prerequisites](../administration/clinical-configuration-resources.md), [analysis availability](../administration/assay-analysis-availability.md) | [Add an assay](../administration/assay-setup.md) |
| Assay group and named subpanels | [Groups](../administration/assay-groups.md), [definitions and associations](../administration/assay-subpanels.md) | [Setup order](../administration/assay-setup.md#when-order-matters) |
| Gene lists / ISGL | [List types and clinical scope](../user-guide/gene-lists-and-assay-context.md) | [Configure selected lists](../administration/assay-setup.md#4-prepare-the-gene-lists-that-filters-will-select) |
| Reporting rule set | [Rule syntax, validation and publication](../reference/clinical-reporting-rules.md) | [Assay rule preparation](../administration/assay-setup.md#5-publish-compatible-reporting-rules) |
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
