# Changelog

## v4.0.0

- Added collection-level creator/updater attribution, preserved original creators
  across edits, and made system-installed configuration read-only in administration
  workflows. Added an explicit, dry-run-first historical attribution backfill.

- Add a related-data migration stage and collection selectors for CNVs,
  translocations, biomarkers, v2 fusions, v3 D4 coverage and embedded RNA results.
  Allow these to migrate after samples without processing unrelated variants or QC.

- Require installed HGNC/VEP metadata before shared VEP preparation. Add per-assay
  findings, sample and final snapshot migration stages, retain original sample
  ObjectIds, and split historical tumwgs samples into hema and solid ASPs.

- Select annotation sources explicitly: hematology from v3, all other groups from v2.
  Block sample conversion when a saved report references an excluded annotation.

- Apply operator-supplied historical annotation assay/ASP and solid-diagnosis mappings
  during v2/v3 migration, lowercase scope identifiers, and validate installed target scopes.

- Build shared historical `anno_vep` migration bundles from v2/v3 variant evidence,
  resolve annotations against exact transcripts, and add all-sample batch conversion
  with embedded RNA results and per-sample reports. Document MongoDB apply commands
  separately from offline preparation and local lookup indexes.

- Correct offline v2/v3 migration persistence for blacklist assay scopes and reviewed
  annotation diagnoses. Verify migrated blacklist entries through the runtime repository.

- Align the modern report's center logo to the right edge with the center name below
  it in HTML and PDF. Preserve clinical content and the existing report format.
- Consolidate deployment acceptance into one checklist, remove the pending-development
  maintenance page, and correct source-build versus verified-artifact instructions.

Version 4 replaces the Flask application with FastAPI and React while preserving
its supported clinical workflows.

### Application and packages

- Remove duplicate Python HTTP login helpers and the unused API authentication
  re-export. Publish Python client 2.0 with one validated sync/async client flow;
  move operational CLIs to that flow and preserve explicit token-output controls.
- Rebuild distribution package trees before wheel creation so deleted modules cannot
  reappear from stale setuptools output. Verify the installed client independently.
- Remove obsolete flat fusion presentation adapters; consume the current gene-pair
  and caller-evidence contracts, including zero read counts.
- Remove obsolete response-envelope alternatives from finding, public gene-list,
  knowledgebase, dashboard, audit and contract-catalog pages; align their fixtures
  and the release workflow checker with the current API contracts.

- Added typed DNA and RNA ingestion, analysis, reporting, administration, public
  catalog, and cohort-review workflows.
- Removed the legacy Flask application and its compatibility paths.
- Apply the COYOTE3 Free-Use Source-Available License 1.0 to the application,
  identify Ram Nanduri in module/package notices and retain Apache 2.0 for the
  independent Python client. Preserve the main license's copyright statement.
- Package core and root-level FastAPI modules together with optional `api` and
  `all` dependencies and the installed `coyote3-api` entry point. Move HTTP clients
  into the independent `coyote3-client` distribution with sync/async operations.
  External client imports change from `coyote3.client` to `coyote3_client`.
- Keep deployment catalogs, demo installers, contact/about pages, collection names
  and product assets outside the core namespace. Group domain modules by clinical
  responsibility and reusable authoring contracts under `contracts/authoring/`.
  Document clinical record fields separately from physical storage keys and add
  explicit MongoDB-adapter field bindings.

### Clinical review and reporting

- Compact modern-report metadata and replace empty finding tables with configurable
  per-analysis text. Keep center wording separate from ASPC revisions and preserve
  legacy output and populated finding tables. Capture saved modern-report wording
  in the preview fingerprint so changed messages require another review before save.

- Added versioned data contracts, ASPC-driven filtering, reference annotations,
  MongoDB-backed clinical reporting rules, and immutable report snapshots.
- Add Coyote3/center branding and labeled metadata fields to the modern report,
  with embedded validated SVG logos and print-safe A4 layout. Remove obsolete
  logo files, use the current vector assets throughout, and support dark-theme lettering.
- Add in-place PDF preview to the established report tab and show independently
  installed core SDK and Python HTTP client versions on the About page.
- Extract legacy and modern report HTML/CSS into packaged Jinja layouts and
  modality-specific components. Preserve legacy template identities and clinical
  content; allow registered modern layouts through governed template profiles.
- Add **Try new report** for DNA/RNA with matching temporary HTML/PDF previews and
  local downloads. Preserve established clinical content and saved-report behavior;
  embed styles and bypass report numbering, snapshots and server report-file writes.
- Resolve query policies and clinical reporting rules from current published scopes,
  independently of ASPC revisions. Capture rules used by each report and require
  another preview when publications change before save. Preserve issued reports.
- Add configured SNV flag exclusions for both intents and tumor WGS groups while
  retaining the existing `tumwgs` group. Preserve saved report snapshots.

### Security and audit

- Added database-backed access control, authentication, auditing, notifications,
  background processing, and operational controls.
- Separate expiring operational audit records from retained clinical history;
  enforce collection-scoped MongoDB runtime permissions and insert-only replay.
  Existing deployments require the documented one-time identity role upgrade
  before production installation checks. Add optional hourly checkpoint exports
  to independently retained archival storage.
- Enforce finding ownership and current clinical access for report notifications;
  restrict sample deletion to its explicit permission. Add audit integrity chains,
  durable outboxes/checkpoints and transaction-owned report-file erasure jobs.

### Deployment and maintenance

- Require authenticated, restricted identity connections for installation in every
  environment. Replace anonymous local MongoDB examples with authenticated settings.

- Reject obviously anonymous production identity connections before image builds
  and explain runtime credential, server authorization, and role prerequisites.

- Added container deployment, backup and restore tooling, automated tests,
  and operator and clinical documentation.
- Build the application wheel inside the normal Docker installation, without
  requiring host SDK preparation. Keep tested-wheel verification in the optional
  release Compose overlay and release CI target.
- Make fresh installation create identity, application catalogs, bundled references
  and synthetic starter data by default, with module skip flags and preservation of
  existing data. Later additions/repairs use API authentication, role checks and
  first-login password change handling.
- Separate ingestion and maintenance worker queues, bound activity scans and deep
  sorted-page memory, and add error-mail backoff/quarantine and erasure diagnostics.
- Add optional production Redis TLS and certificate procedures. Development and
  staging keep the base Redis transport. Clarify application versus monitor email controls.

### Quality and documentation

- Add optional self-hosted load testing with synthetic fixtures, target checks,
  authenticated workflows and separate measurement of ingest completion.
- Generate frontend HTTP types from FastAPI OpenAPI, with source and running-server
  checks and a verified-build CI gate. Use generated types for sample/navigation
  and report responses; retain explicit transports for binary downloads/uploads.
- Use Ruff for Python linting, formatting and import ordering; remove redundant
  Black, Flake8 and isort tools and unused runtime dependencies. Remove the
  documentation linter's vulnerable globbing dependencies and run Markdown checks
  through the repository runner with a patched math renderer.
- Replace obsolete release-validation commands, require real replica-set CI coverage,
  and remove retired runtime/Compose compatibility tests while retaining supported
  migration and clinical safety tests. Keep archived Compose definitions.
- Separate frontend OpenAPI guidance from collection-contract documentation,
  correct test and versioning instructions, and organize audit tests by responsibility.
  Remove placeholder test docstrings while preserving their assertions and fixtures.

For deployment prerequisites, index/retention maintenance, coordinated service
replacement and rollback limits, follow
[release maintenance](docs/deployment/release-maintenance.md) before the
[upgrade procedure](docs/deployment/application-upgrades.md).

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
  - Added `scripts/deployment/compose-with-version.sh` to export version from `api/version.py` and run `docker compose`.
- Added npm package version sync from Python version source:
  - Added `scripts/release/sync-package-version.js`.
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
