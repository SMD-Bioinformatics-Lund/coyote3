# UI Functionality Matrix

This page documents actual user-facing functionality across the Coyote3 UI.
It focuses on what users can do, not only route names.

For exact button-level behavior, see `Product -> UI Action Effects Reference`.

## Global behavior (app-wide)

| Area | Functionality |
|---|---|
| Permissions | Every action is permission-gated (read, edit, classify, admin actions). |
| Feedback | Success/failure flashes are shown for mutations and save operations. |
| Comments | Comment add/hide/unhide behavior is available across sample and variant views where permitted. |
| Filters | Filter states are persisted at sample level and reused on revisit. |
| Pagination | Home list uses server-side pagination; multiple detail tables use client-side pagination. |
| Help/docs | Help links resolve to the configured docs endpoint (`HELP_CENTER_URL`) and About/Changelog/License pages in app. |

## Dashboard

Users can:

1. View operational KPIs (sample throughput, analysed/pending, tier distribution, quality rates).
2. View assay workload and sample distributions by profile, omics layer, scope, and pairing.
3. Open filtered sample lists from chart interactions (assay/workload drilldown).
4. Toggle gene dashboard view between ASP gene counts and ISGL association metrics.
5. View admin-only insight panels when authorized.

## Samples home

Users can:

1. Search samples by string query.
2. Switch sample view modes (`live`, `reported`, `all`).
3. Filter by profile scope (`production` vs `all`).
4. Filter by assay navigation dimensions (panel type, technology, assay group).
5. Page independently through live and reported tables.
6. Open sample-specific review pages.

## Sample settings page (Edit Sample)

Users can:

1. Select and apply ISGL gene lists to a sample.
2. Add ad-hoc genes (paste/save) and clear ad-hoc gene sets.
3. Inspect effective gene scope computed from ASP + ISGL + ad-hoc state.
4. View sample-level filter thresholds and categorical filter selections.
5. See filtered vs raw variant summary counts.
6. Read latest comments and open full comments modal.
7. Read report history and open/download individual reports.

## DNA workflow UI

## DNA findings list (sample overview)

Users can:

1. Review SNV, CNV, and translocation sections in one DNA workflow.
2. Apply or reset DNA filters (depth, reads, AF, population frequency, consequences, CNV thresholds/effects).
3. Toggle display options like hiding false positives.
4. Trigger bulk classification/flag operations from sidebar actions.
5. Export findings as CSV (SNVs, CNVs, translocations).
6. Open individual SNV, CNV, and translocation detail pages.
7. Preview and save DNA reports.

## Small variant detail

Users can:

1. Inspect transcript/consequence-level details and external references.
2. Mark/unmark False Positive.
3. Mark/unmark Interesting.
4. Mark/unmark Irrelevant.
5. Add/remove blacklist entries (where allowed).
6. Add comments/annotations and optionally mark as global comment.
7. Hide/unhide comments.
8. Classify/remove classification at variant and global levels.

## CNV detail

Users can:

1. Mark/unmark Interesting.
2. Mark/unmark False Positive.
3. Mark/unmark Noteworthy.
4. Add and manage comments (including hide/unhide).
5. Classify CNV findings for reporting context.

## Translocation detail

Users can:

1. Mark/unmark Interesting.
2. Mark/unmark False Positive.
3. Add/manage comments including hide/unhide.
4. Classify translocation findings for reporting context.

## RNA workflow UI

## Fusion list view

Users can:

1. Apply/reset RNA fusion filters:
   - spanning reads/pairs thresholds
   - fusion list selection
   - fusion caller selection
   - fusion effect selection
2. Run bulk class actions on selected fusions.
3. Hide false positives in view.
4. Open per-fusion detail pages.
5. Preview and save RNA reports.

## Fusion detail

Users can:

1. Inspect selected call and alternate calls.
2. Pick which call is selected when multiple calls are available.
3. Mark/unmark fusion as False Positive.
4. Add comments/annotations and optional global annotation.
5. Hide/unhide comments.
6. Apply/remove classification for fusion findings.
7. Use contextual external links (literature/reference portals) from fusion metadata.

## Coverage UI

Users can:

1. View low-coverage information for a sample.
2. Update gene status in coverage context.
3. View blacklisted regions grouped by domain.
4. Remove blacklist entries from coverage blacklist views.

## Common utilities UI

Users can:

1. Search tiered variants globally.
2. Open tiered-variant sample occurrence views.
3. Open gene info pages (public and authenticated contexts).
4. Add sample comments from DNA/RNA contexts.
5. Hide/unhide sample comments.

## Authentication and profile UI

Users can:

1. Login and logout.
2. Run forgot-password flow.
3. Complete reset-password flow using token.
4. View own profile.
5. Change own password (for local-auth users and permissions allowing the page).

## Admin UI

## Admin home and audit

Users with admin access can:

1. Open admin navigation cards for users, roles, permissions, assay resources, samples, and audit.
2. Review audit entries and operation history.

## Users management

Admins can:

1. Search and page through users.
2. Validate username/email availability while creating users.
3. Create users.
4. Edit users.
5. View users.
6. Toggle active state.
7. Delete users.
8. Send invite/reset mail flows for local users.

## Roles and permissions

Admins can:

1. Create, edit, view, toggle, and delete roles.
2. Create, edit, view, toggle, and delete permissions.
3. Work with versioned resource edits in role/permission management.

## Assay resources

Admins can:

1. Manage ASP (assay panels): create/edit/view/print/toggle/delete.
2. Manage ASPC (assay configs): create DNA/RNA config, edit/view/print/toggle/delete.
3. Manage ISGL (genelists): create/edit/view/toggle/delete and manage gene content/versions.

## Sample administration

Admins can:

1. Search and edit sample documents in admin mode.
2. Delete samples from admin sample management.

## Public/catalog UI

Users can:

1. Browse assay catalog and assay catalog matrix.
2. Browse ASP genes and ISGL-linked views.
3. Export catalog genes as CSV.
4. Open gene detail cards and curated list views.
5. Open contact information page.

## In-app meta pages

Users can:

1. Open About page (build/version and project links).
2. Open Changelog page.
3. Open License page.
4. Follow links to full documentation endpoint.

## Notes for maintainers

1. This matrix describes behavior currently wired in templates, blueprints, and API-backed actions.
2. If a new UI action is added, update this page together with developer route docs.
3. Keep this aligned with permission model changes so user-visible capabilities remain accurate.
