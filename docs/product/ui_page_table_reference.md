# UI Page And Table Reference

This page describes the information shown by each Coyote3 screen, how the major tables are read, and which badges or compact symbols can appear in each data area.

!!! info "Scope"

    This reference documents the React application as a clinical review surface. It describes what the user sees, what each table column means, and how badges should be interpreted. API contracts, collection schemas, and deployment details are documented separately in the API and operations sections.

## General Table Rules

All clinical tables follow the same basic conventions.

| Pattern | Meaning |
| --- | --- |
| Search field | Filters the visible table rows or submits a backend search, depending on the page. |
| Export to CSV | Downloads the same clinical context represented by the table, not a raw MongoDB dump. |
| Row count | Shows the total number of returned rows for the current filters and page. |
| Sorting | Server-paginated clinical tables sort the complete filtered result set before pagination. Sorting a column therefore changes the full result order, not only the currently visible page. Clicking additional sortable headers builds a multi-column sort. |
| Human dates | Dates are shown as relative text when appropriate, such as `6 h ago`; detailed timestamps remain available in tooltips or detail views. |
| Compact counts | Large counts use short forms such as `5K` so dense tables stay readable. |
| Header rows | Header cells are visually separated from data cells with stronger background and borders. |
| Detail action | Opens the clinical detail page for the row. |

!!! info "Table caching and refresh"

    Table requests are cached by their clinical query state: sample, page, page size,
    search text, sort columns, and sort directions. Revisiting the same query state
    can reuse cached data for a short time. Paged table state is also reflected
    in the URL so opening a detail page and returning to the sample restores the
    same tab, search, page size, page, and sorting context. Applying filters or
    changing finding state, such as false positive, blacklist, irrelevant,
    interesting, or tier, invalidates the relevant table queries so the next view
    reflects persisted backend state. Smaller client-side tables use the same
    multi-column sort component. When a page controls the table state, the
    sort order is reflected in the URL; otherwise only search and sort settings
    are stored in browser session storage. Row data is not duplicated there.

!!! tip "Clinical table reading"

    Start from the left side of a row. The status column tells you whether the finding has review flags, knowledgebase evidence, comments, or pharmacogenomic context before you read the biological columns.

## Badge Reference

### Review Status Badges

These appear in the compact status column of variant-like tables.

| Badge | Meaning | Typical location |
| --- | --- | --- |
| False-positive icon | The finding has been marked as a false positive. The row is visually muted/red-tinted and excluded from normal reporting decisions. | Small variants, CNVs, fusions, translocations, detail pages |
| Blacklist icon | The finding matches a blacklisted technical artifact unless an override exists. | Small variants and other finding tables |
| Irrelevant icon | The finding has been marked clinically irrelevant for the current review context. | Finding tables |
| Interesting icon | The finding has been marked for follow-up or special attention. | Finding tables |
| Comment icon | The finding has one or more comments or annotations. | Finding tables and detail pages |
| `OKB` | The gene is present in the local public OncoKB cancer gene cache. This links to the OncoKB gene page. | Status column, knowledgebase cards |
| `Rx` | Historical local OncoKB actionable evidence exists for the gene or alteration. This is local evidence only and can include drug-level fields from historical center data. | Status column, knowledgebase cards |
| `PGx` | The gene is present in the ClinPGx public gene cache. This links to ClinPGx public gene information when available. Detail pages can fetch richer public API knowledge on demand. | Status column, knowledgebase cards |

!!! warning "Badge placement"

    OncoKB and ClinPGx markers are not displayed beside the gene name. They are displayed in the status/evidence column so the gene symbol remains biologically faithful to the source finding.

### Tier Badges

| Badge | Meaning | Color intent |
| --- | --- | --- |
| `1` | Tier I, strong clinical significance. | Red/orange clinical priority |
| `2` | Tier II, potential clinical significance. | Yellow/orange review priority |
| `3` | Tier III, uncertain clinical significance. | Blue informational priority |
| `4` | Tier IV, benign or likely benign. | Green low-priority/benign |
| `-` | No tier has been assigned. | Neutral |

Clicking a tier badge in a finding table opens the reported-variant context page for that tiered variant when the row has enough saved classification context.

### Filter Flag Badges

Filter badges are compact labels derived from the VCF `FILTER` field and center-configured metadata in `api/config/filter_flag_metadata.yaml`.

| Badge family | Meaning |
| --- | --- |
| `PASS` | The finding passed primary pipeline filters. |
| `FAIL...` | A failing quality or rule condition. These badges use fail coloring. |
| `WARN...` | A warning condition that requires review but is not an automatic failure. |
| `PON...` | Panel-of-normals overlap or related artifact evidence. |
| `LOD...` or `T_LOD...` | Limit-of-detection or low-support review condition. |
| Other configured labels | Center-specific labels defined in filter metadata. |

Hovering a flag badge shows the exact raw flag token and the configured explanation for that token.

### VEP Consequence And Impact Badges

Consequence badges are rendered from the selected VEP consequence terms and VEP metadata.

| Impact | Meaning | Color intent |
| --- | --- | --- |
| `HIGH` | Usually protein-truncating, splice-critical, or otherwise high-impact. | Fail/red |
| `MODERATE` | Protein-altering or likely coding consequence. | Warn/yellow |
| `LOW` | Synonymous or low-effect coding consequence. | Pass/green |
| `MODIFIER` | Usually non-coding, intronic, regulatory, upstream, or downstream. | Neutral |

Common compact labels include `missense`, `frameshift`, `splice donor`, `splice acceptor`, `splice region`, `inframe insertion`, `inframe deletion`, `synonymous`, `intron`, and `coding sequence`. Hovering a consequence badge shows the source VEP term, impact, and metadata description.

### Caller And Prediction Badges

| Badge type | Meaning |
| --- | --- |
| Caller badge | One badge per caller, such as `FREEBAYES`, `TNSCOPE`, or `VARDICT`. |
| SIFT/PolyPhen prediction | Color-coded functional prediction. Damaging/deleterious calls use fail or warning colors; benign/tolerated calls use pass coloring; unknown calls are neutral. |
| Biomarker badge | Displays available biomarker values such as MSI or HRD. Missing or undefined biomarkers are omitted rather than shown as empty values. |

## Dashboard

The dashboard is the operational entry point. It summarizes work that a reviewer, developer, or administrator should notice quickly.

| Section | Information shown |
| --- | --- |
| Sample totals | Total samples, analyzed samples, pending samples, and available variants. |
| Variant review | SNV, CNV, fusion, translocation, false-positive, blacklist, pathogenic, VUS, and tier distribution summaries. |
| Workflow queues | Ingest status, report readiness, and review state summaries. |
| Sample profiles | Production and non-production profile distribution. |
| Recent samples | Latest loaded samples with assay, subpanel, status, counts, and relative added time. |
| Gene coverage per assay | Charted covered and germline gene scope by assay/catalog configuration. |
| Resource health | Operational counts and configuration coverage that help identify stale or missing setup. |

!!! info "Dashboard performance"

    Dashboard panels should use aggregate backend endpoints instead of loading full clinical tables. The page is intended to answer "what needs attention?" without triggering heavy review queries.

## Samples Page

Route: `/samples`

The Samples page lists loaded samples visible to the user. It starts in production scope and can be switched to all permitted profiles.

| Column | Data shown | Badges and symbols |
| --- | --- | --- |
| Sample | Clickable sample name. Opens the sample detail page. | Document icon |
| Case ID | Case sample identifier from the sample document. | Plain text |
| Case Clarity | Case Clarity/LIMS identifier. | Plain text |
| Control | Control sample identifier when paired. | `-` when unavailable |
| Control Clarity | Control Clarity/LIMS identifier. | `-` when unavailable |
| Profile | Sample profile/environment. | Profile badge such as production/prod |
| Assay | Assay panel identifier. | Plain text |
| Subpanel | ASPC/subpanel context. | Plain text |
| Analysis | Ingest/analysis status. | `ready`, warning, or pending-style badge |
| Report | Reported state. | `reported` or `unreported` badge |
| Counts | Short data counts by analysis type. | `SNV`, `CNV`, `Fusion`, `SV`, `Cov` badges |
| Added | Human relative added time. | Full timestamp in tooltip |
| Actions | Opens the sample. | Arrow/detail button |

## Sample Detail

Route: `/samples/:id`

The sample detail page is the main review workspace. Tabs are shown from the ASPC analysis configuration for the sample, so a sample only shows analysis areas that are enabled for that assay/subpanel/environment. The selected tab is represented by the `tab` URL parameter; refresh, browser history, and return navigation therefore restore the same review area. Tab availability is validated only after the sample context has loaded.

### Sample Header

The header shows sample name, assay, profile, ingest status, and available biomarkers. Biomarker badges are shown only when values are present and meaningful.

### Overview Tab

The overview tab mirrors the sample settings and sample-level context needed before review.

| Card | Information shown |
| --- | --- |
| Overview | Case and control identifiers, Clarity IDs, pool IDs, run, reads, FFPE, and purity when present. |
| Files and QC | Expected input files, whether each file path is present, and file availability/size when the backend can inspect the mounted path. |
| Gene settings | Selected SNV/CNV gene lists, ad-hoc gene lists, and effective gene scope. |
| Biomarkers | MSI, HRD, and other configured biomarkers loaded for the sample. |

!!! caution "Raw payloads"

    Normal clinical views should not expose raw JSON payloads. Raw inspectors belong only in explicit diagnostics or developer/admin debug screens.

### Small Variants Tab

Route: `/samples/:id` with Small Variants tab

| Column | Data shown | Badges and symbols |
| --- | --- | --- |
| Select | Row checkbox for bulk actions. | Checkbox |
| `S` | Review and knowledgebase status. | False-positive, blacklist, irrelevant, interesting, comment, `OKB`, `Rx`, `PGx` |
| Gene | Source display gene resolved through HGNC when available. | Gene link; info indicator when alias/previous symbol was normalized |
| HGVS | HGVSc and HGVSp for the selected transcript. | Expandable text |
| Exon | Selected transcript exon value. | Plain text |
| Intron | Selected transcript intron value. | Plain text |
| Type | Compact variant class. | `SNV`, `DEL`, `INS`, `INDEL`, `SUB` |
| Indel Size | SVLEN/indel size when present. | `-` when unavailable |
| Consequence | VEP selected consequence terms. | Impact-colored consequence badges |
| PopFreq (%) | Public population frequency as percent. | Monospace number |
| Tier | Current classification tier. | Tier badge; opens reported context when available |
| Chr:Pos | Chromosome coordinate. | Neutral coordinate link for IGV |
| Flags | Filter flags from VCF/filter metadata. | PASS/WARN/FAIL/PON/LOD badges |
| Case (`sample`) | Case VAF and depth. | `VAF% (VD/DP)` |
| Control (`sample`) | Control VAF and depth. Hidden for unpaired samples. | `VAF% (VD/DP)` |
| Actions | Opens variant detail. | Detail icon |

Bulk actions include assigning or removing tiers, marking/unmarking false positive, marking/unmarking irrelevant, marking/unmarking interesting, adding blacklist entries, overriding blacklist, and clearing blacklist overrides. Bulk actions require confirmation and update the table in place after success.

!!! warning "Tier annotation text"

    Bulk Tier 3 assignment creates the approved automatic Tier III annotation
    text for each selected small variant. Tier 1, Tier 2, and Tier 4 assignments
    do not create automatic text. Templates for those tiers must not be added
    until their wording has been reviewed and approved by the responsible
    genetics team.

Small-variant sorting is performed after all active filters and search terms have
been applied and before the page slice is returned. Frequency columns, including
case VAF, control VAF, and population frequency, are sorted numerically across
the complete filtered result set. CNV, fusion, and translocation tables follow
the same rule: search and multi-column sort are applied to the filtered backend
result before pagination.

### CNVs Tab

The CNV tab lists copy-number events and opens CNV detail pages.

| Column family | Data shown |
| --- | --- |
| Status | Review flags, comments, and evidence badges where applicable. |
| Gene/region | Primary gene list and genomic region for the event. |
| Type/effect | Gain, loss, amplification, deletion, or configured CNV effect. |
| Size/copy number | Event size, copy number, log ratio, and supporting metrics when available. |
| Tier | CNV classification tier. |
| Actions | False-positive, report inclusion/exclusion, noteworthy, and detail-page actions. The labeled **Report** control persists report inclusion immediately and changes to **Exclude** for included CNVs. |

The CNV bulk-action menu is limited to CNV review operations: mark or unmark
false positive, include or exclude from the report, and mark or unmark
noteworthy. Small-variant tier, relevance, and blacklist operations are not
shown in this menu.

#### CNV Profile Review

When a DNA sample includes an ingested CNV profile image, the CNV tab presents the calls table and profile in one review workspace. On desktop displays, drag the divider to allocate more width to either the table or image; the selected split is retained in the browser for later reviews. The divider also supports the arrow, Home, and End keys. On narrower displays the panes stack vertically.

The rotate control switches the profile between its original `0°` orientation and a clockwise `90°` orientation. The image scales with the available pane width as the divider moves, and the profile card expands to the complete rotated image height. Selecting the image opens the original profile in a separate browser tab.

### Fusions Tab

The fusions tab lists RNA or DNA fusion calls.

| Column family | Data shown |
| --- | --- |
| Status | Review flags, comments, and knowledgebase indicators when available. |
| Gene 1 / Gene 2 | Fusion partners. |
| Breakpoints | Coordinates and transcript context when available. |
| Support | Spanning pairs, unique reads, anchor support, and caller information. |
| Tier | Fusion classification tier. |
| Actions | False-positive and detail-page actions. Fusion rows do not expose a report-inclusion control because fusion reporting is governed by the fusion review/filter workflow rather than an `interesting` finding flag. |

The fusion bulk-action menu contains only fusion review operations: mark or
unmark false positive and mark or unmark irrelevant.

### Translocations Tab

The translocations tab lists structural rearrangements.

| Column family | Data shown |
| --- | --- |
| Status | Review flags and comments. |
| Gene 1 / Gene 2 | Genes linked to each breakpoint when available. |
| Positions | Breakpoint positions or BND positions. |
| Type | Structural variant type. |
| HGVS | Structural HGVS or notation when available. |
| Panel | Matching panel/gene-list context. |
| Tier | Structural variant tier. |
| Actions | False-positive, report inclusion/exclusion, and detail-page actions. The labeled **Report** control changes to **Exclude** after the translocation is included. |

The translocation bulk-action menu contains only structural-event review
operations: mark or unmark false positive and include or exclude from the
report. Small-variant tier, relevance, noteworthy, and blacklist operations are
not shown in this menu.

### Coverage Tab

The coverage tab shows DNA sample quality coverage and gene-level coverage context. It appears when the active ASPC enables `COVERAGE` and the DNA sample has a successfully ingested `cov` resource. Coverage is independent of both CNV calls and the CNV profile image.

| Area | Information shown |
| --- | --- |
| Summary | Coverage thresholds, pass/warning/error counts, and overall coverage state. |
| Gene table | Gene symbol, HGNC context, exon/probe counts, low-coverage intervals, and threshold status. |
| Gene detail | Clicking a gene opens gene/probe/exon-level coverage information and links back to HGNC/gene context. |

### Reports Tab

The reports tab builds and previews clinical report content from current filters and reportable findings.

| Area | Information shown |
| --- | --- |
| Preview controls | DNA/RNA selection, snapshot toggle, save report, and export/PDF actions where enabled. |
| Report preview | Rendered clinical report preview using the configured report format. |
| Snapshot rows | Gene, variant, class/tier, and report text for reportable findings. |
| Report context | Collapsible technical context used for the report snapshot. |

!!! warning "Temporary snapshot"

    The report preview is temporary until saved. When a report is saved, Coyote3 stores the report document and reported finding snapshots so future searches can reproduce exactly what was reported.

## Finding Detail Pages

Routes:

* `/samples/:id/variant/:varId`
* `/samples/:id/cnv/:varId`
* `/samples/:id/fusion/:varId`
* `/samples/:id/translocation/:varId`

Detail pages put the review decision, comments, and evidence around the finding.

| Card or table | Information shown |
| --- | --- |
| Header | Finding identity, sample link, caller badges, and high-value evidence badges. |
| Classification | Current tier and controls for changing classification. |
| Add comment or annotation | Markdown editor. Detail pages use an explicit preview button. |
| Sample comments | Comments attached to this sample/finding context. |
| Global annotations | Reusable annotations for the same biological finding across samples. Clicking an existing annotation can load it as a draft. |
| Identity | Gene, transcript, HGVS, chromosome coordinate, variant class, and normalized HGNC context. |
| Genotype/evidence | Case/control VAF, depth, read support, callers, and quality evidence. |
| Transcript consequences | Selected and alternative transcripts, transcript provenance badges, canonical-source status, cDNA/protein notation, consequence, exon/intron, and impact. Alternate rows can be promoted to the primary display transcript when the selected transcript better represents the clinical review. |
| Prediction cards | SIFT, PolyPhen, and other configured prediction signals. |
| PON evidence | Separate rows by PON tool/source. |
| Knowledgebase | One consolidated card with collapsible sections for CIViC, BRCA Exchange, TP53/IARC, local OncoKB cancer gene/actionable evidence, public OncoKB lookup, and ClinPGx local/API context. ClinPGx local context stays compact; fetched API context can include VIP summary, guideline annotations, labels, top connected drugs, pathways, and variant annotation examples. |
| Seen in other samples | Prior reported or observed samples that match the same finding. |

!!! info "Transcript selection"

    Small variant display selects NCBI MANE Plus Clinical first, followed by Ensembl MANE Plus Clinical, NCBI MANE Select, and Ensembl MANE Select. Center and VEP canonical transcripts are subsequent fallbacks. HGNC normalization uses HGNC ID when possible and resolves previous symbols or aliases to the same approved HGNC record. Manual transcript changes use the versioned `anno_vep` vault for the sample's VEP version and refresh the selected transcript in place.

The transcript table can show the following compact badges in the **Transcript**
column:

| Badge | Meaning |
| --- | --- |
| NCBI MANE+ | HGNC marks the RefSeq transcript as MANE Plus Clinical. |
| ENS MANE+ | HGNC/VEP identifies the Ensembl transcript as MANE Plus Clinical. |
| NCBI MANE | HGNC maps the transcript to RefSeq MANE Select. |
| ENS MANE | HGNC maps the transcript to Ensembl MANE Select. |
| Canonical | The transcript matches the center canonical RefSeq map. |
| VEP canonical | VEP marks the transcript as canonical. |

The **Canonical** column shows the canonical source used for the row. Center
canonical evidence comes from the configured `refseq_canonical` collection after
HGNC normalization; VEP canonical evidence comes directly from the VEP CSQ
payload.

## Tiered Variant Search

Route: `/variants/search`

This page searches reported tiered variant annotations across samples.

| Control or column | Information shown |
| --- | --- |
| Search mode | Variant, gene symbol, HGVSp, HGVSc, genomic, transcript, subpanel, author, annotation text, or all fields. |
| Include annotation text | Includes stored annotation/report text in the search query. |
| Assays | Filters results by assay. |
| Tier cards | Current result count by tier. |
| Assay distribution | Tier count distribution by assay for the current search. |
| Tier | Reported tier badge. |
| Gene | Gene symbol for the reported finding. |
| Variant | HGVS or compact variant string, expandable for long values. |
| Assay | Assay or assay group. |
| Subpanel | Subpanel/diagnosis context. |
| Author | User who created the annotation/classification. |
| Annotation | Stored annotation text, merged with class context when applicable. |
| Samples | Samples and report links where this reported variant appears. |

## Reports Page And Saved Reports

Routes:

* `/reports`
* `/samples/:id/reports/:reportId`

The Reports page lists saved reports and provides access to saved clinical report output. A saved report contains its report snapshot, filter snapshot, ASPC identifier, report metadata, and reported finding references.

## Assay Catalog

Route: `/public/catalog`

The assay catalog combines YAML catalog metadata with ASP, ASPC, ISGL, and gene metadata from the database.

| Area | Information shown |
| --- | --- |
| Modality tree | DNA/RNA, modality section, assay group, assay, subpanel, and gene list navigation. |
| Header | Catalog title, subheading, description, catalog/ASP/ASPC/subpanel identifiers. |
| Input material | Sample material badges from catalog metadata. |
| TAT | Turnaround time from catalog metadata. |
| Sample types | Accepted sample types as badges. |
| Genes | Covered and germline gene counts. |
| Available analysis | Analysis types configured for the catalog item. |
| Reporting sections | Report sections configured for the catalog item. |
| Clinical indications | Indication badges or text. |
| Limitations/public notes | User-facing explanatory notes. |
| Gene table | HGNC ID, symbol, gene name, status, locus, sortable locus, aliases, and other available HGNC fields. |

## Assay Catalog Matrix

Route: `/public/matrix`

The matrix shows gene coverage across catalog columns.

| Header row | Meaning |
| --- | --- |
| Row 1 | Modality or large catalog section such as WGS, WTS, targeted panels, or RNA fusion panel. |
| Row 2 | Assay group or section within the modality. |
| Row 3 | Assay, subpanel, or gene-list column label. |
| Body rows | One row per gene. A tick means the gene is present in that catalog column; `-` means absent. |

Matrix filters include gene search, modality, section, and gene list. Gene search returns focused rows; otherwise the matrix is paged to keep loading fast.

## Gene Pages

Routes:

* `/public/gene/:geneId/info`

Gene pages present HGNC-centered gene context.

| Section | Information shown |
| --- | --- |
| Identity | Approved symbol, HGNC ID, gene name, status, locus, aliases, and previous symbols. |
| Transcript context | MANE Clinical Plus, MANE Select, Ensembl/RefSeq transcript information when available. |
| Catalog membership | Assays, subpanels, and gene lists that include the gene. |
| Knowledgebase markers | OncoKB public cancer gene, historical actionable evidence, and ClinPGx cache/API context when available. |

## Admin Pages

Routes:

* `/admin`
* `/admin/:resource`
* `/admin/:resource/create`
* `/admin/:resource/:id/view`
* `/admin/:resource/:id/edit`
* `/admin/audit`
* `/admin/controls`
* `/admin/ingest`
* `/admin/ui-routes`

Admin pages use forms and explicit contracts rather than JSON editors for normal workflows.

| Page | Information shown |
| --- | --- |
| Admin home | Available admin resources and operational shortcuts. |
| Resource list | One search field, row count, informative columns, human updated dates, status badges, and view/edit/actions. |
| View page | Same structure as edit page, but read-only. |
| Create/edit page | Field-specific form controls, constants-backed select options, grouped permissions, and validation messages. |
| Audit events | Actor, event type, resource, method/path, severity, outcome, created time, request ID, and details. |
| Application controls | Runtime toggles for Celery task families, application modules, and retention policies. |
| Ingest workspace | Watch-folder configuration, ingest task state, and manual ingest controls. |

### Admin Badge Families

| Badge | Meaning |
| --- | --- |
| Role badges | Configured role colors for admin, developer, tester, manager, user, intern, viewer, and external roles. |
| Auth type | `local` and `ldap` badges; a user can have multiple auth types. |
| Active state | Active/inactive status. |
| Assay category | DNA/RNA and other configured categories. |
| Assay group/family/platform | Constants-backed assay group, family, sequencing platform, and read-mode badges. |
| Permission group | Compact permission labels grouped by domain; hover shows the exact permission key such as `samples:edit`. |

!!! caution "Governance changes"

    Clinical configuration resources such as ASP, ASPC, and ISGL follow append-only/versioned governance rules. User, role, and permission records are edited through audited updates rather than raw document mutation.

## Notifications

Route: `/notifications`

Notifications show clinically or operationally relevant events only. Errors are translated into user-facing messages where possible instead of exposing raw stack traces or generic `500` text.

| Field | Meaning |
| --- | --- |
| Severity | Info, success, warning, or error. |
| Title | Human-readable action summary. |
| Message | Useful next-step-oriented explanation. |
| Context | Sample, variant, report, ASP, or admin resource when applicable. |
| Time | Human relative timestamp with full date available. |

## Profile And Static Pages

| Route | Purpose |
| --- | --- |
| `/profile` | Shows account identity, roles, auth types, scopes, editable profile settings, and password controls when local auth is enabled. |
| `/about` | Product, application version, database names, software versions, reference versions, support summary, and useful operational links including documentation, license, repository, and issue submission. |
| `/contact` | Public contact, service hours, support roles, address, and configured center links from the contact TOML file. |
| External license link | License and usage terms from the configured codebase link. |
