# Changelog

## v4.0.0

Version 4 replaces Flask with FastAPI and React.

- Session-authenticated ingestion accepts an absent editor-session header and
  preserves valid editor UUIDs without treating dependency metadata as a UUID.
  The runtime pins `pyasn1` 0.6.5 to address decoder denial-of-service advisories.
  Disposable MongoDB integration checks run on demand through the dedicated
  runner or manual CI input. The quality runner preserves relative interpreter
  selections when child checks change working directories.
  API resource navigation keeps the selected section in view after switching to
  a narrow viewport, including repeated and keyboard selections.

- Ingest rejects unsupported ZIP compression before extraction, reports corrupt
  compression streams as input errors, and resolves Windows-style manifest paths.
  CNV and RNA exports preserve zero support; unavailable purity no longer hides
  a valid CNV copy-number estimate. Numeric admin inputs are validated without
  silently truncating values. Missing population frequencies remain unavailable.
  Clinical-rule exports use deferred download cleanup and report download failures.
  Report SVG validation rejects document type declarations regardless of XML encoding.

- SNV CSV exports retain available genotype evidence when other measurements are
  missing, without substituting zero. Coverage tables show unavailable depth
  neutrally, and returning to a previously opened sample resets optional coverage scope.

- Coverage review can optionally narrow assay scope to a gene list captured in
  the applied configuration. Assay scope remains the default; the temporary
  selection leaves finding filters unchanged. The coverage API and SDK accept
  an optional `gene_list_id` and return available list choices.

- Coverage review uses the assay scope captured in the sample's applied
  configuration independently of finding filters. Assays without covered genes
  use the genes present in the ingested coverage data; blacklist exclusions remain
  in effect.

- Overlapping interface-preference saves retain newer edits and roll back only
  failed changes. Coverage blacklists match displayed coordinates and exclude
  blocked intervals from low-coverage summaries while preserving gene context.

- Report save feedback remains bound to its original sample, editing controls
  expire with their lease, and delayed preference responses preserve the current
  account. Structural-finding evidence preserves missing measurements and zero
  coordinates, and translocation support accepts stored comma-separated counts.
  Coverage summaries retain low coding regions without overlapping probes;
  blacklist controls respect permissions and refresh affected results. RNA sorting
  preserves measured zero support, and SNV ingestion closes readers on failure.

- Unified DNA/RNA review with assay-aware filters, reference annotations, biomarkers,
  coverage and traceable classification history.
- Modern HTML/PDF reports with assay-specific accreditation, detailed findings,
  reviewer history and immutable snapshots that preserve issued reports.
  New report defaults and authoring examples use variant terminology; published
  rule wording changes through reviewed versions.
  Migrated report rules support grouped DNA-fusion evidence and explicit legacy
  panel sentence formatting without changing existing rule defaults.
- Governed query policies and clinical reporting rules with visual authoring,
  previews, independent review and controlled publication.
  Bulk annotation templates support finding-specific DNA and RNA tiering previews.
  Rule autosave waits for incomplete sentences instead of submitting empty text.
  Background refreshes preserve unsaved rule edits; bulk previews are bound to the
  selected findings and one published rule version.
  Empty names pause rule autosave; bulk actions prevent duplicate submissions and
  keep failed confirmations open for retry with a fresh annotation preview.
  API requests reject malformed successful responses and handle interrupted body
  downloads. Report preview/save URLs encode sample identifiers consistently;
  corrupt ZIP contents are reported as invalid uploads.
  Shared controls support same-file import retries, honest clipboard failure feedback,
  and form-safe expand/copy buttons. Table state rejects malformed stored sorting,
  bounds URL page sizes, and normalizes sort directions consistently with the API.
  Missing measurements and tiers retain missing-value semantics; epoch timestamps
  display correctly and custom date filters reject impossible dates. Notification
  deduplication preserves distinct messages containing separators.
  Empty MANE annotation lists fall back to available translocation annotations.
  Chart exports contain valid SVG namespaces and reserve subtitle space. IGV keeps
  remote alignment URLs intact, and rule workspaces bound restored panel widths.
  Gene-count extraction ignores metadata, unpaired report paths accept null controls,
  nonfinite sort values remain missing, and encrypted ZIP uploads fail validation.
  Comment saves and suggestions preserve newer edits. Markdown keeps code literal,
  ordered-list numbering and valid block structure; tooltips retain accessible descriptions.
  Tables prevent selection from moving to replacement rows and honor explicit page sizes.
  Notification read changes require successful saves; stale refreshes cannot replace newer inboxes.
  VCF ingestion preserves phasing, missing alleles and measured zero population frequencies,
  accepts AF or VAF, and parses scalar annotations. CNV ingestion rejects partial malformed
  bundles and retains explicit amplification labels. UTF-8 BOM JSON imports are accepted.
  Query imports preserve assay or family bindings through preview and save.
  Sample comparisons retain pinned assay/gene scopes; parent retirement checks child
  policies. Missing RNA filter profiles inherit the applied configuration's defaults.
  Admin rule/profile lists open on current publications; retained resource versions
  are available through read-only history on demand.
- Hierarchical assay catalog with service details, inherited pricing and turnaround,
  reviewed gene scopes, assay comparison and a gene coverage matrix.
  In-place catalog editing supports sections, source dropdowns and draft management.
- Consistent light/dark themes, including API documentation, clearer navigation and raised cards
  and badges.
  Workflow badges share status colors; assay setup uses a unified workspace card.
  Read-only setups explain their state and expose the appropriate editing or review actions.
  Submitted assay setups require approval from their assigned independent reviewer.
  Table search includes searchable column values; diagnosis registries add per-column filters.
- Central assay, diagnosis, gene-list and configuration management, with validated
  imports/exports, editing leases, revision checks and protected system records.
  Numeric filter editing preserves decimal zeros without changing saved number types.
  Reporting forms show tiers for selected sections and retain saved choices in read-only views.
  Setup editing protects unsaved forms and imports, including browser history navigation, and
  supports removing unavailable list selections, with a searchable sidebar and
  workflow-state filters for saved setups.
  Configuration JSON can be staged directly in existing setup drafts with scope checks.
  Resource uploads accept single JSON/YAML objects as well as bulk lists.
  Assay activation requires only Base/production; configurations can be copied from
  saved records or setup drafts into new scopes. Setup review is optional;
  authorized users can publish directly or assign a colleague for optional review.
  Fixed saved setup pages failing to load their reviewer choices.
  Successful setup publication removes draft snapshots while retaining audit events and published versions.
  Delayed file imports cannot overwrite changed or closed editors; deletion clears stale forms
  and confirmation dialogs.
  Restored RNA fusion workflow dependencies and retained setup timestamps when reading snapshots.
- Permission-scoped personal and service tokens with expiry, revocation,
  one-time secrets and audit attribution; retained clinical audit history.
- Resumable background ingestion with credential rechecks, retry safeguards and
  dedicated ingestion audit views.
- Typed HTTP APIs, generated frontend contracts, API documentation and independently
  versioned Python SDK and HTTP client, both starting at `1.0.0`.
- Container deployment, separate workers, backup/recovery tools, offline v2/v3 data
  migration and branded Nginx error pages. Redis transport checks catch missing
  worker dependencies before runtime.
  Isolated legacy builds retain Python 3.12 on Bullseye with signed Debian archives;
  modern builds use Bookworm.
  Host-run commands inherit the configured center mount directory automatically.

### Upgrade and compatibility notes

- External Python clients use `coyote3-client` and import `coyote3_client`
  instead of `coyote3.client`.
- The application uses the COYOTE3 Free-Use Source-Available License 1.0;
  the independent Python client retains Apache 2.0.
- Existing authenticated deployments must apply the updated
  [restricted identity role](docs/operations/audit-and-logging.md#runtime-database-privileges)
  for token access and startup index inspection.
- Follow the [upgrade procedure](docs/deployment/application-upgrades.md) for database
  permissions, identity roles, schema/index maintenance and rollback limits.
  Legacy v2/v3 data migration remains a separate operation.

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
