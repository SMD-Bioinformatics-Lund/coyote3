# Changelog

## v4.0.0

Version 4 replaces the Flask application with FastAPI and React, bringing clinical
review, reporting, administration and integrations into one application.

### Clinical review and reporting

- Reporting rules can use calculated CNV copy numbers and paired/split-read
  percentages as inline values or compose grouped CNV summaries with reviewed wording.
- Unified DNA and RNA review with assay-aware filtering, reference annotations,
  coverage, biomarkers and consistent finding identities across workflows.
  Annotation deactivation preserves classification history and recorded sample links,
  with explicit warnings for uncertain legacy history. Inactive annotations do not
  automatically tier new samples during analysis.
- Governed query policies and reporting rules with visual authoring, sample-backed
  previews, independent clinical review and controlled publication.
- Modern branded reports are the primary format, with repeated PDF patient headers,
  assay-specific accreditation, compact findings and formatted summaries. Manual
  biomarker assessments retain reviewer history and appear in report summaries.
  Saved reports retain immutable finding and
  configuration snapshots; existing issued reports remain unchanged.
- Consistent light/dark themes and clearer navigation across sample review,
  reporting, the assay catalog and administration.

### Administration and security

- Query rules, reusable profiles and assay setups support reviewed JSON imports
  and portable exports. Diagnosis, group and assay-association registries provide
  JSON exports matching their bulk creation workflows. User, role, permission and
  application-control forms also support configuration transfer without credentials
  or imported approval state.

- Diagnosis definitions always provide a view action, explain protected records,
  and offer confirmed availability changes for editable definitions.
- Updated vulnerable runtime dependencies and the documentation toolchain's RE2JS
  dependency; corrected the aggregate SDK extra to select SDK version `1.0.0`.
- Central management of assays, diagnoses, gene lists and configurations, including
  validated JSON/YAML bulk installation and a public assay catalog with DNA/RNA
  navigation by sequencing family, biological group and diagnosis, multi-gene
  matching and test comparison. The gene coverage matrix includes knowledgebase
  badges and keeps grouped headers aligned when analyses and filters change.
- Shared editing sessions and revision checks protect concurrent changes. Creator
  attribution and read-only system records preserve configuration provenance.
- Permission-based access across the UI and API, with assay and environment scopes,
  required first-login password changes and retained clinical audit history.
  Operational audit records have separate retention controls.

### Integrations and operations

- Analysis descriptions are authored, tested and published through clinical rules
  with dynamic values and assay Base inheritance. ASPCs no longer store description text.
- Dedicated Admin ingestion audit with outcome filters, sample links and correlated
  history; synchronous uploads and workers retain attempt outcomes in audit storage.
- Cron ingestion records pending submissions before upload, recovers terminal
  acknowledgements without reuploading, and blocks uncertain or conflicting retries.
- Typed HTTP APIs, generated frontend contracts, and a themed API documentation
  portal with resource browsing, structured response examples, authentication
  guidance and searchable endpoints.
- Independently versioned core SDK and sync/async Python HTTP client, both starting
  at `1.0.0`, alongside application `4.0.0`.
- Offline v2/v3 migration workflows for samples, findings, annotations, blacklist
  records and related data, with scope validation and preserved clinical history.
- Container deployment, separate ingestion and maintenance workers, backup/restore
  tooling, optional Redis TLS, and deployment acceptance and recovery procedures.
- Expanded clinical regression coverage, synthetic integration/load testing, and
  task-oriented user, developer and operator documentation.

### Upgrade and compatibility notes

- External Python clients now use the independent `coyote3-client` package and
  import `coyote3_client` instead of `coyote3.client`.
- The application uses the COYOTE3 Free-Use Source-Available License 1.0; the
  independent Python client retains Apache 2.0.
- Review database permissions, identity-role upgrades, schema/index maintenance
  and rollback limits in the [upgrade procedure](docs/deployment/application-upgrades.md).
  Legacy v2/v3 data migration is a separate operation, not a routine upgrade step.

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
- Improved markdown rendering for summary comments-headings, line breaks, and formatting now display correctly using the enhanced format_comment filter.
- Updated report terminology: replaced “variant” with “mutation” in summary text, variant summary table, detailed table headers, and Tier 3 naming.

## v3.0.9

### BugFix #119

- Fixed carry-over of protein changes between variants.
  The protein_changes list is now reinitialized inside the variant processing loop, ensuring each variant has its own independent protein change data.
  Previously, variants without explicit protein changes could inherit those from prior variants, causing incorrect annotations.
- Added a repository collection-mapping configuration for easier deployment management.

## v3.0.8

### HotFix #117

- Fixed handling of long indel in reports: indels longer than 20 characters are no longer truncated in the UI - table cells show the indel length (e.g., "45 bp") instead of a cut-off sequence. For very long indels (>30 characters) the column header is also updated to include the indel length to improve readability.

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
