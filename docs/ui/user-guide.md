# Coyote3 UI User Guide

## Audience
This guide is for:
- clinical geneticists and doctors reviewing diagnostic findings
- bioinformatics analysts preparing and validating case interpretation
- administrative users maintaining governed configuration and user access

## Scope
This manual explains the current web user interface behavior in Coyote3, including navigation, role-based visibility, sample workflows, DNA and RNA review flows, report access, and operational troubleshooting from an end-user perspective.

For the full route-by-route UI inventory, tested surface summary, and permission matrix, see [ui-surface-and-permissions.md](ui-surface-and-permissions.md).

## Key Concepts
For terminology used in this guide (sample, assay group, tiered variants, RBAC, audit trail), refer to [GLOSSARY.md](GLOSSARY.md).

## Where To Look In Code (for support teams)
- UI routes and page orchestration: `coyote/blueprints/`
- UI templates: `coyote/templates/` and blueprint-specific `templates/`
- UI-to-API calls: `coyote/services/api_client/`

## Operational Implications
- The UI renders server-side templates and displays data returned from API endpoints.
- Permission enforcement is authoritative in API; UI visibility follows that policy but does not replace it.
- If a UI action fails with access denied or backend error, data integrity is preserved because API policy checks occur before state mutation.

---

## 1. System Overview
Coyote3 is a web application for clinical genomics review and reporting. The interface is built around case navigation, assay-aware views, and role-controlled actions. Users move from sample discovery to detailed analysis, then to report reading/export or governed administration depending on permissions.

The UI is not a standalone decision engine. It is a structured clinical workspace that requests domain decisions from the API layer and presents the result in context-specific pages (DNA, RNA, admin, coverage, and report views).

---

## 2. Login and Session Behavior

### 2.1 Login flow
1. Open the Coyote3 login page.
2. Enter credentials (organization-backed authentication flow).
3. On success, you are redirected to the sample dashboard.

### 2.2 Session ownership model
- The browser session is managed by the Flask UI runtime.
- API access is bound to session context and validated on every backend request.
- If session state expires, protected pages redirect to login.

### 2.3 What users should expect
- A successful login gives access only to routes allowed by your role/permissions.
- Menu entries and page actions can differ across users in the same environment.

---

## 3. Navigation Model

### 3.1 Main navigation structure
Coyote3 navigation groups pages by function:
- sample-centric workflows (`/samples` backed by `/api/v1/samples`)
- DNA review routes
- RNA review routes
- coverage and quality views
- dashboard summaries
- administration pages
- documentation/help pages

### 3.2 Sample entry point
The primary starting point for clinical work is:
- `/samples`

This page lists active and completed sample sets and provides filter/search controls.

### 3.3 Context transitions
From sample pages, users can open:
- sample edit/context pages
- DNA small-variant views
- RNA fusion views
- linked report views

Navigation links preserve the current role and session constraints. If you open a route outside your permissions, the action is denied by backend policy.

### 3.4 Embedded views and viewport behavior
- Embedded iframe content (for example the contact/map page) uses responsive container sizing.
- On desktop, iframe panels expand to available page height.
- On narrow screens, layout collapses to one column while preserving readable minimum iframe height.

---

## 4. Role-Based UI Behavior

### 4.1 Why role-aware behavior exists
Clinical workflows require separation of duties. Coyote3 applies role and permission policies so users only perform actions appropriate to their responsibilities.

### 4.2 Typical behavior by user category

1. Analyst-focused users
- Broad read access to sample and variant views.
- Can perform interpretation-oriented actions according to assigned permissions.

2. Clinical reviewer/doctor users
- Emphasis on interpretation and report review flows.
- Access to read and decision support views according to role policy.

3. Administrative users
- Access to user/role/permission management pages.
- Access to schema-driven configuration pages and policy maintenance routes.

4. Restricted users
- Limited menus and action controls.
- No access to admin routes or privileged mutation endpoints.

### 4.3 Important behavior note
UI visibility reflects policy intent, but backend checks are authoritative. If your role changes, visible options may update after re-authentication or session refresh.

---

## 5. Sample Dashboard Workflow

### 5.1 Purpose
The sample dashboard is used to locate active or completed work and route into detailed case views.

### 5.2 Common controls
- free-text sample search
- profile scope selection (`Production`, `All Profiles`) preserved in compact URL query param `scope`
- assay panel filtering options where available
- server-driven table pagination with independent parameters per section:
  - live table: `lp` (page), `lpp` (page size)
  - reported table: `dp` (page), `dpp` (page size)

### 5.3 Interpreting list results
Sample lists are grouped to support operational triage:
- active/live samples for ongoing review
- completed/done samples with report linkage

List behavior:
- Both `Live Samples` and `Reported Samples` sections are rendered on the same page.
- Default profile scope is production-only on first load.
- Switching to `All Profiles` expands both sections using server-side filtering.
- Search applies to both sections and returns full matching sets (no table pagination while search is active).

Selected filters and section paging stay in the URL, enabling refresh and link sharing without losing context.

### 5.4 Pagination preference model
Per-table page size resolution is designed for future user settings:
1. explicit query parameter (`lpp` / `dpp`)
2. persisted user preference (future)
3. system default

This keeps behavior stable now and allows user-configurable defaults later without route redesign.

### 5.5 Opening sample context
Selecting a sample opens a detail/edit context page where report access, gene-related actions, and workflow-specific links are available based on assay and permissions.

### 5.6 Dashboard visualization behavior
The operational dashboard is a summary of throughput, quality, assay load, and catalog/system capacity.
All values are derived from `/api/v1/dashboard/summary` and rendered as cards + charts.

Primary KPI cards:
- `Total Samples`: total sample count in dashboard scope.
- `Analysed`: number of samples marked analysed.
- `Pending`: number of samples pending analysis.
- `Panel Genes`: unique gene count across configured panels in scope.
- Header `Analysed rate`: `analysed / total * 100`.

Sample Progress:
- Donut with two slices: `Analysed` and `Pending`.
- Shows proportion of completed vs remaining work.
- Hover shows absolute counts.

Variant Composition:
- Donut with variant-type mix (for example SNP, Indel, CNV, Fusion, Translocation).
- Side info cards show:
  - `Small Variants`: total small variant count.
  - `SNP Fraction in Small Variants`: `total_snps / total_variants * 100`.
  - `Blacklist Rate`: `blacklisted / total_variants * 100`.
    - `blacklisted` is the count of unique blacklist positions (`distinct("pos")` in blacklist data).
    - denominator `total_variants` is total small variants from the variants dataset.
  - `FP Rate`: `fps / total_variants * 100`.
    - `fps` counts small-variant documents where `fp == true`.
    - denominator `total_variants` is total small variants from the variants dataset.

Tier Distribution (Reported):
- Bar chart of reported variants grouped by Tier 1/2/3/4.
- Used to monitor reporting mix and tiering pressure.

My Assay Workload:
- 100% stacked bar per assay.
- Dark segment = analysed %, light segment = pending % for that same assay.
- Center label = analysed percentage for the full bar.
- Hover shows absolute counts: `total`, `analysed`, `pending`.
- Clicking a bar routes to filtered live samples for that assay group.

Quality Snapshot:
- Multi-ring radial chart with three metrics:
  - `Analysed` (%)
  - `Blacklist` (%)
  - `FP` (%)
- Companion cards repeat the same values with fixed precision.
- The dashboard uses zero-safe math: if `total_variants == 0`, both `Blacklist Rate` and `FP Rate` are shown as `0.0%`.

Sample Distribution:
- Four donut charts:
  - `By Profile`: production/validation/development/testing split.
  - `By Omics Layer`: DNA vs RNA split.
  - `By Sequencing Scope`: scope distribution (for example WGS, WTS, PANEL, DNA, RNA, UNKNOWN).
  - `Pairing Status`: paired, unpaired, unknown.

Sequencing Scope Summary:
- Top scope categories shown as compact cards with absolute counts.
- Intended as a quick “top scopes” read without opening donut tooltips.

Platform Capacity Rings:
- Radial rings for `Users`, `Roles`, `ASP`, `ASPC`, `ISGL`.
- Ring length is normalized to the maximum entity count in this set.
- Hover and ring labels show absolute counts (not normalized percentages).

ISGL Visibility Overlap:
- 3-set overlap (Public, Private, Adhoc).
- Displays only non-zero regions to reduce clutter.
- Hovering circles/regions shows exact region counts.
- Legend hover highlights matching regions.

Admin Insights (admin-only section):
- `Users per Role`: donut distribution of users across roles.
- `Professions by Role`: stacked bar matrix for profession-role composition.

Metric interpretation notes:
- Counts are absolute unless explicitly labeled as `%`.
- Most chart tooltips are count-based for operational triage.
- If displayed values appear stale, verify static asset rebuild and browser cache first.
- If displayed values appear incorrect, validate `/api/v1/dashboard/summary` payload fields before debugging rendering logic.

---

## 6. DNA Workflow in the UI

### 6.1 Entry points
DNA review pages are available from sample context links and DNA navigation entries.

### 6.2 Typical DNA review sequence
1. Open sample context.
2. Enter the DNA small-variant listing page.
3. Apply filters and sort relevant findings.
4. Open variant detail cards/pages.
5. Review tiering, evidence, and annotation context.
6. Save/update permitted interpretation fields.

### 6.2.1 Variant list default sort and bulk actions
- On page load, the SNV list defaults to sorting by the `case` frequency column in descending order (highest AF first).
- In `Modify Variants`, bulk actions apply to the checked rows:
  - `Tier3`:
    - `Apply` adds tier-3 class + default interpretation text annotation docs.
    - `Remove` removes tier-3 class docs and their matching default interpretation text docs for the same scoped context (`assay`, `subpanel`, `gene`, and transcript when available).
  - `Irrelevant` and `False Positive` support both `Apply` and `Remove` in the same bulk flow.
- Sample-specific comments saved from SNV/CNV/translocation detail pages are persisted and rendered from each finding's own `comments` list (separate from global annotations).

### 6.3 Tiered variant interpretation in UI
Tiered views organize findings by clinical significance and configured logic. Users should treat tier placement as review guidance tied to configured workflow rules and assay context.

### 6.4 Reports from DNA context
If reports exist for a sample, users can open report views directly and download files through report links on sample-related pages.

---

## 7. RNA Workflow in the UI

### 7.1 Entry points
RNA pages are accessible from sample context and RNA navigation routes.

### 7.2 Typical RNA review sequence
1. Open sample context.
2. Enter RNA fusion/event listing.
3. Apply fusion and panel-related filters.
4. Open detailed fusion context.
5. Perform allowed actions and comments.
6. Access linked report views when available.

### 7.3 Assay group context
RNA behavior can differ across assay groups. Users should confirm assay group metadata before comparing outcomes between samples.

---

## Coverage Workflow in the UI

### Purpose
The Coverage Review page is used to evaluate low-depth regions for a sample, inspect gene-level transcript coverage, and apply blacklist actions for genes or regions in a governed assay context.

### Entry points
- Coverage page from sample context: `/cov/<sample_id>`
- Blacklisted coverage overview for assay/group: `/cov/blacklisted/<group>`

### Coverage page layout model
- Left sidebar:
  - actions (open blacklisted regions page)
  - cutoff controls (`100X`, `500X`, `1000X`)
  - low coverage region table (sortable)
- Right panel:
  - selected gene plot (with zoom controls)
  - low-coverage detail tables (exons/probes) below the plot

Behavior rules:
- Sidebar can be collapsed/expanded.
- On desktop, sidebar width is resizable and constrained to max 30% width.
- When collapsed, plot/details area uses full available width.
- Plot and detail tables are synchronized in the right panel and resize with available space.

### Plot and table behavior
After selecting a gene in the low-coverage table:
1. A gene coverage plot is rendered.
2. A legend is displayed below the plot area.
3. Low-coverage detail tabs (exons/probes) appear below the plot.
4. Region-level blacklist actions are available in table rows.

Zoom controls:
- `Zoom In`
- `Zoom Out`
- `Reset`

The plot initializes to available panel width and uses internal horizontal scrolling when zoomed, so page-level layout remains stable.

### Blacklist actions and effect
Available actions:
- `Blacklist Gene` (from plot header)
- `Blacklist` for individual region/probe rows

These actions call backend mutation routes and apply group/assay-scoped blacklist state.

### Operational notes for support teams
- Coverage UI route handlers: `coyote/blueprints/coverage/views.py`
- Coverage UI template and interaction logic: `coyote/blueprints/coverage/templates/show_cov.html`
- Coverage API reads: `api/routers/coverage.py`
- Coverage blacklist mutations: `api/routers/samples.py`
- Local vendored plotting dependency: `coyote/static/js/vendor/d3.v7.min.js`

### If colors/layout do not update as expected
- Confirm `tailwind.css` is rebuilt from `coyote/static/css/tailwind.input.css`.
- Hard refresh browser assets after CSS updates.
- If classes are present in templates but missing in compiled CSS, verify Tailwind build runtime and class source/safelist coverage.

---

## 8. Reporting Workflow (Read and Download)

### 8.1 Report access model
Reports are opened from sample pages using report identifiers associated with the sample.

### 8.2 Common report actions
- Open report in browser view.
- Download report file for distribution or archival workflows.

### 8.3 What to verify before export
- correct sample identifier
- correct report identifier/version label
- expected assay context

### 8.4 Variant Table CSV Downloads (DNA)
- SNV, CNV, and translocation table download buttons export backend-generated CSV based on the same active filters as the list page.
- CSV rows include review-state fields (for example false-positive/irrelevant/interesting where applicable) and latest comment metadata when present.
- Multi-value fields are normalized with `|` separators and HGVS is split into `HGVSp` and `HGVSc` for SNV exports.

If a report link fails, the UI redirects back to a safe page and logs the event for operator review.

---

## 9. Admin Workflow in the UI

### 9.1 Admin area purpose
Admin pages manage governed configuration and identity/policy entities, including:
- users
- roles
- permissions
- schemas
- assay-related configuration entities

Admin landing cards are generated from the enabled admin routes. If a route family is not active in the deployed UI module set, its card is not shown.

### 9.2 Governance expectations
Administrative changes affect downstream access and workflow behavior. Perform changes with review discipline and verify outcome in non-production context when available.

### 9.3 Access boundaries
Only users with appropriate permissions can access admin routes. Unauthorized requests are denied by backend checks even if URLs are manually entered.

---

## 10. UI and API Responsibilities (High-Level)

### 10.1 What the UI does
- accepts user input
- calls API endpoints through centralized client helpers
- renders templates and page-level messages

### 10.2 What the API does
- validates authentication and permissions
- applies workflow and business rules
- reads/writes MongoDB through backend handlers
- records audit events

### 10.3 Why this matters to users
This design reduces inconsistent behavior and ensures actions are evaluated consistently regardless of which UI page triggers them.

---

## 11. Security and Access Behavior (User-Facing)

### 11.1 Session handling
- protected pages require valid session context
- session expiry leads to login flow

### 11.2 Permission denial behavior
When a user lacks access:
- sensitive action is blocked
- safe response/redirect is shown
- backend policy prevents state mutation

### 11.3 Audit visibility
Where audit views are exposed to authorized users, they represent backend-generated records of significant actions.

---

## 12. Common User Issues and What To Do

### 12.1 “I cannot see admin pages”
Likely cause: role/permission does not include admin access.
Action: request policy review through administrator.

### 12.2 “A sample appears but action buttons are missing”
Likely cause: page-level action is permission-gated.
Action: verify assigned role and required permission set.

### 12.3 “Report link opens error or redirects back”
Likely causes:
- report file no longer available at expected path
- report identifier mismatch
- backend access denial
Action: capture sample ID + report ID and contact support/admin.

### 12.4 “Data looks stale after role or config change”
Likely cause: session context needs refresh.
Action: log out and log in again; retry route.

### 12.5 “Search returns no expected samples”
Likely causes:
- status mode mismatch (live vs done)
- search/filter criteria too narrow
- assay-specific context
Action: reset filters and confirm expected sample status scope.

---

## 13. Workflow Quick References

### 13.1 Open active sample list
1. Navigate to `/samples`.
2. Confirm status mode.
3. Search and open target sample.

### 13.2 Open report from sample page
1. Open sample context.
2. Locate report list.
3. Open report or use download action.

### 13.3 Perform DNA review
1. Open sample context.
2. Go to DNA small variants.
3. Apply filters and inspect tiered results.

### 13.4 Perform RNA review
1. Open sample context.
2. Go to RNA fusions.
3. Filter, inspect details, and review supporting data.

---

## 14. Related Documentation
- [../ARCHITECTURE_OVERVIEW.md](../ARCHITECTURE_OVERVIEW.md)
- [../api/reference.md](../api/reference.md)
- [../SECURITY_MODEL.md](../SECURITY_MODEL.md)
- [../deployment/troubleshooting.md](../deployment/troubleshooting.md)
- [../development/developer-guide.md](../development/developer-guide.md)
