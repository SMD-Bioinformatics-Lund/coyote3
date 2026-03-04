# Coyote3 UI User Guide

## Audience
This guide is for:
- clinical geneticists and doctors reviewing diagnostic findings
- bioinformatics analysts preparing and validating case interpretation
- administrative users maintaining governed configuration and user access

## Scope
This manual explains the current web user interface behavior in Coyote3, including navigation, role-based visibility, sample workflows, DNA and RNA review flows, report access, and operational troubleshooting from an end-user perspective.

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
- sample-centric workflows (home/samples)
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
- DNA variant views
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
- tabbed status selection (`Live`, `Reported`, `All`) preserved in URL query param `view`
- assay panel filtering options where available
- server-driven pagination (`page`, `per_page`) so large sample sets do not overload one response

### 5.3 Interpreting list results
Sample lists are grouped to support operational triage:
- active/live samples for ongoing review
- completed/done samples with report linkage

Tab behavior:
- `Live`: shows only active samples
- `Reported`: shows only reported samples
- `All`: shows both sections on one page

The selected tab and page index stay in the URL, enabling refresh and link sharing without losing filter state.

### 5.4 Opening sample context
Selecting a sample opens a detail/edit context page where report access, gene-related actions, and workflow-specific links are available based on assay and permissions.

---

## 6. DNA Workflow in the UI

### 6.1 Entry points
DNA review pages are available from sample context links and DNA navigation entries.

### 6.2 Typical DNA review sequence
1. Open sample context.
2. Enter DNA variant listing page.
3. Apply filters and sort relevant findings.
4. Open variant detail cards/pages.
5. Review tiering, evidence, and annotation context.
6. Save/update permitted interpretation fields.

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
2. Go to DNA variants.
3. Apply filters and inspect tiered results.

### 13.4 Perform RNA review
1. Open sample context.
2. Go to RNA fusions.
3. Filter, inspect details, and review supporting data.

---

## 14. Related Documentation
- [ARCHITECTURE_OVERVIEW.md](ARCHITECTURE_OVERVIEW.md)
- [API_REFERENCE.md](API_REFERENCE.md)
- [SECURITY_MODEL.md](SECURITY_MODEL.md)
- [TROUBLESHOOTING.md](TROUBLESHOOTING.md)
- [DEVELOPER_GUIDE.md](DEVELOPER_GUIDE.md)
