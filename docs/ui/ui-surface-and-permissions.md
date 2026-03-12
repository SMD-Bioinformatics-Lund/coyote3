# UI Surface And Permissions Matrix

## Purpose
This document is the authoritative inventory of the Coyote3 web UI surface.
It describes:

- the active UI route families
- the main UI elements rendered on each page family
- the backing API resources each page depends on
- the authoritative API permissions required for read and mutation access
- the browser-backed validation method used for route coverage

The UI is a Flask application with its own blueprint structure. It does not need to mirror the API route shape. Authorization is authoritative in the API, while the UI primarily enforces authentication and hides actions based on template helpers.

## UI Validation Method
UI route validation uses [ui_crawl_playwright.py](/home/ram/dev/projects/coyote3/scripts/ui_crawl_playwright.py) against the local development stack.

The crawl verifies:

- login succeeded with the local admin user
- authenticated crawl covered the main navigation surface, sample pages, DNA pages, RNA pages, profile, handbook, public catalog, and admin pages
- all crawled GET routes returned `200`
- no broken routes were detected
- no crawl notes were emitted

Scope note:
- the crawler verifies page renderability, link traversal, and form target reachability
- it does not submit every destructive mutation with production-like data changes
- mutation correctness is still primarily covered by API tests and targeted UI integration tests

## Access Model
UI access is evaluated at two layers.

1. Flask route access
- Most protected pages use `@login_required`.
- Public pages do not require authentication.

2. API permission enforcement
- The UI calls the FastAPI backend through `coyote/services/api_client/`.
- Read and mutation permissions are enforced by `api/routers/*`.
- Template helpers `can`, `min_role`, `min_level`, and `has_access` only influence presentation and action visibility. They do not replace API policy checks.

## Blueprint Registration
The active Flask blueprint prefixes are registered in [coyote/__init__.py](/home/ram/dev/projects/coyote3/coyote/__init__.py):

| UI prefix | Blueprint purpose |
| --- | --- |
| `/` | login and shared utility endpoints |
| `/samples` | sample list, sample edit context, reports, gene-list selection |
| `/dna` | DNA small variants, CNVs, translocations, DNA report entry points |
| `/rna` | RNA fusions and RNA report entry points |
| `/dashboard` | operational dashboard |
| `/cov` | coverage review and blacklist views |
| `/admin` | governance and resource management UI |
| `/profile` | user profile |
| `/public` | public catalog and contact pages |
| `/handbook` | built-in handbook pages |

## Route Family Matrix

### Login And Session

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/` and `/login` | username field, password field, login submit | public | `POST /api/v1/auth/sessions` | credential-based session creation |
| `/logout` | logout action | login required | `DELETE /api/v1/auth/sessions/current` | active session required |

Notes:
- The UI session is cookie-based.
- The API session cookie is relayed by the Flask login flow.

### Samples And Sample Context

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/samples` and `/samples/<status>` | live samples table, reported samples table, search box, profile scope switch, assay filters, table pagination | login required | `GET /api/v1/samples` | `min_level=1` |
| `/samples/edit/<sample_id>` | sample metadata panel, variant statistics, ASP context | login required | `GET /api/v1/samples/{sample_id}/edit-context` | `min_level=1` |
| `/samples/<sample_id>/isgls` | selected genelists, available genelists | public UI route, but linked from authenticated pages | `GET /api/v1/samples/{sample_id}/genelists` | `min_level=1` |
| `/samples/<sample_id>/effective-genes/all` | effective gene list view | public UI route, but linked from authenticated pages | `GET /api/v1/samples/{sample_id}/effective-genes` | `min_level=1` |
| `/samples/<sample_id>/apply_isgl` | apply selected in-silico gene lists | login required | `PUT /api/v1/samples/{sample_id}/genelists/selection` | `permission=edit_sample`, `min_role=user` |
| `/samples/<sample_id>/adhoc_genes` | save ad hoc genes | login required | `PUT /api/v1/samples/{sample_id}/adhoc-genes` | `permission=edit_sample`, `min_role=user` |
| `/samples/<sample_id>/adhoc_genes/clear` | clear ad hoc genes | login required | `DELETE /api/v1/samples/{sample_id}/adhoc-genes` | `permission=edit_sample`, `min_role=user` |
| `/samples/<sample_id>/reports/<report_id>` | report viewer | login required | `GET /api/v1/samples/{sample_id}/reports/{report_id}/context` | `permission=view_reports`, `min_role=admin` for report context API |
| `/samples/<sample_id>/reports/<report_id>/download` | report download | login required | report file download path from report context | governed by report availability and current session |

Sample comment actions:

| UI route | UI element | Backing API | API permission |
| --- | --- | --- | --- |
| `/sample/<sample_id>/sample_comment` | add sample comment form | `POST /api/v1/samples/{sample_id}/comments` | `permission=add_sample_comment`, `min_role=user`, `min_level=9` |
| `/sample/<sample_id>/hide_sample_comment` | hide comment action | `PATCH /api/v1/samples/{sample_id}/comments/{comment_id}/hidden` | `permission=hide_sample_comment`, `min_role=manager`, `min_level=99` |
| `/sample/unhide_sample_comment/<sample_id>` | unhide comment action | `DELETE /api/v1/samples/{sample_id}/comments/{comment_id}/hidden` | `permission=unhide_sample_comment`, `min_role=manager`, `min_level=99` |

### Dashboard

| UI route | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/dashboard/` | KPI cards, sample progress donut, variant composition donut, tier distribution chart, assay workload chart, quality snapshot, sample distribution charts, admin insight charts | login required | `GET /api/v1/dashboard/summary` | `require_access()` for base dashboard, admin-only sections depend on admin payload fields |

Admin-only dashboard panels:
- users per role
- profession by role

Those panels depend on admin-scoped dashboard data that the API only exposes to high-privilege users.

### DNA Small Variants

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/dna/sample/<sample_id>` | small-variant table, filter form, AI text, panel/genelist coverage, hidden comment indicator, bulk action form | authenticated navigation path | `GET /api/v1/samples/{sample_id}/small-variants` | `min_level=1` |
| `/dna/<sample_id>/var/<var_id>` | variant detail, annotations, latest classification, expression context, CIViC and OncoKB data, hidden comments | authenticated navigation path | `GET /api/v1/samples/{sample_id}/small-variants/{var_id}` | `min_level=1` |
| `/dna/<sample_id>/plot/<fn>` | plot image | authenticated navigation path | `GET /api/v1/samples/{sample_id}/small-variants/plot-context` | `min_level=1` |

Small-variant actions:

| UI route | UI element | Backing API | API permission |
| --- | --- | --- | --- |
| `.../fp` and `.../unfp` | false-positive toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/small-variants/{var_id}/flags/false-positive` | `permission=manage_snvs`, `min_role=admin` |
| `.../interest` and `.../uninterest` | interesting toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/small-variants/{var_id}/flags/interesting` | `permission=manage_snvs`, `min_role=admin` |
| `.../relevant` and `.../irrelevant` | relevance toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/small-variants/{var_id}/flags/relevant` | `permission=manage_snvs`, `min_role=admin` |
| `.../blacklist` | blacklist action | `PATCH /api/v1/samples/{sample_id}/small-variants/{var_id}/flags/blacklist` | `permission=manage_snvs`, `min_role=admin` |
| `.../hide_variant_comment` | hide comment action | `PATCH /api/v1/samples/{sample_id}/small-variants/{var_id}/comments/{comment_id}/hidden` | `permission=hide_variant_comment`, `min_role=manager`, `min_level=99` |
| `.../unhide_variant_comment` | unhide comment action | `DELETE /api/v1/samples/{sample_id}/small-variants/{var_id}/comments/{comment_id}/hidden` | `permission=unhide_variant_comment`, `min_role=manager`, `min_level=99` |
| `/dna/<sample_id>/multi_class` | bulk tiering, bulk false-positive, bulk irrelevant | `PATCH /api/v1/samples/{sample_id}/classifications/tier` and bulk small-variant flag routes | `permission=assign_tier` for tiering, `permission=manage_snvs`, `min_role=user`, `min_level=9` for bulk flagging |
| `.../classify` | create classification from detail page | `POST /api/v1/samples/{sample_id}/classifications` | `permission=manage_snvs`, `min_role=user`, `min_level=9` |
| variant comment forms | add annotation/comment | `POST /api/v1/samples/{sample_id}/annotations` | `permission=add_variant_comment`, `min_role=user`, `min_level=9` |

### DNA CNVs

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/dna/<sample_id>/cnv/<cnv_id>` | CNV detail view, annotation panel, status actions | authenticated navigation path | `GET /api/v1/samples/{sample_id}/cnvs/{cnv_id}` | `min_level=1` |

CNV actions:

| UI route | UI element | Backing API | API permission |
| --- | --- | --- | --- |
| `interestingcnv` and `unmarkinterestingcnv` | interesting toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/interesting` | `permission=manage_cnvs`, `min_role=user`, `min_level=9` |
| `fpcnv` and `unfpcnv` | false-positive toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/false-positive` | `permission=manage_cnvs`, `min_role=user`, `min_level=9` |
| `noteworthycnv` and `notnoteworthycnv` | relevance/noteworthy toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/cnvs/{cnv_id}/flags/noteworthy` | `permission=manage_cnvs`, `min_role=user`, `min_level=9` |
| `hide_cnv_comment` | hide comment | `PATCH /api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden` | `permission=hide_variant_comment`, `min_role=manager`, `min_level=99` |
| `unhide_cnv_comment` | unhide comment | `DELETE /api/v1/samples/{sample_id}/cnvs/{cnv_id}/comments/{comment_id}/hidden` | `permission=unhide_variant_comment`, `min_role=manager`, `min_level=99` |

### DNA Translocations

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/dna/<sample_id>/transloc/<transloc_id>` | translocation detail view, annotation panel, status actions | authenticated navigation path | `GET /api/v1/samples/{sample_id}/translocations/{transloc_id}` | `min_level=1` |

Translocation actions:

| UI route | UI element | Backing API | API permission |
| --- | --- | --- | --- |
| `interestingtransloc` and `uninterestingtransloc` | interesting toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/interesting` | `permission=manage_translocs`, `min_role=user`, `min_level=9` |
| `fptransloc` and `ptransloc` | false-positive toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/translocations/{transloc_id}/flags/false-positive` | `permission=manage_translocs`, `min_role=user`, `min_level=9` |
| `hide_variant_comment` | hide comment | `PATCH /api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden` | `permission=hide_variant_comment`, `min_role=manager`, `min_level=99` |
| `unhide_variant_comment` | unhide comment | `DELETE /api/v1/samples/{sample_id}/translocations/{transloc_id}/comments/{comment_id}/hidden` | `permission=unhide_variant_comment`, `min_role=manager`, `min_level=99` |

### RNA Fusions

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/rna/sample/<sample_id>` | fusion list, filter form, bulk action form, AI text | authenticated navigation path | `GET /api/v1/samples/{sample_id}/fusions` | `min_level=1` |
| `/rna/<sample_id>/fusion/<fusion_id>` | fusion detail, annotations, latest classification, comment controls | authenticated navigation path | `GET /api/v1/samples/{sample_id}/fusions/{fusion_id}` | `min_level=1` |

Fusion actions:

| UI route | UI element | Backing API | API permission |
| --- | --- | --- | --- |
| `fusion/fp/<fus_id>` and `fusion/unfp/<fus_id>` | false-positive toggle | `PATCH` or `DELETE /api/v1/samples/{sample_id}/fusions/{fusion_id}/flags/false-positive` | `min_level=1` |
| `pickfusioncall/...` | choose active fusion caller result | `PATCH /api/v1/samples/{sample_id}/fusions/{fusion_id}/selection/{callidx}/{num_calls}` | `min_level=1` |
| `hide_fusion_comment` | hide comment | `PATCH /api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden` | `min_level=1` |
| `unhide_fusion_comment` | unhide comment | `DELETE /api/v1/samples/{sample_id}/fusions/{fusion_id}/comments/{comment_id}/hidden` | `min_level=1` |
| `/rna/multi_class/<sample_id>` | bulk false-positive and irrelevant actions | `PATCH /api/v1/samples/{sample_id}/fusions/flags/{flag}` | `min_level=1` |

### Reports

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/dna/sample/<sample_id>/preview_report` | DNA report preview | login required | `GET /api/v1/samples/{sample_id}/reports/dna/preview` | `permission=preview_report`, `min_role=user`, `min_level=9` |
| `/dna/sample/<sample_id>/report/save` | DNA report creation | login required | `POST /api/v1/samples/{sample_id}/reports/dna` | `permission=create_report`, `min_role=admin` |
| `/rna/sample/<sample_id>/preview_report` | RNA report preview | login required | `GET /api/v1/samples/{sample_id}/reports/rna/preview` | `permission=preview_report`, `min_role=user`, `min_level=9` |
| `/rna/sample/<sample_id>/report/save` | RNA report creation | login required | `POST /api/v1/samples/{sample_id}/reports/rna` | `permission=create_report`, `min_role=admin` |

### Coverage

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/cov/<sample_id>` | depth cutoff selector, low-coverage table, plot area, blacklist actions, details tables | Flask route does not use `@login_required`; access is enforced by the API session and permission model | `GET /api/v1/coverage/samples/{sample_id}` | `min_level=1` |
| `/cov/blacklisted/<group>` | blacklisted gene and region table | Flask route does not use `@login_required`; access is enforced by the API session and permission model | `GET /api/v1/coverage/blacklisted/{group}` | `min_level=1` |
| `/update-gene-status` | AJAX gene blacklist action | login required | `POST /api/v1/coverage/blacklist/entries` | `min_level=1` |
| `/cov/remove_blacklist/<obj_id>/<group>` | remove blacklist action | Flask route does not use `@login_required`; access is enforced by the API session and permission model | `DELETE /api/v1/coverage/blacklist/entries/{obj_id}` | `min_level=1` |

Coverage note:
- The Flask coverage blueprint has weaker route-level guards than most blueprints.
- Access is still controlled by the API, but maintainers should treat the API permission model as authoritative here.

### Common Utility Pages

| UI route(s) | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/gene/<id>/info` | gene annotation popup/modal content | public UI route | `GET /api/v1/common/gene/{id}/info` | `permission=view_gene_annotations`, `min_role=user`, `min_level=9` |
| `/public/gene/<id>/info` | public gene info popup | public | public gene info backend path | public access |
| `/reported_variants/variant/<variant_id>/<tier>` | reported-variant detail helper | login required | common reported-variant context | governed by authenticated sample access |
| `/search/tiered_variants` | tiered variant search form and result list | login required | common search endpoints | `permission=view_gene_annotations`, `min_role=user`, `min_level=9` for gene detail overlays |

### Profile

| UI route | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/profile/<user_id>/view` | user profile summary | login required | profile-related API context | current-session access to own or resolvable profile |

### Governance And Resource Management

The admin UI remains grouped under `/admin` even though the API uses `/api/v1/users`, `/api/v1/roles`, `/api/v1/permissions`, and `/api/v1/resources/*`.

#### Admin Landing

| UI route | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/admin/` | card grid for users, roles, permissions, ASP, ASPC, ISGL, schemas, audit, sample management | login required | indirect navigation only | card visibility is driven by `permission`, `min_role`, and `min_level` in [views_home.py](/home/ram/dev/projects/coyote3/coyote/blueprints/admin/views_home.py) |

#### Users

| UI route(s) | Main UI elements | API permission |
| --- | --- | --- |
| `/admin/users` | user table, actions | `permission=view_user`, `min_role=admin`, `min_level=99999` |
| `/admin/users/new` | create form | `permission=create_user`, `min_role=admin`, `min_level=99999` |
| `/admin/users/<user_id>/edit` | edit form | `permission=edit_user`, `min_role=admin`, `min_level=99999` |
| `/admin/users/<user_id>/view` | user detail | `permission=view_user`, `min_role=admin`, `min_level=99999` |
| `/admin/users/<user_id>/toggle` | activate/deactivate | `permission=edit_user`, `min_role=admin`, `min_level=99999` |
| `/admin/users/<user_id>/delete` | delete action | `permission=delete_user`, `min_role=admin`, `min_level=99999` |

#### Roles

| UI route(s) | Main UI elements | API permission |
| --- | --- | --- |
| `/admin/roles` | role table | `permission=view_role`, `min_role=admin`, `min_level=99999` |
| `/admin/roles/new` | create form | `permission=create_role`, `min_role=admin`, `min_level=99999` |
| `/admin/roles/<role_id>/edit` | edit form | `permission=edit_role`, `min_role=admin`, `min_level=99999` |
| `/admin/roles/<role_id>/view` | role detail | `permission=view_role`, `min_role=admin`, `min_level=99999` |
| `/admin/roles/<role_id>/toggle` | activate/deactivate | `permission=edit_role`, `min_role=admin`, `min_level=99999` |
| `/admin/roles/<role_id>/delete` | delete action | `permission=delete_role`, `min_role=admin`, `min_level=99999` |

#### Permissions

| UI route(s) | Main UI elements | API permission |
| --- | --- | --- |
| `/admin/permissions` | permission policy table | `permission=view_permission_policy`, `min_role=admin`, `min_level=99999` |
| `/admin/permissions/new` | create form | `permission=create_permission_policy`, `min_role=admin`, `min_level=99999` |
| `/admin/permissions/<perm_id>/edit` | edit form | `permission=edit_permission_policy`, `min_role=admin`, `min_level=99999` |
| `/admin/permissions/<perm_id>/view` | detail page | `permission=view_permission_policy`, `min_role=admin`, `min_level=99999` |
| `/admin/permissions/<perm_id>/toggle` | activate/deactivate | `permission=edit_permission_policy`, `min_role=admin`, `min_level=99999` |
| `/admin/permissions/<perm_id>/delete` | delete action | `permission=delete_permission_policy`, `min_role=admin`, `min_level=99999` |

#### Resources

| UI route(s) | Main UI elements | API permission |
| --- | --- | --- |
| `/admin/asp/manage` | assay panel table | `permission=view_asp`, `min_role=user`, `min_level=9` |
| `/admin/asp/new` | create ASP form | `permission=create_asp`, `min_role=manager`, `min_level=99` |
| `/admin/asp/<id>/edit` | edit ASP form | `permission=edit_asp`, `min_role=manager`, `min_level=99` |
| `/admin/asp/<id>/view` | ASP detail | `permission=view_asp`, `min_role=user`, `min_level=9` |
| `/admin/asp/<id>/toggle` | activate/deactivate | `permission=edit_asp`, `min_role=manager`, `min_level=99` |
| `/admin/asp/<id>/delete` | delete ASP | `permission=delete_asp`, `min_role=admin`, `min_level=99999` |
| `/admin/aspc` | assay config table | `permission=view_aspc`, `min_role=user`, `min_level=9` |
| `/admin/aspc/dna/new` and `/admin/aspc/rna/new` | create ASPC forms | `permission=create_aspc`, `min_role=manager`, `min_level=99` |
| `/admin/aspc/<id>/edit` | edit ASPC form | `permission=edit_aspc`, `min_role=manager`, `min_level=99` |
| `/admin/aspc/<id>/view` | ASPC detail | `permission=view_aspc`, `min_role=user`, `min_level=9` |
| `/admin/aspc/<id>/toggle` | activate/deactivate | `permission=edit_aspc`, `min_role=manager`, `min_level=99` |
| `/admin/aspc/<id>/delete` | delete ASPC | `permission=delete_aspc`, `min_role=admin`, `min_level=99999` |
| `/admin/genelists` | gene-list table | `permission=view_isgl`, `min_role=user`, `min_level=9` |
| `/admin/genelists/new` | create ISGL form | `permission=create_isgl`, `min_role=manager`, `min_level=99` |
| `/admin/genelists/<id>/edit` | edit ISGL form | `permission=edit_isgl`, `min_role=manager`, `min_level=99` |
| `/admin/genelists/<id>/view` | ISGL detail | `permission=view_isgl`, `min_role=user`, `min_level=9` |
| `/admin/genelists/<id>/toggle` | activate/deactivate | `permission=edit_isgl`, `min_role=manager`, `min_level=99` |
| `/admin/genelists/<id>/delete` | delete ISGL | `permission=delete_isgl`, `min_role=admin`, `min_level=99999` |
| `/admin/schemas` | schema table | `permission=view_schema`, `min_role=developer`, `min_level=9999` |
| `/admin/schemas/new` | create schema form | `permission=create_schema`, `min_role=developer`, `min_level=9999` |
| `/admin/schemas/<id>/edit` | edit schema form | `permission=edit_schema`, `min_role=developer`, `min_level=9999` |
| `/admin/schemas/<id>/toggle` | activate/deactivate | `permission=edit_schema`, `min_role=developer`, `min_level=9999` |
| `/admin/schemas/<id>/delete` | delete schema | `permission=delete_schema`, `min_role=admin`, `min_level=99999` |
| `/admin/manage-samples` | sample management table | `permission=view_sample_global`, `min_role=developer`, `min_level=9999` |
| `/admin/samples/<sample_id>/edit` | global sample edit form | `permission=edit_sample`, `min_role=developer`, `min_level=9999` |
| `/admin/manage-samples/<sample_id>/delete` | delete sample globally | `permission=delete_sample_global`, `min_role=developer`, `min_level=9999` |

#### Audit

| UI route | Main UI elements | API permission |
| --- | --- | --- |
| `/admin/audit` | audit log viewer | `permission=view_audit_logs`, `min_role=admin`, `min_level=99999` |

### Public And Handbook Pages

| UI route family | Main UI elements | UI auth | Backing API | API permission |
| --- | --- | --- | --- | --- |
| `/public/assay-catalog...` | assay catalog navigation, matrices, gene export links | public | public catalog API endpoints | public |
| `/public/genelists/<id>/view` | public genelists detail | public | public genelist API/resource path | public |
| `/public/contact` | contact/help | public | none or static content | public |
| `/handbook/...` | handbook navigation and handbook content | login required | handbook UI only | authenticated UI access |

## UI Elements By Family

### Sample Pages
- live sample table
- reported sample table
- global search box
- profile scope selector
- assay-group filters
- table pagination controls
- sample context links
- report links

### DNA Small-Variant Pages
- filter sidebar
- variant result table
- bulk-action toolbar
- hidden comment indicators
- detail evidence panels
- annotation/comment forms
- classification controls
- plot viewers

### RNA Fusion Pages
- fusion filter form
- fusion result table
- bulk-action toolbar
- detail annotation panels
- fusion-call selection controls

### Coverage Pages
- depth cutoff selector
- low-coverage region table
- gene plot
- blacklist gene action
- blacklist region action
- blacklisted-region overview table

### Governance And Resource Pages
- list tables
- create/edit forms
- detail views
- toggle actions
- delete actions
- admin landing cards

## Maintenance Guidance

When adding or changing a UI element:

1. Update the owning Flask blueprint and template.
2. Update the corresponding API route or verify the existing API contract still matches.
3. Add or update UI tests.
4. Add or update API authorization tests if the action mutates data.
5. Update this document if the route family, visible actions, or permissions changed.

When adding a new protected action:

1. Add `@login_required` on the Flask route if the page or action is not public.
2. Add the canonical API client call in `coyote/services/api_client/`.
3. Enforce permissions in the FastAPI router with `require_access(...)`.
4. Expose the action in templates only through `can`, `min_role`, `min_level`, or `has_access`.
5. Verify the action in both UI tests and API tests.

## Error And Feedback Model

The UI uses two different failure presentation models.

### Standard error page

Use the standard error page when the UI cannot render the requested page because essential backend context failed to load.

Examples:

- sample page context cannot be loaded
- dashboard summary cannot be loaded
- report path resolution fails before a report can be served

In this case, the route raises a typed web exception and Flask renders the standard error template with the correct HTTP status code, summary, details, and request id.

### Flash message

Use flash messaging when the page itself is valid but an action inside that page fails.

Examples:

- create or edit action fails
- toggle action fails
- blacklist mutation fails
- bulk action fails

In this case, the UI preserves navigation context and informs the user without replacing the page.

## Known Gaps

- The browser crawl validates route reachability and element traversal, not every destructive state mutation.
- Coverage Flask routes rely more heavily on API-side authorization than on Flask route guards.
- Some legacy UI paths still use older Flask-friendly naming, while the API beneath them is already resource-oriented.

## Related Documentation

- [user-guide.md](user-guide.md)
- [../api/reference.md](../api/reference.md)
- [../api/endpoint-catalog.md](../api/endpoint-catalog.md)
- [../SECURITY_MODEL.md](../SECURITY_MODEL.md)
- [../development/developer-guide.md](../development/developer-guide.md)
