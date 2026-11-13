# Changelog

## v3.4.3

- Fix variant detail rendering for numeric-string gnomAD frequencies using the shared percentage formatter; handle missing values and compare population-frequency thresholds numerically.

## v3.4.2

- Fix the production translocation collection mapping so TumWGS translocations are read from `transloc`.

## v3.4.1

- Fix genelist URL in the public catalog

## v3.4.0

- Render production DNA reports using `smd-reports==0.5.3`, with conditional JSON
  built from existing findings and configuration and the production author label preserved.
- Match DNA report, summary, and snapshot eligibility to the selected transcript and
  assay context; exclude indication-only classifications and apply existing report exclusions.
- Add HTML preview downloads, compact panel and gene-list actions, and a centered
  confirmation dialog before finalizing reports through the existing save workflow.
- Read laboratory identity and contact details from config and embed application,
  center, and optional accreditation logos. Show accreditation artwork only for accredited assays.
- Use matching numbered-table captions, bordered classification tables, uniform gene
  matrices, themed detail labels, and conclusion headings containing the clinical question.
- Update report dependencies and remove unused PDF-rendering dependencies.
- Update production/development image builds and install scripts for runtime environment
  configuration, deployment recovery, and env-selected accreditation-logo staging.
- Stop tracking local `bugs/` artifacts and ignore them in Git.

## v3.3.0
### DNA – Translocations
- Added "Pick" for DNA translocation annotations: users can select which alternate transcript combination is the active annotation (new `dna_bp.pick_transloc_call` route, `TranslocsHandler.pick_transloc`). The selected annotation is used as fallback when no MANE annotation exists.
- Alternate transcript table in translocation view now has a "Status" column (Selected / Pick) and is sortable.
- Translocation header now uses the `GENE1::GENE2` fusion naming convention.
- Updated `regex_replace` filter to return an empty string for values without digits (cleaner DNA translocation display).
- Updated IGV links for TumWGS translocations.

### RNA – Fusions
- Reworked RNA fusion views to align with the DNA layout (fusion list, fusion detail, sidebars, selected gene/fusion panel).
- Fusion routes are now sample-scoped (`/<sample_id>/fusion/<fusion_id>`, fp/unfp, pick call, hide/unhide comment).
- Moved fusion query building out of `dna/varqueries.py` into new `rna/fusion_queries.py` (spanning pairs/reads coerced to int, effect/caller/fusion-list filters).
- Added RNA expression, RNA QC and RNA classification data to the sample view (new handlers `rna_expression`, `rna_qc`, `rna_classification` and matching collections in `coyote3_collections.toml`).
- Added fusion handler helpers: matching breakpoints, fusion in other samples, hidden fusion comments.
- RNA report: refactored report payload building, added save-report route (`/sample/<sample_id>/report/save`) and updated fusion tiering.
- Renamed `fusioneffects` filter key to `fusion_effects`.
- Sample deletion now also removes RNA expression, QC and classification records.

### Assay catalog
- Restructured TumWGS hematology into separate Hematology, Myeloid and Lymphoid categories, each with its own gene list, analysis types and description (with links to the curated pindel, CNV and fusion lists).
- Relabelled TumWGS solid as "Pediatric solid cancer" with an updated description.

### Fixes / internal
- Fixed `get_isgl_by_asp` `is_active` filter (it was a no-op because of `:` instead of `=`) and added a `list_type` filter.
- Default filters now override sample filters only when the sample value is `None`, so falsy values such as `0` and `[]` are kept.
- Dev/Test config now uses `config/coyote3_collections.toml`. Dev CNV collection is renamed `cnvs_wgs` → `cnvs`.
- Dev Docker port changed 6815 → 8801. `run.py` reads its port from `PORT_NBR`.

## v3.2.0
- Changed the headers in the reports for CNVs (Kliniskt relevanta genspecifika kopietalsförändringar) and Fusions (removed DNA in the name), diagnosis is fixed as 'Solid tumör' for solid tumors.
- Fixed ASPC Create/Edit numeric input step handling: float fields now use `step="0.1"` (including CNV gain/loss ratio fields) and int fields use `step="1"`, so decimal CNV ratio values save correctly.
- Fixed development Tailwind watcher stability in Docker by running `npm run dev:css -- --watch=always` in `coyote3_dev_tailwind` to prevent restart loops and stale CSS.
- Fixed DNA variant sidebar CNV ratio filter inputs to render as numeric controls (`type="number"`, `step="0.1"`), enabling proper decimal stepping/validation for gain/loss cutoffs.
- Fixed DNA/RNA classify/remove-classify/comment action handlers to accept explicit Flask route kwargs (`var_id`, `fus_id`, `cnv_id`, `transloc_id`) and avoid `unexpected keyword argument` errors from multi-route endpoints.
- Moved shared classify/remove-classify/comment routes from `dna_bp` to `common_bp` (keeping existing `/dna/...` URL paths), and updated DNA/RNA templates to call `common_bp` endpoints.
- RNA: Updated fusion detail views to use shared `common_bp` endpoints for classify, remove-tier, and add-comment flows.
- RNA: Fixed legacy fusion template action URLs to pass correct route params (`sample_id`, `fus_id`) for shared handlers.
- Fixed TumWGS translocation Sample-Specific Data rendering by iterating on `tl.GT` and using `_sample_id`, restoring per-sample values in the detail table.
- Fixed TumWGS DNA report fusion rendering: corrected fusion summary iteration/section handling and populated fusion report payload data so clinically relevant fusions appear in generated reports.


## v3.1.22
- Variant search gene mode will match exact gene search string, not substring match.
- Added CNV to the Solid CRC avaiable analysis options in the assay catalog.

## v3.1.21
- Fixed HGVS display/toggle behavior across DNA variant list, tiered search, and reported variants views (unique row IDs, stacked HGVS lines, and no blank indent when only one HGVS value exists).
- Replaced legacy custom width utility usage (`max-w-15c` style) with Tailwind arbitrary values where used.
- Removed deprecated DNA gene view routes/templates (`/gene_simple/<gene_name>`, `/gene/<gene_name>`).

## v3.1.20
- Updated handbook structure and docs routing to use main/user/developer index pages, standardized ASP/ASPC/ISGL naming, and added DNA/RNA/Sample/Admin flow diagrams.

## v3.1.19
- Fixed Tailwind v4 dynamic class generation gaps by expanding template scan coverage (`.jinja/.jinja2`) and explicit inline source classes for semantic/admin color tokens.
- Added Tailwind v4 border compatibility base layer and stabilized modal/button styling with Tailwind-safe static class mapping.
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
  - Added `scripts/compose-with-version.sh` to export version from `coyote/__version__.py` and run `docker compose`.
- Added npm package version sync from Python version source:
  - Added `scripts/sync-package-version.js`.
  - Wired `postinstall`, `prebuild:css`, and `predev:css` to sync `package.json` version from `coyote/__version__.py`.
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

## v3.1.9
- Kept the old Gens URI until the complete migration.

## v3.1.8
- Added FL, DLBCL and Breast Cancer analysis/Genelists in the assay catalog

## v3.1.7
- Add New GENS Link

## v3.1.6
- Introduced a dedicated `reported_variants` collection to track tiered variants per report and sample.
- Linked variant tiers to the reports in which they are clinically reported.
- Added `TieredVariantSearchForm` and new `/search/tiered_variants` view to search annotations by gene, variant, transcript, author, assay, and subpanel.
- Connected annotation search results to samples and reports via the `reported_variants` collection, including per-sample report references.
- Added tier statistics sidebar to the tiered variant search page.
- Improved HGVS protein normalization to support complex clinical variants and enhanced backfill reliability using JSONL-based dry-run and bulk insert workflows.
- Fixed gene links to correctly deep-link into tiered variant search with proper query parameters and assay filtering.

## v3.1.5
- Added CNV aftefct column from the legacy coyote

## v3.1.4
- Adjusted sample search behavior to remove the time limit for user-initiated searches, while keeping a default 90-day time filter for reported samples.
- Changed the sample profile filter to hide non-production samples by default, with a toggle to show all samples.
- Removed Exon/Intron Info from the variant table in the report.
- Fix: Replaced naive datetime usage with a centralized `utc_now()` helper to ensure all newly stored timestamps are timezone-aware and consistently recorded in UTC.
- Fix: removed excess whitespace in DNA report variant comments caused by default paragraph margins in report tables.
- Fix: prevent hidden genelist form fields from rendering as stray boxes in generated report PDFs.
- Fix: Prevent previously tiered variants marked as false positives from appearing in the “Suggest” summary text (they were only removable by marking as irrelevant), while still keeping them out of the final summary table.
- Fix: Reduced the default font size of markdown headings inside the summary editor (EasyMDE/CodeMirror) so section headers appear more compact while typing, matching the final report style.

## v3.1.3
- Fixed missing ISGL routes in production by standardizing Flask blueprint route definitions.

## v3.1.2
- Admin: Fixed JSON sample editor to safely serialize and restore MongoDB ObjectIds during full document updates.

## v3.1.1
- Reports: HTML reports now use compact UTC timestamps in filenames to avoid collisions on re-runs.
- New format <TUMOR_NAME>_<TUMOR_CLARITY_ID>-<NORMAL_NAME>_<NORMAL_CLARITY_ID>.<YYDDMMHHSS>.html for tumor-normal analysis.  <TUMOR_NAME>_<TUMOR_CLARITY_ID>.<YYDDMMHHSS>.html for tumor only analysis.

## v3.1.0
### Added
- Sample landing page to view sample related meta data, case/control overview, files & QC, gene filters, variant filters, analysis data counts, reports, comments, etc.
- Sample landing (settings/edit) page will now show the list of files associated with the sample and if they exist on the drive.
- Added support for AdHoc Gene lists
- Added a key 'adhoc and is_public' to indicate if the gene list is adhoc and public in the isgl schema.
- Added a public facing assay catalog page to view assay related meta data, genelists, configs, etc. This is controlled by assay_catalog.yaml file along with APC and ASPC.
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


# v3.0.9
### BugFix #119
- Fixed carry-over of protein changes between variants.
  The protein_changes list is now reinitialized inside the variant processing loop, ensuring each variant has its own independent protein change data.
  Previously, variants without explicit protein changes could inherit those from prior variants, causing incorrect annotations.
- Added Config/coyote3_collections.toml file to repository for easier configuration management.

## v3.0.8
### HotFix #117
- Fixed handling of long indel in reports: indels longer than 20 characters are no longer truncated in the UI — table cells show the indel length (e.g., "45 bp") instead of a cut-off sequence. For very long indels (>30 characters) the column header is also updated to include the indel length to improve readability.

## v3.0.7
### BugFix
- Fixed full gene view to get all the tiered variants along with the samples. #115

## v3.0.6
- SNV filter step size has been changed to 0.001, now user can go upto 0.1% at the lowest.

## v3.0.5
- Download of csv file from Coyot3 #109
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
