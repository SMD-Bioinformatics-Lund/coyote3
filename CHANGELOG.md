# Changelog

## v4.0.0 - Unreleased

This release entry describes the complete application replacement and every supported
workflow introduced after the `master` branch baseline, rather than only the latest
incremental changes on the development branch.

### Added

- Added explicit MongoDB index `status`, `plan`, `apply`, and guarded
  single-index retirement operations. API startup now performs read-only index
  verification; index creation and retirement require an operator command.
- Rebuilt the application around a FastAPI backend and a typed React/Vite frontend, with stable API contracts for clinical, administrative, public, knowledgebase, and operational workflows.
- Added complete DNA and RNA sample workspaces with ASPC-driven analysis tabs, independent somatic and germline SNV filtering, CNV profile review, coverage, fusions, translocations, biomarkers, comments, and report workflows.
- Added a YAML-driven clinical reporting rules engine with deterministic rule selection, validated template helpers, separate somatic and germline report sections, temporary report snapshots, HTML/PDF output, and persisted reported findings.
- Added version-aware VEP annotation storage, HGNC-based gene normalization, configurable RefSeq-first transcript selection, MANE and canonical transcript indicators, and normalized annotation identities for genomic, HGVS, CNV, and fusion findings.
- Added public OncoKB and ClinPGx integrations, local gene markers for dense tables, and expandable knowledgebase evidence in finding detail views.
- Added database-backed RBAC with locked application permission policies, built-in operational roles, delegated administration, user-specific notifications, password-reset requests, and targeted or broadcast notifications.
- Added application module controls, consolidated ingest-task controls, observed Celery runtime state, retention policies, Mongo backup/restore tooling, and maintenance operations.
- Added first-deployment bootstrap catalogs for permissions, roles, demo ASP/ASPC/ISGL records, and compressed HGNC/VEP reference snapshots. Bootstrap imports are collection-aware and do not overwrite non-empty collections.
- Added public assay catalog and gene-coverage matrix views, richer operational dashboards, panel capability plots, application About and Contact pages, and center-configurable contact information.
- Added centralized semantic UI theming, responsive data tables, server-side multi-column sorting, query caching and invalidation, compact clinical badges, accessible tooltips, confirmation dialogs, and route-state restoration.
- Added a global, reduced-motion-aware back-to-top control for application pages whose content exceeds 110% of the visible page height.
- Added centralized OpenAPI visibility policy so supported client contracts remain documented while health and internal integration routes stay callable but schema-hidden.
- Added atomic watch-folder and manually queued ingestion through consolidated Celery task controls, declared-file validation, failed-manifest handling, ingest audit events, and observed worker/queue state.
- Added complete administrative workspaces for users, roles, permission policies, ASPs, ASPCs, ISGLs, samples, notifications, route contracts, ingestion, application controls, and retention settings.
- Added API session-cookie and bearer-token authentication, local and LDAP provider resolution, password reset and invitation flows, rate limiting, mutation auditing, and reverse-proxy-aware OpenAPI authorization.
- Added Mongo repository adapters and indexes for clinical findings, annotations, configuration history, reports, audit events, notifications, external knowledgebases, VEP transcripts, and runtime controls.
- Added synthetic demo manifests and fixtures, deterministic center bootstrap bundles, browser-level workflow tests, and real-database release validation entry points.

### Changed

- Consolidated Swedish tier-summary vocabulary across clinical report rendering
  and annotation suggestions, removed the unused legacy report utility, and
  extracted ingest file-policy and admin schema-catalog responsibilities into
  focused modules.
- Standardized ASP, ASPC, ISGL, sample, assay-group, subpanel, environment, analysis-type, and file-key contracts while retaining versioned configuration history for future edits.
- Made ASPCs responsible for available analyses, report sections, intent-specific filters, and base-subpanel fallback behavior. Sample pages now expose only analysis tabs enabled by the resolved ASPC.
- Reworked sample ingestion as an atomic workflow: every declared resource must validate and load successfully before the sample becomes ready; optional resources may be absent only when they are not declared.
- Moved deployment-specific collection names, ingest mappings, contacts, file policies, transcript priorities, and clinical metadata to documented center configuration files. Software-owned vocabularies and repository links remain application constants.
- Changed sample-facing routes to use sample names while retaining finding identifiers where needed for unambiguous detail routes.
- Reorganized API routers into clinical, administrative, public, operations, and knowledgebase packages while keeping public endpoint paths stable.
- Reworked the frontend into route-level bundles and standardized tables, cards, forms, icons, status colors, local-time display, loading overlays, dark mode, and responsive page widths.
- Consolidated synthetic fixtures and demo imports under `demo_data/`; application bootstrap assets now live under `api/config/bootstrap/`.
- Replaced embedded Flask/Jinja pages and direct collection access with versioned Pydantic contracts, application services, repository adapters, FastAPI routers, and typed frontend API envelopes.
- Standardized one externally published reverse-proxy port and `SCRIPT_NAME` prefix for the React UI, public catalog, API documentation, generated OpenAPI schema, and MkDocs site.
- Changed clinical timestamps to remain UTC in storage and render in the center-configured local time zone in the UI.
- Changed report templates to preserve the clinical PDF layout while report composition, rule evaluation, filter snapshots, and persisted artifacts use the new application services.
- Changed permission and role bootstrap data into application-owned catalogs that can be synchronized without deleting center-defined roles or policies.

### Fixed

- Corrected global sorting across paginated findings, filter-triggered refreshes, cached-query invalidation after curation actions, and preservation of table state when returning from detail pages.
- Corrected consequence filtering, synonymous exclusion, tiered-variant lookup, annotation text matching, caller and flag presentation, and alternate-transcript metadata.
- Corrected CNV/translocation/fusion ingestion and presentation, control-sample column visibility, CNV profile sizing and rotation, and coverage availability.
- Corrected ASPC base fallback, normalized configuration lookup, dashboard counts, sample gene-list summaries, report introductions, and database-version extraction from VCF headers.
- Corrected authentication-provider startup behavior, local/LDAP account normalization, SCRIPT_NAME routing, reverse-proxy paths, prefixed API/docs routes, and user-facing API error messages.
- Corrected user-specific notification delivery, password-reset escalation to authorized administrators, broadcast targeting, audit-route authorization, and delegated admin field controls.
- Corrected assay catalog pagination and matrix filtering, gene-page enrichment, active gene-list display, matrix header grouping, and panel-only dashboard analytics.
- Corrected report comment drafting, global and sample annotation separation, automatic Tier 3 text, finding action confirmation, and page-specific finding actions.
- Corrected environment and deployment validation so local-only authentication does not require LDAP credentials, current token salts are mandatory, and ingest file checks use the shared center vocabulary.

### Removed

- Removed the Flask application, WSGI launcher, Jinja page layer, Flask blueprints, legacy `coyote/` package, and Flask-era runtime guidance.
- Removed the legacy schema JSON files, retired install scripts, ad hoc reported-variant backfill, historical gene-database builder, and tracked migration implementations. The ignored `migration_scripts/` workspace now contains only its policy README.
- Removed the split Tailwind runtime and legacy template CSS pipeline. Production now serves one prebuilt Vite application; development uses the Vite watcher without container restart loops.
- Removed ObjectId-based sample navigation, legacy sample/configuration aliases, duplicate database-version keys, old transcript-canonical collection behavior, and compatibility query fallbacks.
- Removed the broken Compose `first-run` service that referenced a nonexistent script. `scripts/center_first_run.sh` is the single documented first-deployment orchestrator.
- Removed internal integration, health, and maintenance plumbing from the supported OpenAPI client contract while retaining secured runtime endpoints.

### Security and quality

- Added staged and full-tree checks for secrets, private environment files, clinical identifiers, personal identity numbers, and non-synthetic test metadata.
- Added collection-contract generation and integrity checks, assay consistency validation, ingest-manifest validation, shell quality checks, strict documentation builds, backend family coverage gates, frontend unit coverage, and Playwright route/workflow tests.
- Expanded API and frontend negative-path tests for authentication, permissions, application modules, ingestion, clinical queries, report generation, notifications, admin forms, and empty/error states.
- Reduced GitHub Actions usage with changed-scope validation, draft-pull-request deferral, superseded-run cancellation, cached Playwright browsers, one-pass backend coverage, bounded artifact retention, and a manually dispatched composed-stack acceptance check.

### Documentation

- Replaced legacy handbook material with task-oriented user, developer, administrator, deployment, API, security, data-contract, testing, and troubleshooting documentation.
- Added screenshots and architecture diagrams for bootstrap data flow, configuration authority, clinical review, sample-to-report processing, and deployment topology.
- Documented every supported sample manifest field, configuration key, clinical reporting rule key/operator/helper, transcript-selection stage, filtering exception, collection relationship, and first-deployment requirement.
- Added an audited repository-script reference identifying automated callers, manual operator commands, internal helpers, current architecture dependencies, and safe retirement criteria.

## v3.1.23
- Added typed DNA CSV export row models (`SNV`/`CNV`) and API-backed export context endpoints for stable, contract-driven CSV formatting.
- Switched DNA list-page CSV downloads to backend-generated files via Flask proxy routes instead of DOM-derived table exports.
- Extended backend-generated CSV downloads to translocations with typed export rows and API/UI wiring.

## v3.1.22
- Variant search gene mode will match exact gene search string, not substring match.
- Added CNV to the Solid CRC avaiable analysis options in the assay catalog.

## v3.1.21
- Fixed HGVS display/toggle behavior across DNA variant list, tiered search, and reported variants views (unique row IDs, stacked HGVS lines, and no blank indent when only one HGVS value exists).
- Replaced historical custom width utility usage (`max-w-15c` style) with Tailwind arbitrary values where used.
- Removed deprecated DNA gene view routes/templates (`/gene_simple/<gene_name>`, `/gene/<gene_name>`).

## v3.1.20
- Updated handbook structure and docs routing to use main/user/developer index pages, standardized ASP/ASPC/ISGL naming, and added DNA/RNA/Sample/Admin flow diagrams.

## v3.1.19
- Fixed Tailwind v4 dynamic class generation gaps by expanding template scan coverage (`.jinja/.jinja2`) and explicit inline source classes for semantic/admin color tokens.
- Added Tailwind v4 border base layer and stabilized modal/button styling with Tailwind-safe static class mapping.
- Restored same-line live validation feedback in schema creation editor (inline line highlight + inline error widget).
- Updated admin audit logs view to sort entries by parsed log timestamp in descending order (latest first).
- Fixed subpath static asset behavior for containerized deployment under `SCRIPT_NAME` (e.g., `/coyote3`) by adding prefix-aware WSGI middleware and normalizing compose env formatting.
- Fixed Docker Tailwind build stage to include version-sync script inputs required during npm postinstall.

## v3.1.18
- Migrated Tailwind to npm-based single-file build flow using Tailwind v4 CLI.
- Removed split `custom.tailwind.css` and switched to config-driven Tailwind generation (no manual per-shade utility definitions).
- Updated Docker and Compose for CSS build during image build (prod/dev) and continuous CSS watch service in development.
- Updated dev container flow to build/watch Tailwind only in the dedicated dev Tailwind service, avoiding npm install dependency during `coyote3_dev_app` image build.
- Added version-aware compose workflow:
  - `docker-compose*.yml` now use `COYOTE3_VERSION` image tags instead of hardcoded app versions.
  - Added `scripts/compose-with-version.sh` to export version from `api/version.py` and run `docker compose`.
- Added npm package version sync from Python version source:
  - Added `scripts/sync-package-version.js`.
  - Wired package version sync from `api/version.py`.
- Reworked installation/deployment documentation to production-first, step-by-step runbooks in README and handbook.

## v3.1.17
- Added `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md` and `SECURITY.md`

## v3.1.16
- Reworked product documentation into a complete user/developer handbook under `docs/handbook`.
- Updated in-app documentation routing so handbook content is served under `/handbook`, including markdown-rendered handbook pages.
- Updated README documentation section with current handbook routes and MkDocs ReadTheDocs build instructions.

## v3.1.15
- Removed unused block of code which is causing errors in the tiered variants search.

## v3.1.14
- Fixed tiered variants tier color, and added action button

## v3.1.13
- Fixed IGV links for snv and cnvs, now the IGV links are not hardcoded in the templates

## v3.1.12
- removed huge css files from the repo and fetched from the cdn instead

## v3.1.11
- removed a commented line from the report layout css (`#border:1px solid #aaa;`)

## v3.1.10
- Added documentation pages (About, Changelog, License) and exposed basic version and build information in the UI.

## v3.1.9- Kept the old Gens URI until the complete migration.

## v3.1.8- Added FL, DLBCL and Breast Cancer analysis/Genelists in the assay catalog

## v3.1.7- Add New GENS Link

## v3.1.6- Introduced a dedicated `reported_variants` collection to track tiered variants per report and sample.
- Linked variant tiers to the reports in which they are clinically reported.
- Added `TieredVariantSearchForm` and new `/search/tiered_variants` view to search annotations by gene, variant, transcript, author, assay, and subpanel.
- Connected annotation search results to samples and reports via the `reported_variants` collection, including per-sample report references.
- Added tier statistics sidebar to the tiered variant search page.
- Improved HGVS protein normalization to support complex clinical variants and enhanced backfill reliability using JSONL-based dry-run and bulk insert workflows.
- Fixed gene links to correctly deep-link into tiered variant search with proper query parameters and assay filtering.

## v3.1.5- Added CNV aftefct column from the historical coyote

## v3.1.4- Adjusted sample search behavior to remove the time limit for user-initiated searches, while keeping a default 90-day time filter for reported samples.
- Changed the sample profile filter to hide non-production samples by default, with a toggle to show all samples.
- Removed Exon/Intron Info from the variant table in the report.
- Fix: Replaced naive datetime usage with a centralized `utc_now()` helper to ensure all newly stored timestamps are timezone-aware and consistently recorded in UTC.
- Fix: removed excess whitespace in DNA report variant comments caused by default paragraph margins in report tables.
- Fix: prevent hidden genelist form fields from rendering as stray boxes in generated report PDFs.
- Fix: Prevent previously tiered variants marked as false positives from appearing in the “Suggest” summary text (they were only removable by marking as irrelevant), while still keeping them out of the final summary table.
- Fix: Reduced the default font size of markdown headings inside the summary editor (EasyMDE/CodeMirror) so section headers appear more compact while typing, matching the final report style.

## v3.1.3- Fixed missing ISGL routes in production by standardizing Flask blueprint route definitions.

## v3.1.2- Admin: Fixed JSON sample editor to safely serialize and restore MongoDB ObjectIds during full document updates.

## v3.1.1- Reports: HTML reports now use compact UTC timestamps in filenames to avoid collisions on re-runs.
- New format <TUMOR_NAME>_<TUMOR_CLARITY_ID>-<NORMAL_NAME>_<NORMAL_CLARITY_ID>.<YYDDMMHHSS>.html for tumor-normal analysis.  <TUMOR_NAME>_<TUMOR_CLARITY_ID>.<YYDDMMHHSS>.html for tumor only analysis.

## v3.1.0
### Added
- Sample landing page to view sample related meta data, case/control overview, files & QC, gene filters, variant filters, analysis data counts, reports, comments, etc.
- Sample landing (settings/edit) page will now show the list of files associated with the sample and if they exist on the drive.
- Added support for AdHoc Gene lists
- Added a key 'adhoc and is_public' to indicate if the gene list is adhoc and public in the isgl schema.
- Added a public facing assay catalog page to view assay related metadata, gene lists, and configurations. Catalog presentation is controlled by center configuration together with ASP and ASPC records.
- Updated dashboard stats to have total counts of variants instead of unique counts to reduce the loading time.
- Report name format uses `Sample.name` instead of `Sample.case_id`, causing reports to be created with the same `case_id` but different `sample.name`.
- Public “Assay Coverage Matrix” page with full modality → category → genelist grouping, ASP-aware gene override, and placeholder column support for empty services.
- Added highlight feature for KMT2A and KMT2D in the CNV  table (currently hardcoded).
- Added a sample Edit page for admin views
- Fixed assay group toggle behavior in ISGL edit page, ensuring correct initial display and proper group–assay syncing.
- Enhanced Create/Edit User pages with correct RBAC permission precedence, conflict detection, and a unified color-coded highlight system.
- Added new GitHub bug and support issue templates with auto-assignment to Project 22.
- Improved markdown rendering for summary comments—headings, line breaks, and formatting now display correctly using the enhanced format_comment filter.
- Updated report terminology: replaced “variant” with “mutation” in summary text, variant summary table, detailed table headers, and Tier 3 naming.


## v3.0.9
### BugFix #119
- Fixed carry-over of protein changes between variants.
  The protein_changes list is now reinitialized inside the variant processing loop, ensuring each variant has its own independent protein change data.
  Previously, variants without explicit protein changes could inherit those from prior variants, causing incorrect annotations.
- Added a repository collection-mapping configuration for easier deployment management.

## v3.0.8
### HotFix #117
- Fixed handling of long indel in reports: indels longer than 20 characters are no longer truncated in the UI — table cells show the indel length (e.g., "45 bp") instead of a cut-off sequence. For very long indels (>30 characters) the column header is also updated to include the indel length to improve readability.

## v3.0.7
### BugFix
- Fixed full gene view to get all the tiered variants along with the samples. #115

## v3.0.6- SNV filter step size has been changed to 0.001, now user can go upto 0.1% at the lowest.

## v3.0.5- Download of csv file from Coyot3 #109
- Sort Variants in Report Table by Tier and VAF #107
### BugFix
- Filter button increments incorrectly #102

## v3.0.4
### Typo
- Corrected a typo in autogenerated tier3-comment function

## v3.0.3
### Report Filename Update
- Report should follow a naming structure of <CASE_ID>_<CLARITY_CASE_ID>-<CONTROL_ID>_<CLARITY_CONTROL_ID>.<REPORT_NUM>.html for paired samples and <CASE_ID>_<CLARITY_CASE_ID>.<REPORT_NUM>.html for unpaired samples.
- static files cleanup -> css, icons, images
- replaced groups with assays where needed

## v3.0.2
### BugFix
Fixed an IndexError in the variant summary generation logic where an empty germline intersection caused the summary view to crash. Now safely handles cases with no overlapping germline variants.


## v3.0.1
### BugFix
hotfix: report paired status key update - replaced `sample_num` with the correct key `sample.sample_no` to get the number of samples (case/control)

## v3.0.0
### Added
- Initial release.- Initial release.
- User authentication and authorization.
- Admin dashboard for managing data.
- Responsive UI with modern design.
- Real-time notifications.
- Comprehensive logging and error handling.
- New database schema with optimized queries.
- RBAC (Role-Based Access Control) for user permissions.
- Configurable settings for assays, configs, genelists, etc via UI.
