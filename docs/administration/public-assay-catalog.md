# Public Assay Catalog

The public catalog presents reviewed genomic services. Assays, biological groups,
diagnoses, production configurations and public gene lists remain authoritative
resources. Editing catalog wording does not change sample analysis or reporting rules.

## Find a service

**By Diagnosis** is the default view: select a biological group, a diagnosis,
then a technical family. **By Assay** provides modality, family and assay filters
before diagnosis selection. Both views use the same published offerings.

For example, Solid → Breast can contain a targeted DNA panel and a WGS service.
Each offering has its own price, capabilities and effective gene scope.
**No diagnosis / General testing** represents an explicitly configured Base context.
It appears only when a Base offering has been published. An unselected diagnosis
filter includes all published contexts and does not select Base.

Search accepts group names, diagnoses, tests, assay identifiers, modalities,
technical families and published gene symbols. Results identify which field matched.
Gene searches include only the effective scope in the publication. WGS sequencing
breadth does not imply that every gene is assessed or reportable.

Select **View details** to open an offering's service information and searchable,
downloadable gene table. Details include methodology, material requirements,
turnaround, report deliverables, limitations and ordering instructions when configured.
The offering identifier is retained in the page URL.

Select **Compare** on two or three offerings to compare methods, enabled analyses,
gene counts, deliverables, prices and limitations. Price sorting is available only
when the selected group's published prices share a currency and pricing basis.
The default order follows the catalog's section order and entry order.
No published offerings produces **No published services**.

## Prepare resources

1. Create and activate the biological group and assay.
2. Define the assay's supported analyses and validated covered genes.
3. Associate the shared diagnosis with the assay, or configure an explicit Base context.
4. Create active public gene lists and select them in the production configuration's
   analysis filters.
5. Activate the production configuration for the assay and diagnosis.
6. Open **Administration → Assay catalog** and create a draft.

Publication requires the offering's group, assay, diagnosis and production
configuration to agree. A named diagnosis requires an active assay association.
Analyses must be supported by the assay and enabled in the configuration.
Catalog text cannot enable an unsupported analysis.

## Author an offering

Select **Create first draft**, or **Edit published catalog** for an existing release.
Choose a section or entry in the editor sidebar. Folders organize presentation;
they do not create biological groups, diagnoses, assays or configurations.
An offering's public placement comes from its registered resources.

Link each entry to its assay and production configuration. Set its display name,
description, materials, turnaround and analyses. Assign public gene lists per
analysis, or explicitly select **No gene list** when appropriate. Duplicate list
references, contradictory assignments and unavailable resources prevent submission.

SNV, CNV and fusion list bindings must also be selected in their corresponding
production filter configuration. Effective published genes are the intersection
of those lists with the assay's validated covered genes. This applies to targeted
panels and genome-wide families. The detail page reports how many list genes lie
outside that coverage; excluded genes are not advertised as assessed.
SNV and CNV scopes remain separately identified.

A general list without an analysis binding does not establish an effective
analysis scope. Analyses without an implemented list selector must use **No gene list**.

### Pricing and service information

Enable **Publish an offering-specific price** and supply an amount, three-letter
currency code, and fixed, starting or estimated basis. Add pricing conditions
where applicable. Amounts are nonnegative with up to two decimal places.

Prices belong to individual offerings and do not inherit from folders or diagnoses.
Without a price, **Pricing message** supplies the alternative wording; its default
is **Contact for pricing**.

Set report deliverables, methodology and ordering information on each offering.
These describe the public service; they do not configure report templates,
clinical rules or order submission.

### Presentation inheritance

Blank descriptions, material requirements, turnaround, analyses, resource references
and list bindings inherit from their immediate presentation parent. Nonempty values
replace inherited values. **Suppress inherited details** keeps selected fields empty.
Labels, entry identity, pricing and the additional offering service fields remain local.

Missing parents and cycles are rejected. Resolved references must pass the same
resource validation as explicit references. Inheritance affects presentation only.

Turnaround accepts a positive integer or ascending integer range and a unit of days,
weeks, months or years. Blank means unspecified. Descriptions support restricted HTML;
executable content, unsafe URLs and event handlers are removed. Display names and
structured fields remain plain text.

## Preview, review and publish

**Preview changes** resolves a draft without saving it. **Save draft** records a
revision and opens its preview. Preview uses the same diagnosis-first discovery,
offering details and matrix projection as the public service.

| State | Next operation | Public visibility |
| --- | --- | --- |
| Draft | Edit, save, preview, submit to a reviewer | None |
| Submitted | Assigned reviewer approves or rejects | None |
| Approved | Assigned publisher publishes | None |
| Rejected | Revise as a new draft | None |
| Published | Read, export and inspect history | Current release only |

Submission captures public service details and effective gene scopes alongside
private resource revision references. The assigned reviewer reviews this snapshot.
Publication rechecks resource eligibility and compares the current resolved content
and revisions with the reviewed snapshot. Changes require a revised draft and review;
they cannot silently enter the release.

The reviewer must not be a content editor or the submitter. The assigned publisher
must also be independent of every content editor. Reviewer and publisher may be the
same person if they hold both permissions. Eligibility is checked again at publication.
Rejection requires a reason. Submitted and approved documents cannot be edited.

Workflow notifications link assigned reviewers and publishers to the version.
The workspace records actors, review reasons and lifecycle events.

## Publication data and history

The public discovery endpoint, matrix, catalog gene lookup and CSV export read
approved offering snapshots. They do not rebuild service scope from current
configuration or list contents. Later source edits do not alter the publication.
To remove a service from discovery, publish a reviewed successor without that entry.

Public projections include service wording, resource display names, enabled analyses,
pricing and effective gene scopes. Internal configuration identifiers, revision maps,
query expressions and confidential reporting rules are excluded.

| Collection | Responsibility |
| --- | --- |
| `public_assay_catalog` | Current publication |
| `public_assay_catalog_versions` | Workflow documents and preserved releases |
| `public_assay_catalog_revisions` | Snapshot of each workflow revision |

The catalog stores `published_offerings` and a separate private
`resource_revisions` map. References include assay, configuration, group,
diagnosis association, shared diagnosis definition and gene-list revisions.

Only publication increments the public version. Each workflow save increments
its document revision. Stale revisions and drafts based on an older publication
return HTTP 409. Publication updates the version, current projection and history
in one MongoDB transaction. A replica set is required; see
[MongoDB deployment](../deployment/mongodb-setup-and-recovery.md).

Historical review previews retain their captured service content and prices.
Draft previews resolve current resources. Imported or saved content cannot supply
its own publication snapshot: derived fields are cleared and rebuilt for review.
Back up all three collections together, with identity audit records and application
notifications according to the deployment retention policy.

## JSON exchange

**Export catalog** downloads the displayed document. **Export section** downloads a
section envelope. **Import draft** validates JSON and creates a draft; it cannot
publish directly or grant approval authority. References must resolve at the
destination before submission. Exported presentation documents contain no sample data.

The **Matrix** action compares the selected preview's effective scopes by modality,
group, assay, diagnosis, analysis and list. No list means no inferred coverage column.
Public matrix search and pagination operate on the current publication.

Matrix columns identify the associated assay, with the diagnosis and gene list
shown underneath. Selecting one shared list can therefore show several assay
columns with different coverage; these are separate published offerings, not
duplicate list columns. Assay labels prefer `name` (short name), then `display_name`,
then `asp_id`. These labels are captured in the reviewed publication; changing an
assay name requires a new catalog publication before public labels change.

Public service cards use the application's DNA/RNA accents and explicit modality
badges. Each card emphasizes the test name, method, turnaround, published gene
count and pricing information. Modality is written as text as well as indicated
by color.

See the [collection contract](../reference/mongodb-collections.md#public_assay_catalog)
for stored fields and defaults.

## Permissions and API

| Role | Permissions |
| --- | --- |
| `catalog_viewer` | `catalog:view` |
| `catalog_author` | `catalog:view`, `catalog:draft`, `catalog:submit` |
| `catalog_reviewer` | `catalog:view`, `catalog:review` |
| `catalog_publisher` | `catalog:view`, `catalog:publish` |

An identity administrator assigns roles. Installing role definitions does not assign
them to users.

Public discovery uses `GET /api/v1/public/assay-catalog/offerings`.
Administrative paths below use `/api/v1/admin/assay-catalog`.

| Method and path | Permission | Operation |
| --- | --- | --- |
| `GET /` | `catalog:view` | Workspace, source choices and assigned users |
| `GET /versions/{oid}` | `catalog:view` | Workflow document |
| `GET /versions/{oid}/revisions` | `catalog:view` | Preserved revisions |
| `POST /preview/offerings` | `catalog:view` | Read-only offering preview |
| `POST /preview` | `catalog:view` | Read-only navigation and gene projection |
| `POST /preview/matrix` | `catalog:view` | Read-only effective gene matrix |
| `POST /drafts` | `catalog:draft` | Create a draft |
| `POST /imports` | `catalog:draft` | Create a draft from JSON |
| `PATCH /drafts/{oid}` | `catalog:draft` | Save with an expected revision |
| `POST /drafts/{oid}/submit` | `catalog:submit` | Capture scope and assign review |
| `POST /drafts/{oid}/review` | `catalog:review` | Approve or reject |
| `POST /drafts/{oid}/publish` | `catalog:publish` | Publish the reviewed release |
