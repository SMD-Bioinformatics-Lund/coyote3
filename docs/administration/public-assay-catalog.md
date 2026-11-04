# Public Assay Catalog

The public catalog presents reviewed genomic services. Assays, biological groups,
diagnoses, production configurations and public gene lists remain authoritative
resources. Editing catalog wording does not change sample analysis or reporting rules.

## Find a service

The catalog uses a navigation tree on the left and the selected level's information
on the right. Click a section, family, group or diagnosis name to read its own
description and service information directly. For example, **Panels → Hematology**
shows the parent hematology information; selecting **MPN** shows the MPN entry.
The tree highlights parent levels with distinct heading sizes and colors.
It retains the modality → sequencing method → biological group → diagnosis
levels: for example, **DNA → Panels → Hematology → MPN**. These levels come from
the reviewed offerings, including publications whose editable entries are flat.
Assay names are shown with their service information on the right.

Use the separate arrows to expand or collapse branches without changing the
selection. Opened branches remain expanded when another level is selected.
Draft wording edits preserve collapsed branches. Selecting a different entry opens
its ancestor branches so the selection is visible.
The breadcrumb above the information provides links back to its parents.
**Catalog introduction** returns to the overview. The selection is stored in the
page URL; existing offering links continue to open their service information.

Service information appears first: description, specimen requirements, sample
modes, analyses, turnaround, methodology, limitations, reporting and ordering
instructions, price, published covered-gene counts, and captured platform/read
information. These facts share the main information panel. Right-hand panels retain
the DNA/RNA and sequencing method colors as subtle surface tints and borders with
shared elevation. Analysis,
tissue, pricing, turnaround and coverage badges have distinct colors and retain
their text labels in every theme. Unspecified metadata
is labelled **Not specified**. Method and group overviews show the published
services' values and unique gene counts, with different prices and TATs identified
by assay and diagnosis. The introduction and DNA/RNA pages provide brief explanatory
overviews and available methods, without aggregating individual service details.
They do not repeat the sidebar's links.
The searchable, downloadable gene table appears below that information.
Analysis tabs keep SNV, CNV and fusion scopes separate. Gene rows are limited to
the frozen publication's effective scope; WGS sequencing breadth does not imply
that every gene is assessed or reportable. Current HGNC annotations enrich those
published symbols without expanding coverage.

The gene coverage matrix remains available through **Gene coverage matrix**.
**Compare assays** opens a separate comparison page. Select up to three published
assay/diagnosis services to compare aligned rows for prices, TAT, analyses, samples,
gene counts, platform, reporting and limitations. Search narrows the choices without
clearing selected services. Comparison URLs retain the selected offering IDs.
The catalog itself uses direct information rather than offering cards or gene matching.
No published offerings or hierarchy produces **No published services**.

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
The linked resources determine the public modality, method, group and diagnosis
levels. Named presentation folders can provide wording for the corresponding
level when their descendant offerings belong to that branch.
Entries whose configuration belongs to another assay remain editable in their
source section; they do not define a clinical navigation branch.

Link each entry to its assay and production configuration. Set its display name,
description, materials, turnaround and analyses. Assign public gene lists per
analysis, or explicitly select **No gene list** when appropriate. Duplicate list
references, contradictory assignments and unavailable resources prevent submission.

SNV, CNV and fusion list bindings must also be selected in their corresponding
production filter configuration. Effective published genes are the intersection
of those lists with the assay's validated covered genes. This applies to targeted
panels and genome-wide families. The gene scope reports how many list genes lie
outside that coverage; excluded genes are not advertised as assessed.
SNV and CNV scopes remain separately identified.

A general list without an analysis binding does not establish an effective
analysis scope. Analyses without an implemented list selector must use **No gene list**.

### Pricing and service information

Enable **Set a price at this level** and supply an amount, three-letter
currency code, and fixed, starting or estimated basis. Add pricing conditions
where applicable. Amounts are nonnegative with up to two decimal places.

Configure general prices and service wording on a section or parent folder.
Missing child values inherit from the immediate parent; a diagnosis-specific price
replaces that default. **Pricing message** provides alternative wording where no
numeric price is configured. If neither is available, the public view displays
**Contact for pricing**. The comparison does not convert between currencies.

Set report deliverables, methodology and ordering information on each offering.
These describe the public service; they do not configure report templates,
clinical rules or order submission.

### Presentation inheritance

Blank descriptions, material requirements, turnaround, analyses, resource references
and list bindings inherit from their immediate presentation parent. Nonempty values
replace inherited values. **Suppress inherited details** keeps selected fields empty.
Prices, pricing messages, methodology, ordering information and report deliverables
also inherit. Labels and entry identity remain local. A diagnosis's available
analyses and genes remain bounded by its reviewed operational configuration.

Published gene counts use the union of effective reviewed gene lists. They do not
expand coverage from current assay resources. New review snapshots also capture
sample modes, platform, read length/mode and the assay's covered-gene count.
Older publications retain their stored metadata; publish a newly reviewed version
to capture these additional assay facts. Missing values are not fetched live.
Previously submitted or approved versions must be revised and reviewed again if
their captured facts differ from the current snapshot; publication retains the
existing source-change check.

Missing parents and cycles are rejected. Resolved references must pass the same
resource validation as explicit references. Inheritance affects presentation only.
Creating shared defaults preserves existing service values, including fields
suppressed by an earlier parent. Those empty fields remain suppressed after the
entry moves beneath the new defaults.

Turnaround accepts a positive integer or ascending integer range and a unit of days,
weeks, months or years. Blank inherits from the parent unless `tat` is suppressed;
without an inherited value it is unspecified. Descriptions support restricted HTML;
executable content, unsafe URLs and event handlers are removed. Display names and
structured fields remain plain text.

## Preview, review and publish

**Preview changes** resolves a draft without saving it. **Save draft** records a
revision and opens its preview. Preview uses the same hierarchy, information view
and matrix projection as the public service.

The **Review and publication** section above the editor shows the current step
and the next action. Save and preview the draft, select an independent reviewer,
then choose **Send for approval**. Submission is disabled while changes are unsaved
or the editor is open. Only the assigned independent reviewer sees review actions;
only the assigned independent publisher sees **Publish catalog** after approval.
Publication requires confirmation.

Select a draft to open it for editing. One tree contains the modality, method,
group and diagnosis levels, individual assay entries, custom sections and unfinished
items. Expand a level to use its **Add new entry** action directly beneath it.
Custom sections keep their children in place after an assay is attached.

For a new section, enter its **Section name** and select **DNA / RNA**. Add an
entry beneath it, then use **Entry setup** to set the **Entry name**, **Assay**,
**Diagnosis** and **Analyses**. Diagnosis choices select the corresponding active
production configuration. When names are duplicated, the configuration identifier
distinguishes the choices. Selecting an assay makes the item an assay entry; adding
a child beneath an unbound item makes that parent a section.

Use **Add gene list for SNV**, **CNV**, or another selected analysis to choose
eligible gene lists from a dropdown. Selected lists remain visible as removable
badges while searching. **No gene list** remains an explicit per-analysis choice.
Eligibility still follows the selected assay, group, diagnosis and list type.

The editor uses the public information panel. Select the pencil beside a title,
description, price, TAT, sample type or other public field to edit it in place.
The introduction and DNA/RNA sections use the brief overview layout. DNA/RNA
sections retain their editable technical defaults under **Inherited service defaults**.
Changes update the draft while typing; **Done** closes that field and **Cancel field
edit** restores its prior value. Escape also cancels the field. Neither action
saves or publishes a version. Use **Save draft** to record the document revision.
Incomplete prices and invalid turnaround ranges must be corrected before selecting
**Done**. Incomplete prices also disable **Save draft** until corrected or cancelled.
Background coverage preview pauses for empty sections, unfinished names, source
links and prices. Other source-validation failures appear inline with **Retry preview**,
without repeated notification popups. Editing the draft clears the previous preview's
error while the updated preview is pending. Preview never changes the draft or saved scope.
Analysis edits temporarily disable their dependent source and gene-list
controls so cancellation can restore the complete original binding set.

Inherited values identify their immediate parent. **Use parent value** removes the
local override. Coverage counts and captured assay metadata are computed from the
private draft preview and remain read-only here; update the linked sources or
gene-list selections to change them. Coverage refreshes after edits, and is marked
unavailable while source selections are incomplete.

For a level without its own presentation parent, **Add shared defaults** creates
editable draft folders within its source section. Existing entry identifiers,
source links and effective settings are retained. Overviews combining separate
source sections provide controls to edit each section's defaults separately.
Registered hierarchy names remain stable when a parent information heading changes.

**Add section** is above the navigation tree. Each expanded level has **Add new
entry** directly in the tree. Selected parents also have **Add subsection** and
**Add entry** or **Add child entry** actions. When a public
level combines several source sections, select the source section before adding
content. Missing presentation parents are created within that source section while
preserving existing services' effective settings.

Custom sections and incomplete entries remain in the main tree. **Entry setup**
keeps assay, diagnosis, analysis and gene-list selection together in one raised
panel. Parent changes, inheritance suppression, descriptions and reference details
remain available under the additional entry settings.

Select a draft in the version list to expose **Delete draft** beside **Review and
publication**. Deletion retains its confirmation, permission, editing-lease and
revision checks; save or discard unsaved changes first. Published and system-installed
versions cannot be deleted. **Import and export** in the sidebar contains file
controls. **History and version options** contains lifecycle history and historical
revision previews.

The public discovery response includes allowlisted presentation entries from the
reviewed document. The browser groups the reviewed offerings into the navigation
levels and uses the corresponding named parent wording where configured. Private
configuration references and resource revision records are excluded. Hierarchy
information uses the stored publication and does not read current operational
configuration. A diagnosis selection shows offerings for that diagnosis within
the exact modality, method and group branch; it excludes the same diagnosis from
other branches.

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

Matrix headers have separate levels for modality, biological group, assay and
diagnosis/subpanel. Each assay header spans its adjacent diagnosis columns;
different assay IDs remain separate even when their labels match. Gene-list names
and analysis types are available in each diagnosis header's tooltip and accessible
label. Selecting one shared list can therefore show several assay
columns with different coverage; these are separate published offerings, not
duplicate list columns. Assay labels prefer `name` (short name), then `display_name`,
then `asp_id`. These labels are captured in the reviewed publication; changing an
assay name requires a new catalog publication before public labels change.
New publications capture `assay_label` for compact views and `assay_display_name`
for service and comparison headings. Views use the captured short label when a
full-name snapshot is absent.
Diagnosis headers use the configured diagnosis display name (for example `MPN`
or `CLL`); diagnoses do not have a separate short-name field. The supplied demo
assays include compact `name` values. Existing installations must set the assay's
**Name** and publish a reviewed catalog revision to replace older captured labels.

Public information panels use technical-family colors for their borders and subtle
gradients, with explicit DNA/RNA modality badges. Large price and turnaround badges
appear at the top right, wrapping below the heading on narrow screens. They retain
separate assay/diagnosis labels when values differ between services.

Specimen requirements, methodology, limitations and ordering information follow
in the main panel. Analysis tabs (such as SNV, CNV and Fusion) show that analysis's
published gene lists and revisions above a table with one row per unique published
gene. The table does not repeat the gene-list name on every row. Search and CSV export apply
to the selected analysis. HGNC symbols link to the public gene reference page.
The table adds current HGNC identifiers, names, chromosome, locus and one transcript
from the public assay reference endpoint where available. Reference annotations
do not expand or replace the frozen published gene scope; unavailable annotations
appear as dashes and the published symbols remain visible if the reference request
fails.

The transcript display prefers RefSeq MANE Plus Clinical (`RS MC+`), Ensembl MANE
Plus Clinical (`ENS MC+`), RefSeq MANE Select (`RS MANE`), then Ensembl MANE Select
(`ENS MANE`). If none is recorded, it uses one protein-coding RefSeq accession
(`NM_` or `XM_`, badge `PC`) from the accession list or transcript metadata.
Within the same priority, accessions are sorted for a stable choice. No transcript
is inferred from an Ensembl gene ID, noncoding RefSeq accession, or gene-level
biotype. A dash means no eligible transcript is available. Badge tooltips show the
full designation, and CSV exports include the chosen accession and designation.
This display choice does not change any finding's selected transcript.

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
