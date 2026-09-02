# User Action and Operational Impact Reference

This reference maps UI controls to backend endpoints, persistent state changes, and visible outcomes. It is mainly intended for QA and engineering work.

## Core Sample Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Apply selected** | Sample Overview Gene Settings | `PUT /api/v1/samples/{id}/genelists/selection?target={snv,cnv,fusion}` | `samples.filters.somatic.snv.snvlists`, `samples.filters.somatic.cnv.cnvlists`, or `samples.filters.somatic.fusion.fusionlists` | Update of the selected analysis scope, its table query, report preview snapshots, and sample summaries. Lists never cross analysis boundaries. |
| **Save Ad-Hoc** | Sample Overview Gene Settings | `PUT /api/v1/samples/{id}/adhoc-genes?target={snv,cnv,fusion}` | `samples.filters.<target>.adhoc_genes` | Insertion of targeted gene inclusions for the selected analysis domain. |
| **Clear Ad-Hoc** | Sample Overview Gene Settings | `DELETE /api/v1/samples/{id}/adhoc-genes?target={snv,cnv,fusion}` | Removes `samples.filters.<target>.adhoc_genes` | Reversion of the selected target to ISGL/ASPC-defined gene scope. |
| **Download** | Report Catalog | Service file stream | (Read-only) | Local archival retrieval of report PDF/JSON. |

## DNA Interpretation Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Apply (Filters)** | Discovery Sidebar | `PUT /samples/{id}/filters` | `samples.filters` (DNA) | Recalculation of findings within active review tables. |
| **Reset** | Discovery Sidebar | `DELETE /samples/{id}/filters` | `samples.filters` (Defaults) | Re-initialization of assay-original thresholds. |
| **Apply (Bulk)** | Bulk Action Panel | `PATCH /api/v1/samples/{id}/classifications/tier` | Classification annotations and, when requested for Tier III small variants, a generated text annotation | Update the selected findings without changing report-rule configuration. |
| **Finalize Report** | Report Preview | Report creation endpoint | `reported_variants` snapshots | Generation of immutable clinical report record. |

## Finding-Level Clinical Interactions (SNV, CNV, SV)

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Mark False Positive** | Detail Views | `PATCH .../flags/false-positive` | `fp` flag status | finding removal from prioritized review streams. |
| **Classify (Tier)** | Classification Panel | `POST .../classifications` | `annotations.class` | Formal clinical tier assignment applied. |
| **Remove Class** | Classification Panel | `DELETE .../classifications` | Mutation of active annotation index | Clearance of clinical priority markers. |
| **Save Comment** | Annotation Form | `POST .../annotations` | `annotations` collection record | Persistence of review notes and diagnostic audit trail. |
| **Add to Blacklist** | Variant Details | `POST .../blacklist_entries` | `blacklist` collection update | Systematic exclusion from future center-level findings. |

### Detail Page Action Rules

Finding detail pages expose only actions that are meaningful for the active domain:

- **Small variants**: false-positive toggle, interesting toggle, irrelevant toggle, add-to-blacklist, blacklist override, and clear blacklist override.
- **CNVs**: false-positive toggle, report inclusion toggle, and noteworthy toggle.
- **Translocations**: false-positive toggle and report inclusion toggle.
- **Fusions**: false-positive toggle and selected-call control. Fusion call selection is separate from the finding flag controls because it changes the evidence source rather than the clinical interpretation state.

Blacklist entry creation asks for confirmation because it changes center-level future filtering. Blacklist override is sample-scoped and is only available when a blacklist match is present.

### Comment Composer Rules

Comment behavior is intentionally different between sample-level review and finding-level review:

- **Sample comments** use the markdown toolbar and show a live rendered preview below the editor while the user writes.
- **Finding detail comments** use the markdown toolbar and explicit Edit/Preview mode only. They do not show a second live preview.
- **Suggested text** is available only in sample comment composition. Finding comments are written explicitly by the reviewer.
- Clicking an existing visible comment loads that comment text into the composer as a draft for reuse or editing.
- Hide/unhide controls mutate visibility; hidden comments remain auditable but are visually de-emphasized.

Global finding annotations and sample-specific finding annotations are shown in separate cards so reviewers can distinguish center-wide interpretation knowledge from comments tied to the active sample.

### Bulk classification text

Bulk classification always stores the requested Tier I-IV classification.
For Tier III small variants, the confirmation dialog also offers **Include
automatic text**. When selected, the backend calls
`create_annotation_text_from_gene` and stores its result as a separate text
annotation for each eligible variant. The generator uses the selected
consequence, gene, assay group, and local OncoKB gene status.

The option is unavailable for CNVs, fusions, and translocations, and for Tier
I, II, and IV. Those actions store the classification only. ASPC reporting
fields and clinical reporting YAML are not inputs to this annotation generator.

## RNA Interpretation Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Apply (Filters)** | Fusion Sidebar | `PUT /samples/{id}/filters` | `samples.filters` (RNA) | Dynamic recalculation of fusion visibility. |
| **Pick Call** | Fusion Detail | `PATCH .../selection/{idx}` | `fusions.selected_call` mutation | Designation of primary diagnostic evidence source. |
| **Classify Fusion** | Fusion Detail | Classification endpoint | `annotations` tier context | Tier assignment for targeted fusion event. |

## Administrative and Governance Actions

| UI Interceptor | Interface Context | Execution Endpoint | Persistent Mutation | Operational Outcome |
|---|---|---|---|---|
| **Save User** | Identity Management | `POST/PUT /admin/users` | `users` collection record | Mutated organizational user identity. |
| **Toggle Status** | Administrator Lists | `PATCH .../status` | `is_active` boolean | Modification of resource accessibility. |
| **Send Invite** | User Management | `POST .../invite` | Crypto-token generation | Email-link delivery or manual credential hand-off. |
| **Save Policy** | Roles/Permissions | Authorization endpoints | `roles` / `permissions` docs | Real-time update of RBAC enforcement policies. |
| **Save Panel/Config** | Assay Resources | ASP/ASPC endpoints | `asp_configs` / `assay_specific_panels` | Versioned update of center-level analytic logic. |
| **Queue Ingest** | Ingest Workspace | `POST /api/v1/internal/ingest/sample-bundle/upload/async` | Celery task entry plus staged upload files | Validated sample-bundle ingest is executed by workers and task state is visible in the UI. |

## Notification Semantics

Every mutating UI action emits a notification event to the client-side notification
store. Notifications include:

- tone: success, info, warning, or error
- source: UI module that initiated the action
- resource context: sample name, finding identity, admin resource type, or task id
- readable message: what changed and which clinical or administrative object was affected

The notification history is therefore useful for operator review, not only transient
toast display. Sample-related events include the sample name, and admin events include
the edited resource key or business identifier.

## Local Interface Controls (Non-Persistent)

The following controls manipulate the Browser Document Object Model (DOM) without triggering persistent backend state changes:

- **Hide false positives**: Browser-only visibility control for finding filters.
- **Navigation Collapse**: Sidebar and menu layout changes.
- **Pagination**: Local table paging within client-orchestrated datasets.
- **Expand/Collapse**: User-driven text visibility for long descriptions.
- **Chart Toggles**: Analytical chart mode switching (e.g., Target vs. Evidence).

## Table and Search Rules

All clinical tables use a visibly separated header row with bordered cells. Column content is left-aligned by default; tier columns are centered because they are categorical severity indicators. CSV export operates on the currently loaded table model and excludes selection/action columns.

Tiered variant search is a submitted search workflow. The user enters a query, chooses a mode, optionally includes annotation text, optionally restricts assays, and then clicks **Search**. This prevents unnecessary cross-sample annotation queries on every keystroke and keeps the displayed result set tied to the visible search criteria.

Supported tiered-variant search modes:

- **Variant**: searches `variant` and every canonical flat small-variant identity (`hgvsp`, `hgvsc`, `genomic`, and `genomic_hash`). CNV, fusion, and translocation identities use the universal `variant` field.
- **HGVSp**: searches the canonical flat `hgvsp` identity.
- **HGVSc**: searches the canonical flat `hgvsc` identity.
- **Genomic**: searches the canonical flat `genomic` and `genomic_hash` identities.
- **Gene symbol**: searches annotation gene symbols case-insensitively.
- **Transcript ID**: searches transcript identifiers.
- **Subpanel**: searches clinical subpanel labels.
- **Author**: searches annotation author names.
- **Annotation text**: searches free-text annotation/comment records.
- **All fields**: searches identity, context, author, subpanel, and annotation text fields together.

## Quality Assurance Execution Protocol

Analytical verification of UI actions must confirm:

1. **Interactive Trigger**: Successful UI invocation of the targeted control.
2. **Transactional Acknowledgement**: Verification of successful API response headers.
3. **Persistence Verification**: Refresh-based confirmation of server-side state commitment.
4. **Contextual Propagation**: Validation that related summaries (e.g., report totals) acknowledge the mutation.
