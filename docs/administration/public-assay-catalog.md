# Public Assay Catalog

The catalog describes a center's publicly offered assays. It combines governed
presentation content with active assay definitions, production configurations,
and public gene lists. Catalog editing never changes ingest requirements,
clinical filters, reporting rules, or existing samples.

The public view presents offered analyses, included genes, categories, sample
requirements and turnaround times. Reporting sections are controlled by the ASPC
and reporting rules, not the catalog. Internal catalog, assay, configuration and
subpanel identifiers are omitted from public detail cards; administrators can
inspect the underlying links in the editor's **Database references** section.

The landing page displays the configured **Catalog heading** and **Introduction**
beside the category navigation. The introduction supports formatted text and links.
Assay details and gene tables appear after selecting a category; **Catalog overview**
returns to the introduction. Set this public introduction in the catalog editor and
preview it before publishing.

Navigation arrows expand or collapse branches without changing the displayed entry.
Select an entry's name to view its details. The gene table includes available HGNC,
OMIM and MANE transcript references from the installed gene database; missing values
are shown as a dash. These references describe genes and transcripts, not a clinical
classification of a sample finding.

Platform, read mode and read length come from the linked assay definition. In
**Administration → Assays**, the form offers editable defaults of **Illumina**,
**PE (paired-end)** and **150 bp per read**. Confirm these values before saving;
**SE** means single-end, and available modes depend on the platform. Update the
assay definition to change these catalog details. Missing stored values are not
presented as confirmed sequencing specifications.

Before catalog entries are available, the public catalog displays **Add catalog**
setup guidance. An empty catalog is a normal installation state. The shared layout
also reads catalog context to build navigation, even outside the catalog page;
this background read returns an empty context without a request-failure notification.
Requests for a specific unavailable entry still return a not-found response.

## Create the dependent records first

Anonymous gene-list endpoints, catalog gene tables, exports, and the matrix expose
only explicitly public, active, non-adhoc gene lists. Gene-list descriptions are
sanitized and the public response excludes private administrative fields. ASP
descriptions use the same restricted public HTML formatting policy.

1. Create and activate the ASP in **Assay Panels**.
2. Create the relevant public ISGLs, linked to their assays and subpanels.
3. Create and activate the production ASPCs for those assays and subpanels.
4. Open **Admin > Public Assay Catalog** at `/admin/assay-catalog`.
5. Link each public entry to its ASP and production ASPC, then select its analyses.
6. For each analysis, select one or more eligible ISGLs or check **No gene list**.

The builder lists active assays, active production configurations, and active,
public, non-ad-hoc gene lists. It does not expose sample data. Publishing does
not make a private gene list public. Each entry can link a given gene list only
once; duplicate references prevent submission for approval.
That reference can serve multiple analyses. The builder filters lists by the
selected assay and, where a list declares group restrictions, the assay group.
Changing the assay clears its gene-list assignments so they can be reviewed for
the new assay.

## Gene lists by analysis

Each selected analysis has its own selection card. Search narrows the eligible
lists without clearing checked values. Select multiple lists when an analysis
uses more than one diagnostic or reporting gene set. List descriptions remain
editable under **Selected gene-list descriptions**.

**No gene list** is an explicit catalog declaration, not an empty selection. It
removes list links for that analysis while retaining their links to other analyses.
Submission and publication reject incomplete assignments, contradictory selections,
and lists that are no longer active, public or eligible for the assay and group.
Catalog assignments describe the public offering; they do not alter sample filters.

| Stored field | Meaning |
| --- | --- |
| Entry `analysis` | Analyses offered by the catalog entry |
| Entry `gene_lists[].isgl_id` | Reference to the public ISGL; gene contents remain in the source list |
| Entry `gene_lists[].analysis` | One or more entry analyses that use this list |
| Entry `no_gene_list` | Entry analyses explicitly declared to have no linked gene list; defaults to an empty list |

The catalog and draft preview show analysis tabs in the gene-table card on the right.
The first analysis and its first linked list open automatically. Selecting a tab
shows only that analysis's lists. Selecting a list displays its
genes. The matrix adds analysis to the section, assay, subpanel and gene-list
dimensions, with filters for each. Rows remain paginated; shared lists are read
once per matrix request. **N/A** means no list is assigned to an analysis, while
the absence marker means a gene is not in a selected list.

> [!IMPORTANT]
> When analyses are defined, assign all linked lists to those analyses.
> Before submitting a successor draft, assign those
> lists to analyses or remove the references and select **No gene list** where
> appropriate. No assignment is inferred from a list name or gene content, and no
> published document is rewritten automatically.

## Hierarchy and identity

The left navigation represents the catalog hierarchy. For example:

```text
DNA
  WGS
    Hematology
    Solid
  Panels
    Solid
      Breast
      Colon
RNA
  Panels
    Fusion
  WTS
```

These are example offerings, not installed clinical definitions. Each section has
a DNA/RNA category. **Folder** entries organize families and groups; **Assay or
subpanel** entries reference installed clinical resources. Use **Add child entry**
and **Parent entry** to build or move branches. A parent cannot be removed while
it has children. Missing parents and cycles are rejected when a draft is saved.
Without a published catalog, collection-derived navigation groups active assays
by DNA/RNA, family, and assay group.

The right panel describes the selected entry. Analysis tabs belong to its gene-table
card, not the navigation tree. Each tab offers only gene lists assigned to that
analysis. Changing the gene list does not replace the selected entry's heading or
available analyses.

Entry details remain independent of gene-table selection. The coverage summary
describes the assay, while the table count describes the selected list. List-specific
wording appears inside the gene-table card. Navigation typography distinguishes
sections, families, groups and deeper entries.

If an entry has no analyses after inheritance, its first general gene list opens
automatically. General lists are references without analysis assignments and can
be configured under **General gene lists** in the editor. An unspecified list
inherits from the nearest parent that defines one. Assay, group, subpanel and
public-visibility checks still apply. An analysis explicitly marked **No gene list**
does not fall back to a general list.

### Inherited information

An unspecified field inherits from the immediate parent, recursively up to the
section. Nonempty values replace the inherited field; lists are replaced rather
than appended. Labels, navigation identities and entry types are always local.
**Suppress inherited details** keeps selected fields empty. **No gene list** is an
explicit per-analysis declaration and removes inherited list bindings for that analysis.

| Field | Inheritance and validation |
| --- | --- |
| Description, material, sample modes, turnaround, indications, limitations, notes | Inherit when blank; override locally or explicitly suppress |
| Analyses | Inherit the complete list; local selections replace it |
| Assay, configuration and subpanel references | Inherit when unspecified; all resolved references must match on publication |
| Gene lists and analysis assignments | Inherit the list of references; no gene content is copied |
| `parent_key` | Entry key in the same section; absent means section root |
| `node_kind` | `folder` for organization or `entry` for an assay/subpanel offering |
| `clear_fields` | Names of fields that must not inherit; defaults to an empty list |
| Section `omics` | `dna` or `rna`; determines supported analysis choices |

> [!IMPORTANT]
> Presentation inheritance does not change query rules, reporting rules, assay
> membership or sample filters. The resolved gene lists must belong to the selected
> assay, respect declared group and subpanel restrictions, and support the analysis
> through their ISGL `list_type`. The supported ISGL types are a subset of the DNA/RNA
> analysis types. An analysis without an applicable list uses **No gene list**.

DNA/RNA analysis choices come from the application-owned clinical capability
constants. A center cannot introduce an unsupported analysis by editing catalog text.
The packaged demo uses DNA → Panels → Hematology and RNA → Panels → Fusion, with
an inherited DNA focus entry demonstrating child presentation defaults.

DNA and RNA are starter sections containing editable WGS, WES, WTS and Panels
folders. On a new installation, select **Create first draft** beneath
**Starter catalog** in the sidebar. For an existing publication, select
**Edit published catalog**. In a draft, use **Add section** for another section, edit
**Section display name** to rename it, use the arrow controls to reorder it, or
choose **Remove section**. The public catalog and matrix retain the entered name.
Section identifiers remain stable when display names change. These presentation
sections are separate from application-owned assay families and analysis types.

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

The [catalog contract](../reference/mongodb-collections.md#public_assay_catalog) lists
stored fields and defaults. Public visibility also requires the references and
publication steps below; a valid JSON document alone does not publish an offering.

## Authoring

The initial view is the published catalog, read-only. **Edit published catalog**
creates a separate draft from that publication. **Create first draft** is
available when no catalog has been published. Several drafts can coexist.

Select a section or entry in the structure sidebar to edit its fields. Add,
remove, and reorder sections; add or remove assay entries and gene-list
descriptions. Use the introduction view for the catalog heading, introduction,
and maintainer.

Introductions, section descriptions, assay and gene-list descriptions, limitations
and public notes have visual formatting controls for **bold**, *italic*, underline,
bulleted and numbered lists, hyperlinks, link removal and clearing inline formatting.
Select text before applying a format or inserting a link. Links accept `https://`,
`http://` and `mailto:` addresses. Pasted text is inserted without external formatting;
apply the editor controls as needed. Saved and displayed HTML is sanitized.
Display names, identifiers, badges and other structured fields remain plain text.

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

## Gene metadata

Assay gene pages retain every covered gene even when HGNC metadata is unavailable.
Those rows are marked **Unresolved** and have no fabricated HGNC identifier.
For targeted panels, assay-specific gene-list views intersect the list with the
panel's covered genes. WGS and WTS views retain the complete associated public
gene list rather than applying a targeted-panel intersection.

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
cannot support this workflow. See [MongoDB deployment](../deployment/mongodb-setup-and-recovery.md).

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

The workspace response's `presets` object contains `analysis`, `input_material`,
and `sample_modes` lists. `analysis_by_omics` maps `dna` and `rna` to their
supported analysis lists. The builder uses the selected section's omics layer
to choose its analysis options.

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
