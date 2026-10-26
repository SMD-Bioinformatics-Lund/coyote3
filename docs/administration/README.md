# Application administration

For creator/updater fields and read-only bundled records, see
[record attribution](record-attribution.md).

Application administration covers user accounts, roles, assay definitions, gene lists,
and clinical configuration. Administrative actions are governed by permissions and
recorded through the application's audit workflows. Service maintenance and incident
response are covered in [Operations](../operations/README.md).

## First time configuring an assay?

Start with [prerequisites and setup steps](assay-setup.md#step-by-step-add-a-new-assay).
That is the ordered procedure from preparing an active group to validating an
activated assay. The sidebar groups its supporting pages under **Set up an assay**.
You do not need to read every reference before starting.

| At this stage | Read this |
| --- | --- |
| Understand the names | [Resources and dependencies](clinical-configuration-resources.md): an assay (ASP) defines the offering; an assay configuration (ASPC) configures a diagnosis and environment; an in-silico gene list (ISGL) selects genes. |
| Prepare prerequisites | [Setup step 1](assay-setup.md#1-confirm-authors-reviewers-and-the-active-group), then [assay groups](assay-groups.md). |
| Choose diagnoses or subpanel scopes | [Setup step 3](assay-setup.md#3-select-scopes-and-environments). Named diagnoses are optional; Base needs no diagnosis registration. |
| Understand which findings will be retrieved | [Application base queries](query-rules.md#application-base-queries-by-analysis), then [installed group policies](installed-defaults.md#published-set-identifiers). |
| Change finding selection in the UI | [Query-rule scope and inheritance](query-rules.md#scope-and-inheritance), then [create and activate a policy](query-rules.md#create-and-activate-a-policy). |
| Prepare reporting | [Optional setup step 5](assay-setup.md#5-optionally-publish-reporting-rules) and the [reporting-rule reference](../reference/clinical-reporting-rules.md). Query rules select findings; reporting rules generate clinical report content. |
| Complete configurations and activate | Continue from [setup step 6](assay-setup.md#6-complete-one-aspc-for-each-selected-combination), including independent review and validation. |
| Resolve a blocked step | [Missing prerequisites and their effects](clinical-configuration-resources.md#missing-prerequisites-and-their-effects). |

## Other administration tasks

- **Edit a document another user may be working on:** read [editing sessions](document-editing.md).

- **Manage users or access:** start with [permissions and access control](permissions-and-access.md).
- **Change an existing clinical configuration:** start with [planning configuration changes](planning-configuration-changes.md).
- **Change an application setting:** use [application controls](application-controls.md).
- **Install, upgrade or recover services:** use [deployment](../deployment/README.md)
  or [operations](../operations/README.md); these are separate from registering an assay.

## All administration guides

| Guide | Use it to |
| --- | --- |
| [Supported application capabilities](supported-capabilities.md) | Distinguish center-defined groups and assays from implemented analyses, and check supported workflows. |
| [Installed defaults and demonstration configuration](installed-defaults.md) | Review bundled groups, exact query conditions, optional demo resources and default roles. |
| [Application administration](administration-guide.md) | Manage users, roles, assays, gene lists, and application controls. |
| [Permissions and access control](permissions-and-access.md) | Understand permission identifiers, roles, scopes, and enforcement. |
| [System permission catalog](permission-catalog.md) | Look up installed permission IDs in the generated catalog. |
| [System role catalog](system-role-catalog.md) | Review every installed role, its purpose and exact permission assignments. |
| [Clinical configuration resources](clinical-configuration-resources.md) | Understand ASPs, ASPCs, diagnoses, ISGLs, rules and the effect of missing prerequisites. |
| [Planning configuration changes](planning-configuration-changes.md) | Identify affected resources, validate changes, and preserve historical review evidence. |
| [Assay Groups](assay-groups.md) | Register and manage assay-group scope and availability. |
| [Assay Diagnoses](assay-diagnoses.md) | Manage shared diagnosis definitions and assay associations. |
| [Bulk installation](bulk-installation.md) | Upload JSON/YAML lists of diagnoses, groups, assays, gene lists or assay configurations. |
| [Assay Setup](assay-setup.md) | Prepare and review an assay's configuration resources. |
| [Finding query rules](query-rules.md) | Manage inherited finding-selection policies for groups, assays and diagnoses. |
| [Clinical reporting rules](../reference/clinical-reporting-rules.md) | Author, test, review and publish the rules that produce clinical report content. |
| [Report presentation settings](../configuration/report-presentation-file.md) | Configure supported empty-section wording without changing clinical rules. |
| [Assay analysis and reporting availability](assay-analysis-availability.md) | Understand how assay files and configuration enable analyses and reporting. |
| [Clinical resource fields](clinical-resource-fields.md) | Look up ASP, ASPC and ISGL field requirements and defaults. |
| [Center Vocabulary Configuration](clinical-vocabulary.md) | Configure center-owned terms and annotation choices. |
| [Public Assay Catalog](public-assay-catalog.md) | Author, review, and publish the public assay catalog. |
| [Application controls](application-controls.md) | Configure runtime switches and retention using exact keys and limits. |

[Documentation home](../README.md)
