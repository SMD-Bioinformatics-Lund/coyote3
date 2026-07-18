# Complete Application Manual

This manual explains Coyote3 as a complete clinical genomics application: what the system is for, how data enters the platform, how review and reporting work, how configuration is governed, and how operators and developers should reason about the application.

!!! info "Audience"

    This page is written for clinical users, bioinformaticians, platform administrators, and software engineers. It explains the system in workflow order rather than by source-code package.

!!! warning "Clinical source of truth"

    Coyote3 records clinical review state, report snapshots, filters, and audit evidence. Do not correct production clinical state by editing MongoDB documents directly. Use the API, admin workflows, or a reviewed migration.

## 1. Product Purpose

Coyote3 supports clinical molecular review from sample ingest to report generation. The platform receives validated sample manifests and analysis outputs, persists normalized documents, applies assay-specific configuration, presents review workflows in a React UI, and stores report snapshots so a clinical decision can be reconstructed later.

The system is designed around four guarantees:

1. **Clinical reproducibility**: filters, report context, reported findings, and configuration identity are stored with the report.
2. **Assay-aware review**: available tabs, filters, gene lists, report sections, and thresholds come from assay configuration.
3. **Auditable operations**: important access, mutation, ingest, reporting, and admin events are audit logged.
4. **Separation of concerns**: React renders workflows, FastAPI owns rules and validation, Celery performs background work, and MongoDB stores persistent clinical and operational state.

!!! tip "How to read this manual"

    Start with the end-to-end workflow if you are learning the application. Use the later sections as reference for a specific domain such as ingest, reporting, access control, or operations.

## 2. End-To-End Workflow

The normal workflow is:

```text
assay setup
  -> sample manifest and analysis files arrive
  -> Celery or API ingest validates and imports the sample
  -> sample opens in the UI with ASPC-derived tabs and filters
  -> reviewer inspects findings, coverage, biomarkers, and comments
  -> reviewer adjusts filters or gene lists when clinically justified
  -> report preview is rendered from current effective review state
  -> report is saved with snapshots and artifacts
  -> audit and search workflows can reconstruct the decision later
```

### Workflow Ownership

| Step | Owner | Persistent State |
| --- | --- | --- |
| Assay definition | Admin/bioinformatics | ASP, ASPC, ISGL |
| Sample import | API/Celery | sample plus dependent analysis collections |
| Review | UI plus API services | filters, classifications, comments, finding state |
| Reporting | API report service | report document and reported finding snapshots |
| Governance | Admin/API | users, roles, permissions, audit events |
| Maintenance | Celery/admin controls | retention, log cleanup, task gates |

!!! caution "Snapshot discipline"

    A saved report must not depend on the current mutable sample view. It must carry enough snapshot state to explain what was reported, which filters were applied, and which ASPC context was used at report time.

## 3. Runtime Architecture

Coyote3 runs as separate services:

- `frontend`: React application and browser-facing UI.
- `api`: FastAPI service, contracts, domain logic, authorization, and database access.
- `worker`: Celery worker for ingest and maintenance work.
- `beat`: Celery scheduler for periodic tasks.
- `redis`: Celery broker, cache, and session infrastructure.
- `mongo`: clinical, operational, and configuration persistence.
- `reverse proxy`: one public entry point for web, API, and docs paths.

The API and worker load the same configuration and use the same repositories. That keeps manually triggered API actions and background task actions on the same validation and persistence path.

!!! info "One way into clinical data"

    All clinical writes should pass through application services and Pydantic contracts. Direct collection manipulation is reserved for reviewed migrations and controlled recovery operations.

## 4. Configuration Model

API-owned configuration lives under `api/config/`.

| File | Purpose |
| --- | --- |
| `api/config/app_config.py` | Runtime configuration objects and environment binding |
| `api/config/constants.py` | Product vocabularies and stable option lists |
| `api/config/runtime.py` | Public runtime helper facade |
| `api/config/coyote3_collections.toml` | MongoDB collection-name mapping |

Deployment-specific secrets and endpoints remain in environment files or secret stores:

- MongoDB URI
- Redis URL
- `SCRIPT_NAME` reverse-proxy mount prefix
- API secret keys
- LDAP and SMTP credentials
- mounted watch directories
- CORS and cookie settings

`SCRIPT_NAME` controls the browser-facing mount point when Coyote3 is served
below a domain path, for example `https://example.org/coyote3`. The value is
empty for root deployments and a leading-slash prefix such as `/coyote3` for
subpath deployments. The API keeps stable internal routes such as
`/api/v1/health`, while FastAPI publishes the configured `root_path`, React uses
the same prefix as its router basename, and static assets and direct report
downloads are generated below that prefix. The compose nginx proxy also renders
exact prefixed routes from this value, so direct access to the compose proxy uses
the same browser paths as the Apache-mounted deployment.

The unauthenticated public UI is mounted below `/public` inside the same app.
With `SCRIPT_NAME=/coyote3`, the public catalog is reached at
`/coyote3/public/catalog`. Public mode keeps the normal application shell but
shows only public catalog/reference navigation and a sign-in action.
The browser mount root accepts both `/coyote3` and `/coyote3/`; the slashless
form is normalized by the frontend before React Router starts.

With `SCRIPT_NAME=/coyote3`, browser-facing support URLs are:

- `/coyote3/api/v1/docs` for Swagger UI.
- `/coyote3/docs-site/` for the documentation site.
- `/coyote3/public/catalog` for the public assay catalog.

!!! info "Reverse proxy behavior"

    The public URL always includes `SCRIPT_NAME` for subpath deployments. Inside
    the container network, nginx still forwards to stable internal targets:
    `/` for the React UI, `/api/` for FastAPI, and `/docs-site/` for the
    documentation site. These internal targets are not the URLs given to users.

!!! warning "Restart behavior"

    Application containers use bounded `on-failure:5` restart policies. This is
    intentional: failed frontend builds, API imports, or Celery startup errors
    should surface quickly instead of restarting indefinitely and creating Docker
    network churn. Fix the underlying error, then start the service again.

Admin-controlled runtime behavior lives in the `app_controls` collection. These settings are for safe behavior toggles and retention policy, not secrets.

!!! warning "Do not move secrets into MongoDB"

    Admin controls are convenient, but they are not a replacement for environment configuration or a secret manager. Credentials, private keys, LDAP bind secrets, and database URLs must stay outside normal admin-editable documents.

## 5. Collection Mapping

Collection names are loaded from `api/config/coyote3_collections.toml`. Application code should refer to repository attributes and configured collection handles, not hardcoded collection names.

The mapping path is:

```text
api/config/coyote3_collections.toml
  -> runtime config
  -> Mongo adapter
  -> repositories
  -> application services
  -> API routes and Celery tasks
```

This makes center-specific collection naming possible without weakening the application contracts.

!!! tip "When adding a collection"

    Add the collection name to the TOML mapping, add or update the Pydantic contract, register the repository or service boundary, then expose it through a route only if the UI or integration needs it.

## 6. Document Contracts

MongoDB documents are validated through Pydantic models under `api/contracts/schemas/`.

| Domain | Typical Contracts |
| --- | --- |
| Samples | sample, report, sample comment |
| DNA | SNV, CNV, translocation, biomarker, coverage, reported finding |
| RNA | fusion, expression, RNA classification, RNA QC |
| Assay | ASP, ASPC, ISGL, blacklist, assay mappings |
| Governance | user, role, permission |
| Reference | annotation, knowledgebase, VEP metadata |
| Operations | app controls, audit events, notifications |

The rule is simple: if a document is persisted by normal application behavior, it needs a contract.

!!! caution "Schema changes"

    Schema changes in Coyote3 are clinical workflow changes. Review biological meaning, ingest behavior, report reconstruction, query ergonomics, migration path, and UI impact before applying them.

## 7. Clinical Configuration

Clinical behavior is driven by ASP, ASPC, and ISGL documents.

### ASP: Assay Definition

An ASP describes the physical or analytical assay:

- assay identifier
- assay family, group, and category
- platform and read mode
- expected and required file keys
- covered genes and germline genes
- assay metadata used by catalog and review workflows

ASP IDs are stable business identifiers and must be unique.

### ASPC: Assay Configuration

An ASPC describes the digital rulebook for an assay context:

- assay ID
- profile/environment
- subpanel or `base`
- analysis types
- SNV, CNV, fusion, coverage, and reporting filters
- report sections and reporting behavior

When a sample is opened or reset, the default filters come from the matching ASPC.

!!! info "ASPC resolution"

    The effective ASPC is selected by assay, profile, and subpanel. If a subpanel-specific configuration is not present, the base configuration is used when clinically valid.

### ISGL: In-Silico Gene List

An ISGL defines curated gene content used by filters and assay catalog views. Canonical list types are:

- `snv`
- `cnv`
- `fusion`
- `expression`
- `pgx`
- `adhoc_snv`
- `adhoc_cnv`
- `adhoc_fusion`
- `adhoc_expression`
- `adhoc_pgx`

Ad-hoc list types are shown separately from curated list types. The UI should not mix these modes in the same selector.

## 8. Sample Ingest

Sample ingest starts from a sample manifest and attached analysis files. A watched folder can be scanned by Celery, or an ingest can be requested explicitly through an internal API route.

The ingest flow is:

```text
manifest
  -> normalize YAML values, including null and "null"
  -> resolve assay file policy from ASP
  -> validate required files
  -> resolve default ASPC
  -> build sample document with files and filter defaults
  -> parse source files
  -> write dependent documents
  -> update ingest status
  -> rename manifest to .done or failure suffix
  -> emit audit events
```

The sample document stores sample identity, paired/single-sample state, assay context, pipeline details, normalized file references, current filters, default ASPC context, biomarker summaries, data counts, ingest state, and timestamps.

!!! warning "Filesystem reality"

    A stored file path says what was ingested or referenced. It does not prove the file still exists on disk. File availability checks should be explicit and current when needed.

## 9. Sample UI

The sample page is ASPC-aware. It should display only the analysis tabs enabled for that sample context.

Typical tabs include:

- Overview
- Small Variants
- CNVs
- Fusions
- Translocations
- Coverage
- Reports

The overview page shows sample settings, case/control identity, files and QC information, biomarkers, selected gene lists, ad-hoc gene settings, and analysis/report status. It should not show raw JSON payloads in normal clinical workflows.

!!! tip "Reviewer orientation"

    The sample header should always make the sample name, assay, profile, status, and relevant biomarkers visible. Reviewers should not need to open raw payloads to understand the sample context.

## 10. Variant And Finding Review

Finding tables support search, export, sorting, filtering, and clinically relevant actions. Tables should use compact rows, readable headers, and stable column behavior.

Small variant rows commonly include selection state, status indicators, gene, HGVS, exon/intron, type, indel size, consequence, population frequency, tier, chromosome coordinate, flags, case VAF/depth, control VAF/depth when paired, and a detail link.

Action buttons should be context-specific. For example, small variants support FP, blacklist, ignore, report, classify, and detail navigation where relevant. Actions should update the current UI state and emit notifications and audit events.

!!! caution "Bulk actions"

    Bulk actions can change clinical review state for multiple findings. The UI must confirm the action, state the sample/finding context, and refresh affected rows after success.

## 11. Badges, Flags, Consequences, And Tiers

Flags are shown as individual badges. Metadata comes from `api/data/filter_flag_metadata.yaml`, which lets centers configure labels and explanations without changing React code.

Recommended severity behavior:

| Category | Meaning | UI Treatment |
| --- | --- | --- |
| PASS | Passed configured filter | Green |
| WARN | Review warning | Amber |
| FAIL | Failed filter | Red |
| PON | Panel-of-normal evidence | Amber or center-configured |
| GERMLINE | Germline risk/evidence | Indigo or center-configured |

VEP consequence display should use VEP metadata. The UI label may be short, but the tooltip should explain the underlying consequence and impact. Impact color should follow biological severity: high is red, moderate is amber, low is green, and modifier is neutral.

!!! info "Metadata-driven labels"

    Display labels and tooltips should come from metadata wherever possible. That keeps center configuration and VEP-version-specific meaning out of hardcoded UI strings.

## 12. Filters And Gene Lists

Filters are domain-specific. SNV filters should not be shown as CNV filters, and CNV lists should not be mixed with SNV lists.

Filter state is grouped by analysis domain:

```text
filters.snv
filters.cnv
filters.fusion
filters.coverage
filters.reporting
```

When a reviewer changes a filter, the UI updates local form state, the API re-queries the relevant domain, row counts and report preview state update, and saving filters persists the correct domain filter blob on the sample.

!!! warning "Filter/report relationship"

    Report preview must use the same effective filters the reviewer sees in the table. A mismatch between displayed rows and report rows is a clinical safety issue.

## 13. Coverage

Coverage views show gene-level and probe/exon-level coverage. Clicking a gene should open a detailed view with gene context, target/probe placement, exon information, and coverage measurements.

Coverage thresholds come from ASPC and sample filter state:

- warning coverage threshold
- error coverage threshold
- coverage data availability
- gene/probe rows

!!! tip "Coverage review"

    Coverage review is not only a plot. It must preserve enough gene, exon, and probe context for a reviewer to understand what region is under-covered and why it matters clinically.

## 14. Biomarkers

Biomarkers are shown in the sample header and overview when present. Examples include MSI, HRD, TMB, and assay-specific markers.

The UI should avoid empty separators or undefined values. If a biomarker is absent, hide the badge or show a deliberate "not available" state in the overview.

!!! info "Biomarker display"

    Biomarkers summarize molecular context and should be visible without opening raw payloads. The exact display should depend on available parsed biomarker documents, not string concatenation.

## 15. Comments And Annotations

Sample-level comments are stored in `sample_comments`. Detail pages can show sample-specific and global finding annotations separately.

Comment behavior:

- Markdown is supported.
- Sample comments may use live preview.
- Detail-page comments use explicit preview/edit mode to conserve space.
- Clicking an existing comment can copy it into the editor as a draft when enabled.
- Hide/unhide operations are auditable.

!!! caution "Global annotations"

    Global annotations apply beyond a single sample context. The UI must make this explicit before save so a reviewer does not accidentally publish a sample-specific note globally.

## 16. Reporting

Report preview is temporary until saved. The preview is generated from current sample state, ASPC report configuration, enabled analysis types, and effective filters.

Saving a report persists:

- report document
- report number or status where applicable
- rendered report HTML and optional PDF artifact
- reported variants/findings snapshot
- filter snapshot
- ASPC context
- author and timestamps
- audit event

After saving, later searches can answer which samples reported a gene, which variants were reported, which class or tier was used, which report configuration was active, which filters produced the reportable set, and whether similar findings appear in other samples.

!!! warning "Report reconstruction"

    A saved report should remain understandable even if ASPC defaults, ISGL contents, annotation text, or sample filters change later.

## 17. Assay Catalog And Matrix

The assay catalog combines database-backed assay resources with catalog metadata. YAML is used only for catalog presentation fields that are better maintained as curated descriptive content, such as assay descriptions, turnaround time, sample types, catalog grouping, display labels, and matrix presentation metadata.

Clinical behavior remains database-driven through ASP, ASPC, and ISGL.

The matrix should support paged gene rows, search for a specific gene, filters for modality/section/gene list, stable grouped headers, tick marks for covered genes, dash marks for non-covered cells, and no vertical scroll inside the table for normal page sizes.

!!! tip "Catalog performance"

    Large matrix views should page gene rows by default. Fetching all genes for every catalog column is expensive and unnecessary unless the user exports or searches broadly.

## 18. Search

Variant search uses annotation and reported-finding data to locate relevant variants across samples. Search should support gene symbol and variant fields such as HGVSc and HGVSp when those are mapped in the annotation collection.

Search output should include gene, variant/HGVS, class/tier, merged class text where available, assay-wise counts, sample/report links, and compact evidence text.

Knowledgebase markers are rendered in compact row-status badges, not as extra
wide table columns and not beside the gene text in dense variant tables. OncoKB
uses `OKB` for public cancer-gene membership and `Rx` for historical local
actionability-style evidence. ClinPGx uses `PGx` for pharmacogenomics gene
membership from `clinpgx_genes_public`. This keeps dense tables readable while
still surfacing curated cancer-gene and PGx context.

Variant detail pages consolidate all knowledgebase evidence into one
**Knowledge Bases** card. CIViC, BRCA Exchange, TP53/IARC, local OncoKB cache,
historical actionable OncoKB evidence, OncoKB public API lookup, and ClinPGx
local/API context are shown as collapsible sections inside that card. Sections
default to a compact state unless they contain the immediate summary a reviewer
needs. This prevents pharmacogenomics or public API metadata from crowding the
main variant decision area while keeping the evidence one click away.

OncoKB public cancer-gene context is populated into
`oncokb_cancer_genes_public` from OncoKB `/utils/cancerGeneList`. Gene-level
public summaries, background text, settings, and public level metadata are
prefilled into `oncokb_genes_public` from OncoKB
`/utils/allCuratedGenes?includeEvidence=true`.

ClinPGx public gene context is populated into `clinpgx_genes_public` from the
official ClinPGx `genes.tsv` export. The cache stores PharmGKB/ClinPGx IDs,
HGNC IDs, NCBI Gene IDs, Ensembl IDs, aliases, VIP status, variant-annotation
availability, CPIC dosing guideline availability, cross-references, and genome
coordinates. Rich API-derived ClinPGx summaries are fetched on demand from the
variant detail page and are not stored as a separate MongoDB collection.

!!! info "Search intent"

    Search is not just a table lookup. It helps reviewers understand recurrence, prior classification, reporting history, and assay context across samples.

!!! warning "Knowledgebase reproducibility"

    `oncokb_cancer_genes_public` and `oncokb_genes_public` are seeded by
    explicit operational actions from the public OncoKB cancer-gene and
    all-curated-gene endpoints. VCF ingest normalizes symbols through HGNC IDs
    and previous/alias symbols, then batches missing public OncoKB lookups into
    `oncokb_public` only for cached OncoKB genes. The preferred small-variant
    query is HGVSg through `POST /annotate/mutations/byHGVSg`, using the exact
    OncoKB-facing genomic format `chrom:g.positionRef>Alt`, for example
    `17:g.76736896T>C`. VEP-provided `HGVSg` is normalized from `chr17:g...` or
    RefSeq chromosome accessions into this chromosome-label format. If VEP does
    not provide HGVSg, Coyote3 constructs HGVSg only for simple SNVs. Complex
    indels are not hand-normalized from VCF fields; they use VEP HGVSg when
    present or fall back to `POST /annotate/mutations/byProteinChange`.

    Dense tables read the public cancer-gene cache for OncoKB markers. Variant
    detail pages can fetch public OncoKB API evidence on demand from
    `https://public.api.oncokb.org/api/v1`. The detail view renders a compact
    subset: query, gene, alteration, data version, gene/variant existence,
    oncogenic state, mutation effect, diagnostic/prognostic levels, and
    gene/variant summaries. Public OncoKB access does not require a commercial
    license or token, but therapeutic data is excluded. Historical local
    `oncokb_actionable` rows contain treatment/actionability-style fields and
    are displayed as a separate actionable-evidence section inside the same
    Knowledge Bases card.

    Dense tables read `clinpgx_genes_public` for PGx markers. Variant detail
    pages can fetch public ClinPGx API context on demand from
    `https://api.clinpgx.org/v1`. Identifier-based lookup
    `/data/gene/{id}` is preferred when the local cache has a ClinPGx/PharmGKB
    accession; symbol query `/data/gene?symbol={symbol}&view=max` is the
    fallback. The public API summary also uses `/data/guidelineAnnotation`,
    `/data/label`, `/data/variantAnnotation`, and
    `/report/connectedObjects/{id}/{type}` for chemicals and pathways. The
    normalized result is returned to the ClinPGx section of the Knowledge Bases
    card for the current review session and is not persisted. ClinPGx asks
    clients to limit requests to 2 per second, so Coyote3 does not call the
    external API per table row.

!!! info "DNA transcript selection"

    DNA ingest selects `selected_CSQ` using clinical transcript priority:
    HGNC MANE Plus Clinical first, then HGNC MANE Select, then the center
    canonical map after HGNC-symbol normalization, VEP canonical,
    protein-coding transcript, and finally the first available transcript.
    HGNC resolution uses HGNC ID first, then approved symbol, previous symbol,
    and alias symbol. If VEP uses a previous or alias gene symbol, HGNC metadata
    normalizes the displayed symbol to the approved symbol and stores the raw VEP
    value in `VEP_SYMBOL` only when it differs.

## 19. Access Control

Coyote3 uses role-driven access control with scoped checks. Users can have multiple roles. The UI may show the highest role in compact places, but profile and user-management screens should show all assigned roles.

User scope can include environments/profiles, assays, and assay groups. Permission strings follow `resource:action[:scope]`.

Authentication provider behavior is controlled by `auth_type`, a list of allowed providers. LDAP login uses email. Local login uses username and local password.

!!! warning "No per-user permission overrides"

    Access should be controlled through roles and scopes, not user-specific allow/deny lists. This keeps effective access explainable and auditable.

## 20. Admin Workflows

Admin pages should use forms built from application contracts, not raw JSON editors. List pages should show useful human columns and relative dates, not ObjectId-heavy tables.

Admin areas include users, roles, permissions, ASP, ASPC, ISGL, assay catalog support, application controls, audit events, and notifications.

Clinical configuration resources should preserve reconstruction history. Governance resources such as users, roles, and permissions are updated in place with version metadata and audit events to keep access management operationally simple.

!!! caution "Admin visibility"

    Admin screens can expose powerful changes. Every create, update, retire, delete, or control toggle should show a user-facing notification and write an audit event.

## 21. Application Controls

Application controls are runtime switches and retention settings managed from Admin. They can include enabling/disabling task families, module visibility, audit retention days, notification retention days, disk log retention days, and gzip thresholds for old logs.

Disabling a Celery task family prevents future task executions from doing work or allows them to return early. It does not resize the worker process pool or release worker threads that are already allocated by the running worker container.

Dashboard and operational plots use the shared React plotting layer. Plot panels
support PNG, SVG, and CSV export, and all charts must provide useful empty
states. Statistical plots should use shared chart components. Genomic track
views may use specialized SVG when needed but should preserve the same theme and
export conventions where practical.

!!! tip "Capacity management"

    Use task controls to stop work. Use worker scaling or container/process configuration to change capacity.

## 22. Audit, Notifications, And Logs

Audit events are durable records. Notifications are user-facing messages. Logs are operational diagnostics. They overlap, but they are not interchangeable.

| System | Purpose | Retention |
| --- | --- | --- |
| Audit events | Compliance and reconstruction | Mongo TTL plus retention task |
| Notifications | User-visible action feedback/history | App control retention |
| Runtime logs | Debugging and operations | File/stdout retention policy |

Audit metadata must be bounded and redacted. Do not store secrets, full tokens, or unnecessary patient-identifying payloads in audit metadata.

!!! warning "Audit payload hygiene"

    Audit events should explain what happened, who did it, which resource was affected, and whether it succeeded. They should not become raw request dumps.

## 23. Operations

Production operation depends on healthy API, frontend, worker, beat, Redis, and Mongo services; current seed/configuration data; valid mounted ingest directories; working audit indexes and TTL indexes; log rotation and retention; backup and restore procedures; and deployment-specific secrets outside source control.

Nightly maintenance can clean expired audit events, clean old notifications, gzip old log files, delete logs beyond retention, and emit audit records for maintenance outcomes.

!!! caution "Backups before migration"

    Any clinical schema migration should be preceded by a MongoDB backup and followed by validation queries. Migration scripts should not be committed with center sample data or secrets.

## 24. Developer Workflow

Developers should preserve clean domain boundaries:

- API routes translate HTTP into service calls.
- Application services own use-case orchestration.
- Domain helpers own clinical computation and formatting rules.
- Repositories own database access.
- Contracts own document and response shapes.
- React components render typed API data and user interaction.

Avoid compatibility shims, template-era UI patterns, raw Mongo result exposure, and duplicated business logic in React.

!!! tip "Adding functionality"

    Start by identifying the clinical domain and data contract. Add the backend contract and service behavior first, then connect the UI. This avoids building screens that rely on accidental raw payload shapes.

## 25. Documentation Rules

Documentation should explain workflow, rule, and consequence. It should not only list endpoints or files.

Use admonitions consistently:

!!! info "Use info for context"

    Use `info` when explaining source of truth, ownership, or architecture context.

!!! tip "Use tip for practical guidance"

    Use `tip` for reviewer habits, operator shortcuts, or developer workflow advice.

!!! warning "Use warning for preventable errors"

    Use `warning` for unsafe or misleading behavior that could cause bad clinical, operational, or security outcomes.

!!! caution "Use caution for high-impact changes"

    Use `caution` for migrations, reporting reconstruction, destructive operations, and changes that require review or backup.

## 26. Quality And Governance Principles

Coyote3 is designed as a clinical genomics platform, so product behavior,
developer workflow, and operational controls are expected to preserve
interpretability, auditability, and reproducibility. The principles below define
the default quality model for clinical and administrative workflows.

| Area | Principle | Expected outcome |
| --- | --- | --- |
| Clinical UI | Clinical and administrative pages present interpreted fields, forms, and action states rather than raw backend payloads. Diagnostic payload inspection belongs in explicit debug or operational tooling. | Reviewers see concise clinical context without needing to understand MongoDB document shape. |
| Data contracts | Writes pass through Pydantic contracts and service-layer validation before reaching repositories. | Stored documents remain predictable, typed, and compatible with reporting and audit reconstruction. |
| Collection access | Domain services use configured collection mappings and repository boundaries. | Collection renames and center-specific deployments can be managed through configuration rather than code edits across the domain layer. |
| Analysis semantics | SNV, CNV, fusion, expression, PGX, and coverage data keep separate filters, gene-list semantics, and reporting rules. | A configuration change in one analysis domain cannot silently alter another domain's interpretation behavior. |
| Reporting | Saved reports preserve the filter snapshot, ASPC context, report template context, selected findings, and rendered output required for later reconstruction. | A finalized report can be explained and reproduced from persisted application state. |
| Permissions | Administrative mutation routes are protected by explicit authorization checks and audited outcomes. | Configuration, identity, and role changes are traceable and limited to authorized users. |
| Secrets and retention | Credentials, tokens, LDAP bind secrets, and private keys remain outside app controls, audit events, and documentation. | Operational records stay useful without becoming a secret-storage risk. |
| Failure visibility | Ingest, report generation, external knowledgebase lookups, and write actions surface meaningful success or failure states. | Users and operators can distinguish an absent result from a failed workflow. |
| UI state | User actions refresh persisted state or clearly indicate pending work. | The interface reflects the backend source of truth after clinical or administrative changes. |
| Architecture | Temporary migration helpers are retired after the target contract is established. Long-term behavior lives in explicit services, contracts, repositories, and UI components. | The codebase remains maintainable as the platform evolves beyond legacy workflows. |

!!! info "Clinical engineering posture"

    Code, UI, schemas, and documentation are reviewed for biological meaning,
    reporting consequences, auditability, and operational safety. A technically
    valid change is not complete until its clinical data flow and reconstruction
    behavior are clear.
