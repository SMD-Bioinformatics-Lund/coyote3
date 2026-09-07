# Public Assay Catalog

The catalog describes a center's publicly offered assays. It combines governed
presentation content with active assay definitions, production configurations,
and public gene lists. Catalog editing never changes ingest requirements,
clinical filters, reporting rules, or existing samples.

## Create the dependent records first

Anonymous gene-list endpoints, catalog gene tables, exports, and the matrix expose
only explicitly public, active, non-adhoc gene lists. Gene-list descriptions are
sanitized and the public response excludes private administrative fields. ASP
descriptions use the same restricted public HTML formatting policy.

1. Create and activate the ASP in **Assay Panels**.
2. Create the relevant public ISGLs, linked to their assays and subpanels.
3. Create and activate the production ASPCs for those assays and subpanels.
4. Open **Admin > Public Assay Catalog** at `/admin/assay-catalog`.
5. Link each public entry to its ASP, production ASPC, and applicable ISGLs.

The builder lists active assays, active production configurations, and active,
public, non-ad-hoc gene lists. It does not expose sample data. Publishing does
not make a private gene list public. Each entry can link a given gene list only
once; duplicate references prevent submission for approval.

## Hierarchy and identity

The public layout has sections, entries, and gene-list descriptions. A section
can be **Whole Genome Sequencing (WGS)**, **Whole Transcriptome Sequencing (WTS)**,
or **Targeted Gene Panels**. Entries such as **Hematology** and **Solid** sit
under those sections. Gene-list descriptions represent diagnoses or subpanels.
Centers can add sections and change display names without renaming an assay.

| Identifier | Purpose | Editable in builder |
| --- | --- | --- |
| Section and entry map keys | Stable public navigation identity | No; generated for new items |
| Entry `catalog_id` | Stable presentation identity | No; generated when saved |
| `asp_id` | Reference to `assay_specific_panels` | Select an installed assay |
| `aspc_id` | Reference to `asp_configs` | Select a production configuration |
| `isgl_id` | Reference to `insilico_genelists` | Select a public gene list |
| Version document `_id` | Identifies one draft or published release | No |
| Display name | Public heading, independent of database identifiers | Yes |

Database references remain visible in expandable reference details. They are not
substitutes for public display names.

## Authoring

The initial view is the published catalog, read-only. **Edit published catalog**
creates a separate draft from that publication. **Create first draft** is
available when no catalog has been published. Several drafts can coexist.

Select a section or entry in the structure sidebar to edit its fields. Add,
remove, and reorder sections; add or remove assay entries and gene-list
descriptions. Use the introduction view for the catalog heading, introduction,
and maintainer.

| Field | Input and validation |
| --- | --- |
| Input material | Select preset badges; add custom material beside the presets |
| Turnaround time | Positive integer or ascending integer range, plus days, weeks, months, or years |
| Sample modes | Select preset badges |
| Analysis | Select the canonical ASPC analysis options |
| Configuration | Active production ASPCs for the selected assay; no environment entry required |
| Gene lists | Active public ISGL references with editable public wording |
| Additional content | Limitations, public notes, report sections, and clinical indications |

For example, enter `7-10` and select `days`. Zero, negative durations, decimals,
descending ranges, and unstructured duration text are invalid. Blank means
unspecified, not zero. Invalid durations are indicated beside the input and
rejected by the API.

**Preview changes** displays the current local edit without saving. **Save
draft** saves a new draft revision and opens its preview. The preview resolves
ASP/ASPC/ISGL presentation metadata through the same application renderer as
the public catalog. View mode uses the public page's modality navigation,
assay details, gene-list selection, gene counts, and gene table on an opaque
theme surface. Draft selections resolve against the draft, not the current
publication. Check all sections before submitting. Unsaved changes
cannot be submitted. A draft is not public, even after it has been saved.

## Review and publication

| State | Allowed next operation | Publicly visible |
| --- | --- | --- |
| Draft | Edit, save, preview, submit to a selected reviewer | No |
| Submitted | Assigned reviewer approves or rejects | No |
| Approved | Assigned publisher publishes | No |
| Rejected | Create a revised draft from its content | No |
| Published | Read, export, inspect history | Yes, for the current release |

The author selects an active reviewer with `catalog:review`. The reviewer
must not be any user who edited that draft, nor the user submitting it.
Approval assigns an active publisher with `catalog:publish`; the publisher
must also be independent of every content editor. The reviewer and publisher
may be the same person if that person has both permissions.

Only the assigned reviewer or publisher can complete their respective stage.
The API rechecks eligibility at publication. Rejection requires a reason.
Submitted, approved, rejected, and published documents cannot be edited.
To revise rejected content, use **Revise as new draft**, then obtain approval
again. Publication requires valid active production references and supported
analysis badges.

The assigned reviewer receives an in-app notification containing a direct link
to the draft. Review results notify the creator, approval notifies the assigned
publisher, and publication notifies the creator. The workspace displays the
assigned users, review reason, and lifecycle events.

## Permissions and roles

| Bundled role | Permissions |
| --- | --- |
| `catalog_viewer` | `catalog:view` |
| `catalog_author` | `catalog:view`, `catalog:draft`, `catalog:submit` |
| `catalog_reviewer` | `catalog:view`, `catalog:review` |
| `catalog_publisher` | `catalog:view`, `catalog:publish` |

An identity administrator assigns these roles to the appropriate users.
Seeding roles does not grant them to users. Read-only access includes previews,
JSON downloads, lifecycle history, and revision snapshots, but no mutations.

## Versions, revisions, and storage

| Collection in the application database | Responsibility |
| --- | --- |
| `public_assay_catalog` | Single current public projection, identified by `catalog_id: default` |
| `public_assay_catalog_versions` | Separate draft/workflow documents and immutable published releases |
| `public_assay_catalog_revisions` | Full preserved document at each saved workflow revision |

The public version increases only when a release is published. Saving,
importing, submitting, and reviewing do not increment the public version.
Drafts record `base_version`; `content_version` is assigned at publication.
Each save or lifecycle transition increments that draft's `revision`.

Writes require the revision the caller inspected. A stale revision returns
HTTP 409 rather than overwriting another user's work. A draft based on an older
public version cannot replace a newer publication: create a draft from the
current publication and obtain fresh approval.

Publication updates the release, public projection, and revision snapshot in
one MongoDB transaction. MongoDB must run as a replica set; a single-node
replica set is sufficient for local development. A standalone MongoDB server
cannot support this workflow. See [MongoDB deployment](../operations/mongodb_deployment_and_recovery.md).

Lifecycle snapshots retain content, actors, assignments, decisions, and times.
Exporting while previewing a historical revision downloads that revision's
content. Historical previews are read-only; return to the current revision
before editing a draft.
Mutation requests use the application's traceability audit logging. Revision
snapshots do not expire through the catalog API and are distinct from the
operational audit log. Historical previews cannot be used to approve a different
current revision. A catalog that predates governed publication is preserved as
an explicitly marked baseline, without inventing a reviewer or approval.

Back up all three collections together. Audit events reside in the identity
database; notifications reside in the application database. Back up both
according to the deployment's retention policy.

## JSON exchange

The database catalog is the sole source of presentation hierarchy and wording;
there is no catalog YAML file, loader, or YAML import script. JSON uploads enter
the governed draft workflow rather than replacing the published catalog.

The **Matrix** action in view mode stays within the selected draft or historical
revision. Matrix columns use its section order, display names, assay entries,
and linked gene lists. Entries without gene lists show their ASP's covered genes.
Search and pagination retain the selected catalog. **Catalog** returns to its
catalog view; neither action publishes content. The public matrix uses the
currently published catalog with the same matrix builder.

The catalog gene table and matrix keep knowledgebase badges in a separate
**Annotations** column. Its checkbox shows or hides the column without changing
gene coverage. Annotations are initially visible in the catalog and hidden in
the matrix; each table remembers its setting in browser storage. Compact badges
show the full knowledgebase description on hover.

Public HTML formatting is sanitized during validation. Paragraphs, lists,
emphasis, tables, and HTTP/HTTPS/mail links are retained; executable content,
event handlers, embedded media, and unsafe URLs are removed. Review the saved
preview to inspect the validated content before submitting it.

**Export catalog** downloads the selected content; **Export section** downloads
one section as a `coyote3.public_assay_catalog_modality` envelope. Exports contain
presentation content and references, not user assignments, approval authority,
or patient data. They can include unsaved local edits.

**Import draft** validates a JSON file and creates a draft. A whole-catalog
import uses the supplied content. A section import copies the current public
catalog and replaces or adds only that section. References must resolve in the
destination installation before submission. Imported content must follow the
same preview, review, and publication workflow; an imported file cannot grant
itself published status. JSON is not an alternative database authority or an
in-browser editing surface.

## API

All routes below use the `/api/v1/admin/assay-catalog` prefix.

| Method and path | Permission | Purpose |
| --- | --- | --- |
| `GET /` | `catalog:view` | Published content, versions, source choices, eligible users, presets |
| `GET /versions/{oid}` | `catalog:view` | One complete workflow document |
| `GET /versions/{oid}/revisions` | `catalog:view` | Preserved revision snapshots |
| `POST /preview` | `catalog:view` | Resolve presentation content without persisting it |
| `POST /preview/matrix` | `catalog:view` | Resolve a draft matrix with gene search and pagination, without writes |
| `POST /drafts` | `catalog:draft` | Copy the current publication into a draft |
| `POST /imports` | `catalog:draft` | Create a draft from JSON content |
| `PATCH /drafts/{oid}` | `catalog:draft` | Save content with an expected revision |
| `POST /drafts/{oid}/submit` | `catalog:submit` | Assign reviewer and submit |
| `POST /drafts/{oid}/review` | `catalog:review` | Assigned reviewer approves or rejects |
| `POST /drafts/{oid}/publish` | `catalog:publish` | Assigned publisher atomically releases content |
