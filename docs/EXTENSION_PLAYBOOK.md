# Coyote3 Extension Playbook

## 1. Purpose and Operating Context
This playbook defines the approved extension patterns for Coyote3. It is written for engineers maintaining a clinical genomics platform where extension work must preserve security, traceability, reproducibility, and operational stability. Coyote3 has clear architectural boundaries: FastAPI in `api/` owns backend workflow logic and policy enforcement, Flask in `coyote/` owns UI rendering and interaction flow, and MongoDB collections accessed through handler classes in `api/infra/db/` remain the persistence source of truth.

The goal of this document is long-term maintainability, not short-term feature throughput. A feature that works but bypasses boundaries produces latent defects that appear later as authorization drift, inconsistent reports, schema fragmentation, and difficult regression triage. Every extension in this document is framed to prevent that failure mode.

The rules in this playbook assume current project structure and concrete modules already present in the codebase. Examples intentionally reference existing files such as:

- `api/routes/dna.py`, `api/routes/rna.py`, `api/routes/reports.py`, `api/routes/admin.py`
- `api/core/workflows/dna_workflow.py`, `api/core/workflows/rna_workflow.py`
- `api/core/dna/*`, `api/core/reporting/*`, `api/core/interpretation/*`
- `api/app.py` for `require_access(...)` and request-level access auditing
- `api/infra/db/roles.py`, `api/infra/db/permissions.py`, `api/infra/db/schemas.py`, `api/infra/db/reports.py`
- `coyote/blueprints/dna/views_reports.py`, `coyote/blueprints/rna/views_reports.py`
- `coyote/services/reporting/web_report_bridge.py`
- `coyote/services/api_client/api_client.py` and `coyote/services/api_client/endpoints.py`

ASSUMPTION:
The repository uses `api/app.py` as route registration root, imports `api/routes/*` modules for route attachment, and exposes Flask blueprints under `coyote/blueprints/*`.

## 2. Non-Negotiable Extension Rules
These rules apply to all extension work, independent of scenario.

### 2.1 Boundary ownership is mandatory
Backend domain logic belongs to API core modules, not Flask views and not Jinja templates. Flask views should orchestrate request->API->template flow only. Datastore operations belong to handlers in `api/infra/db/`, not route functions.

### 2.2 Policy checks must be explicit at route boundaries
All new FastAPI endpoints must attach `Depends(require_access(...))` with either explicit permission, level, role, or a justified combination. Avoid implicit policy assumptions in helper functions.

### 2.3 Audit continuity must be preserved
`require_access(...)` in `api/app.py` already emits access audit events for authorized and denied requests. Any mutation workflow must also emit domain-level audit events or persist changelog metadata at the business action boundary.

### 2.4 Additive first, removal second
Any contract, schema, or permission model change should be additive first. Removal of legacy behavior only follows adoption and verification windows.

### 2.5 Tests and documentation are part of the change
Extension PRs are incomplete without tests and docs. This is policy, not preference.

## 3. Concrete Architecture Map for Extension Work
Before scenario guides, this map shows where extension code should go in Coyote3.

### 3.1 API route layer
`api/routes/*.py` modules define transport contract and call services. Keep this layer thin.

Example current pattern from DNA route family:

```python
@app.get("/api/v1/dna/samples/{sample_id}/variants")
def list_dna_variants(request: Request, sample_id: str, user: ApiUser = Depends(require_access(min_level=1))):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    ...
```

### 3.2 API service layer
`api/core/*` modules contain workflow and interpretation logic, such as:

- `api/core/workflows/dna_workflow.py`
- `api/core/workflows/rna_workflow.py`
- `api/core/dna/dna_reporting.py`
- `api/core/interpretation/report_summary.py`

### 3.3 Persistence layer
`api/infra/db/*` handlers own Mongo operations and should expose meaningful methods, not low-level query fragments leaking across modules.

### 3.4 UI layer
`coyote/blueprints/*` modules own page route handlers and template rendering. They should call API through `get_web_api_client()` and `forward_headers()`.

Concrete pattern already used:

```python
payload = get_web_api_client().get_json(
    endpoint,
    headers=forward_headers(),
    params=params,
)
```

### 3.5 UI reporting bridge
`coyote/services/reporting/web_report_bridge.py` is the right place for report preview/save orchestration in web layer. It keeps view functions small and keeps API transport details centralized.

## 4. Scenario A: Adding a New Clinical Workflow
A clinical workflow is a domain-level end-to-end path, for example a new DNA interpretation flow or RNA decision-support phase.

### 4.1 Step-by-step process
1. Define workflow state model and endpoints.
2. Define permissions and minimum role/level policy.
3. Add route contracts in `api/routes/`.
4. Add or extend service orchestration in `api/core/workflows/`.
5. Add DB handler methods in `api/infra/db/` for new query/write needs.
6. Add or update report summary logic if workflow affects report content.
7. Add UI page handlers and templates in relevant blueprint.
8. Add tests across route, permission, service, and UI boundary layers.
9. Add migration notes if any persisted shape changes.

### 4.2 Implementation pattern
If adding new DNA workflow endpoint family:

```python
# api/routes/dna.py
@app.get("/api/v1/dna/samples/{sample_id}/new_workflow/context")
def dna_new_workflow_context(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="view_new_workflow", min_role="user", min_level=9)),
):
    sample = _get_sample_for_api(sample_id, user)
    assay_config = _get_formatted_assay_config(sample)
    if not assay_config:
        raise _api_error(404, "Assay config not found for sample")
    payload = DNAWorkflowService.build_new_workflow_context(sample, assay_config)
    return util.common.convert_to_serializable(payload)
```

```python
# api/core/workflows/dna_workflow.py (example pattern)
class DNAWorkflowService:
    @staticmethod
    def build_new_workflow_context(sample: dict, assay_config: dict) -> dict:
        # Validate invariants in service layer, not route or template.
        DNAWorkflowService.validate_report_inputs(runtime_app.logger, sample, assay_config)
        ...
        return {...}
```

### 4.3 Architectural boundary
- Route should validate request and policy, then call service.
- Service should compute workflow behavior and orchestrate handlers.
- Handler methods should query/update Mongo.
- Flask should consume endpoint output only.

### 4.4 Common pitfalls
- Embedding workflow logic in Flask templates or filters.
- Using `min_level` only when a dedicated permission should exist.
- Mutating data without workflow-specific audit or changelog metadata.
- Copying query logic from existing route into new route instead of shared service.

## 5. Scenario B: Adding a New Module
A module is a new cohesive responsibility area, either API-side or UI-side.

### 5.1 Step-by-step process
1. Define module boundary and owner.
2. Create route/service/db files (API module) or blueprint/views/templates (UI module).
3. Register module import in root init paths.
4. Introduce minimal vertical slice endpoint/page.
5. Add policy and tests first, then expand behavior.

### 5.2 API module pattern
Add `api/routes/new_domain.py`, import in `api/app.py` similar to existing route imports.

```python
# api/app.py pattern
from api.routes import new_domain as _new_domain_routes  # noqa: F401
```

### 5.3 Flask module pattern
Add blueprint package:

- `coyote/blueprints/new_domain/__init__.py`
- `coyote/blueprints/new_domain/views.py`
- `coyote/blueprints/new_domain/templates/*`

Use API client rather than direct store access.

### 5.4 Architectural boundary
Do not introduce “shared utility dumping grounds.” New module must map to business capability. If logic is backend-centric, ownership stays in `api/`, not `coyote/`.

### 5.5 Common pitfalls
- Creating a module that mixes unrelated concerns.
- Duplicating API client logic instead of using `coyote/services/api_client`.
- Adding direct Mongo usage in Flask module.

## 6. Scenario C: Adding a New Schema-Driven Configuration
Coyote3 already uses schema-driven config and version history logic via admin utility functions and schema handlers.

### 6.1 Step-by-step process
1. Define schema type and config object purpose.
2. Add schema document structure and validator checks.
3. Add admin endpoints/views for create/edit/detail.
4. Ensure version metadata and change reason capture.
5. Ensure UI consumers can safely render updated shape.
6. Add rollback/rewind expectations where applicable.

### 6.2 Existing anchors in code
- Schema access: `store.schema_handler.get_schema(...)` used in multiple route contexts.
- Version/change utilities: `api/utils/admin_utility.py` and `coyote/util/admin_utility.py`.
- Admin views for schemas: `coyote/blueprints/admin/views_schemas.py`.

### 6.3 Implementation pattern
When a workflow depends on schema:

```python
assay_config_schema = store.schema_handler.get_schema(assay_config.get("schema_name"))
if not assay_config_schema:
    raise _api_error(404, "Schema not found for assay config")
```

When storing config changes, maintain `version`, `version_history`, and actor metadata through admin utility pipeline.

### 6.4 Architectural boundary
Schema acceptance/validation belongs in API and admin domain logic, not in frontend templates. UI should render schema output but should not be sole validator.

### 6.5 Common pitfalls
- Schema updates without incrementing version.
- Schema changes with no compatibility mapping for old documents.
- Field removal without migration plan and test coverage.

## 7. Scenario D: Introducing New Permission Categories
Permissions are data and policy objects, not just route decorators. In Coyote3 they live in permission collection and are evaluated with role-level and deny-overrides.

### 7.1 Step-by-step process
1. Define new category name and purpose.
2. Add permission documents via admin flow or migration.
3. Bind permissions in route dependencies with `require_access(permission=...)`.
4. Update roles to grant/deny as required.
5. Validate through access matrix tests for positive and negative cases.

### 7.2 Existing policy semantics to respect
From `_enforce_access(...)` in `api/app.py`:

- `permission_ok` requires permission present and not denied.
- `level_ok` uses numeric access level.
- `role_ok` compares against resolved role level.
- Access is allowed when any required condition branch is satisfied for configured gate.

Design implication: if endpoint is sensitive, use explicit permission plus level/role constraints as needed, then test deny scenarios.

### 7.3 Implementation pattern
```python
@app.post("/api/v1/dna/samples/{sample_id}/new-action")
def new_action(
    sample_id: str,
    user: ApiUser = Depends(require_access(permission="dna_new_action", min_role="user", min_level=9)),
):
    ...
```

Role and permission persistence is managed through:

- `api/infra/db/permissions.py`
- `api/infra/db/roles.py`

### 7.4 Architectural boundary
Do not hardcode permission catalogs in route modules or templates. Keep policy data in collections and admin management flows.

### 7.5 Common pitfalls
- Adding permission ID but not assigning it to any role.
- Relying only on high-level role thresholds for sensitive actions.
- Ignoring `deny_permissions` behavior in regression tests.

## 8. Scenario E: Refactoring Without Breaking Audit Integrity
Coyote3 audit behavior exists at multiple layers: API access-level auditing in `api/app.py` and Flask-side action logging via `coyote/services/audit_logs/*`.

### 8.1 Step-by-step process
1. Inventory existing events and log formats for target flow.
2. Preserve event names and metadata keys unless intentionally versioned.
3. Keep audit emission point where business context is available.
4. Add regression tests that assert event existence and key fields.
5. Validate actor and request correlation integrity.

### 8.2 Existing audit anchors
- API access audit calls in `require_access(...)` and helper checks in `api/app.py`.
- Flask action audit utilities in `coyote/services/audit_logs/decorators.py` and `logger.py`.

### 8.3 Implementation pattern
For Flask mutation view:

```python
from coyote.services.audit_logs.decorators import audit_action

@some_bp.post("/sample/<sample_id>/action")
@audit_action(action_name="sample_action_update")
def update_action(sample_id: str):
    ...
```

For API path, continue to rely on `require_access(...)` and add domain-level mutation audit where workflow changes persisted state.

### 8.4 Architectural boundary
Do not move audit logging into low-level DB handlers where actor and intent are unclear. Emit at service/action boundaries.

### 8.5 Common pitfalls
- Refactor removes audit decorator or bypasses audited path.
- Metadata key changes break downstream log analysis.
- New mutation endpoint lacks corresponding domain audit event.

## 9. Scenario F: Adding New Report Types
Coyote3 report generation now follows a clear separation: API prepares template + context payload; Flask renders HTML and optionally persists rendered output via API save endpoint.

### 9.1 Existing pattern to keep
API preview endpoint returns:

- `report.template`
- `report.context`
- optional `report.snapshot_rows`

Flask bridge (`web_report_bridge.py`) renders template via `render_template(...)` and posts rendered HTML to API save endpoint.

This pattern enforces your stated boundary: backend decides data/structure, web handles templating/UI rendering.

### 9.2 Step-by-step process
1. Add API preview route for new analyte/report type in `api/routes/reports.py`.
2. Add service builder in workflow/reporting service layer.
3. Return template name and context (not raw HTML) from preview path.
4. Extend save route to accept rendered HTML and snapshot rows.
5. Add bridge methods in `coyote/services/reporting/web_report_bridge.py`.
6. Add blueprint view handlers in DNA/RNA or dedicated report blueprint.
7. Add template in proper blueprint template folder.

### 9.3 Concrete extension pattern
API route:

```python
@app.get("/api/v1/dna/samples/{sample_id}/report/preview")
def preview_dna_report(...):
    ...
    template_name, template_context, snapshot_rows = DNAWorkflowService.build_report_payload(...)
    payload = _preview_response_payload(...)
    return util.common.convert_to_serializable(payload)
```

Flask side:

```python
html = render_preview_report_html("dna", sample_id, save=False)
return html
```

Save flow:

```python
payload = save_report_from_preview("dna", sample_id)
```

### 9.4 Architectural boundary
- API: report payload composition, validation, file naming logic, persistence metadata.
- Flask: template rendering and user interaction flow.

### 9.5 Common pitfalls
- Returning rendered HTML from API for preview and duplicating rendering in Flask.
- Putting report business rules into Jinja filters.
- Inconsistent template/context contract across DNA and RNA flows.

## 10. Scenario G: Maintaining Backward Compatibility
Coyote3 has ongoing refactor streams and legacy compatibility constraints. Compatibility failures are typically contract or document-shape failures.

### 10.1 Step-by-step process
1. Identify compatibility surface (API payload, schema docs, permission IDs, report metadata).
2. Implement additive fields first.
3. Add adapter logic in service/contracts layer if needed.
4. Mark deprecation in docs and changelog with target removal release.
5. Test old and new payload expectations.

### 10.2 Implementation pattern
Add new key while preserving old key during transition:

```python
payload["clinical_tier"] = new_value
payload["tier"] = payload.get("tier", new_value)  # temporary compatibility window
```

### 10.3 Architectural boundary
Compatibility adapters should stay in API service/contract layer. Do not implement compatibility translation repeatedly in each Flask view.

### 10.4 Common pitfalls
- Removing old keys without migration notice.
- Renaming permission IDs without updating role documents.
- Schema evolution without dual-read fallback during rollout.

## 11. Scenario H: Handling Schema Evolution Safely
Schema evolution affects data correctness, UI rendering, and report generation. It requires structured migration discipline.

### 11.1 Step-by-step process
1. Classify evolution type: additive, constrained, breaking.
2. Introduce schema version increment.
3. Add migration script with dry-run mode.
4. Add runtime reader fallback during migration window.
5. Create and validate needed indexes for new query fields.
6. Execute staged rollout and verification.
7. Remove fallback only after data is fully migrated.

### 11.2 Implementation pattern
Migration script skeleton:

```python
# migration_scripts/migrate_x_to_v2.py
for doc in collection.find({"schema_version": {"$ne": 2}}):
    updated = transform(doc)
    if not dry_run:
        collection.replace_one({"_id": doc["_id"]}, updated)
```

Runtime compatibility reader:

```python
def read_doc(doc: dict) -> dict:
    version = doc.get("schema_version", 1)
    if version == 1:
        return adapt_v1_to_v2_in_memory(doc)
    return doc
```

### 11.3 Architectural boundary
Migration belongs to operational scripts and controlled service paths, not inline route mutations on read endpoints.

### 11.4 Common pitfalls
- Single-shot migration with no dry-run report.
- Evolving schema and forgetting associated indexes.
- No rollback strategy for partial migration state.

## 12. Extension Guardrails for UI-API Separation
Because this is a stated architecture objective, these guardrails are explicit.

### 12.1 UI must not know backend internals
Allowed in Flask views:

- endpoint path via `coyote/services/api_client/endpoints.py`
- request headers via `forward_headers()`
- template rendering with payload returned by API

Not allowed in Flask views:

- direct use of `api/infra/db/*`
- direct Mongo access
- workflow computations for classification/tiering

### 12.2 API should not own Jinja presentation
API should return template+context or raw data contracts, but should not depend on Flask-specific filters or template state. This avoids errors like template filter mismatch in API runtime and keeps renderer ownership on web side.

### 12.3 Reporting bridge is the approved seam
`coyote/services/reporting/web_report_bridge.py` should remain the abstraction for preview/save orchestration. Extend this module instead of duplicating report API call logic across blueprint views.

## 13. Test Plan Required for Every Extension
Every scenario above needs a concrete test matrix.

### 13.1 Route contract tests
For each new endpoint:

- 200 path with expected keys
- 401 unauthenticated
- 403 unauthorized
- 404 for missing sample/resource
- 400 for invalid payload

### 13.2 Permission matrix tests
Cover:

- role with permission allowed
- role without permission denied
- role with permission but deny override denied
- minimum level pass/fail boundaries

### 13.3 Workflow/service tests
Unit-test deterministic behavior for filtering, classification, summary generation, and report payload assembly.

### 13.4 UI boundary tests
For Flask views, verify they call API client and render templates; avoid domain logic assertions in UI tests.

### 13.5 Audit tests
Assert expected event emission or log marker presence for critical mutations and access checks.

## 14. Code Review Checklist for Extension PRs
Use this checklist before merge:

1. New logic placed in correct layer (`api/core`/`api/security`/`api/infra` vs `coyote/blueprints`).
2. New routes include explicit `require_access(...)` policy.
3. Permission IDs and role updates are synchronized.
4. Audit behavior preserved or explicitly versioned.
5. Schema/version changes include migration and fallback strategy.
6. UI only consumes API payload; no direct DB logic.
7. Tests include negative authorization and invalid-input cases.
8. Docs updated in relevant files (`ARCHITECTURE_OVERVIEW.md`, `DEVELOPER_GUIDE.md`, `API_REFERENCE.md`, `SECURITY_MODEL.md`, this playbook).

## 15. Operational Rollout Pattern for Extensions
Non-trivial changes should follow staged rollout.

### 15.1 Pre-deploy
- Run full test suite and coverage checks.
- Run migration scripts in dry-run mode.
- Confirm indexes for new query patterns.
- Validate environment variables if new integration needed.

### 15.2 Deploy sequence
1. Deploy API with compatibility readers/adapters.
2. Execute migrations.
3. Verify API route health and audit output.
4. Deploy Flask UI changes.
5. Validate top user paths (DNA, RNA, reports, admin).

### 15.3 Post-deploy verification
- Monitor error rates on new endpoints.
- Monitor audit logs for denied/authorized anomalies.
- Perform sample-based functional checks on reports and workflow states.

### 15.4 Rollback approach
Rollback should disable new write path and preserve read compatibility. Avoid destructive data rollbacks unless tested and approved.

## 16. Common Anti-Patterns to Reject
Reject extension PRs that contain these anti-patterns:

- Flask views computing workflow tiering/classification.
- FastAPI routes that embed large query logic instead of service/handler delegation.
- New permission names without category strategy.
- Silent schema key renames with no migration plan.
- Audit removal during refactor “cleanup.”
- Multiple small ad hoc modules where one cohesive module is appropriate.

## 17. Future Evolution Considerations
Coyote3 can evolve while preserving the same extension discipline.

### 17.1 RBAC to ABAC augmentation
Current `require_access(...)` can be extended with attribute constraints (assay ownership, lab unit, case status) while preserving explicit route declarations.

### 17.2 Mongo modernization path
As MongoDB compatibility constraints are relaxed, introduce schema validation and modern query patterns in controlled phases while preserving document-level backward readability.

### 17.3 Reporting architecture growth
If report volume or formats increase, split report rendering/export orchestration into dedicated backend services, but keep UI rendering boundary stable and avoid logic drift into templates.

### 17.4 Stronger API contract governance
Introduce formal OpenAPI contract tests and consumer compatibility checks to reduce accidental breaking changes.

### 17.5 Observability enrichment
Add correlation IDs across Flask request, API request, and audit event chain for faster incident diagnosis and compliance evidence generation.

The maintainability objective remains constant: preserve boundaries, preserve policy correctness, preserve audit integrity, and evolve additively with explicit compatibility controls.

## 18. Appendix: File-by-File Execution Checklists
This appendix provides concrete checklists mapped to existing Coyote3 paths so engineers can execute extensions with consistent structure.

### 18.1 When adding a new API-backed workflow
Update or create the following files intentionally:

- `api/routes/<domain>.py`: route contracts, request parsing, policy dependency declaration.
- `api/core/workflows/<domain>_workflow.py`: orchestration and business invariants.
- `api/core/<domain>/*`: query composition, normalization, report summary integration.
- `api/infra/db/<collection>.py`: handler methods for new query/write operations.
- `api/app.py`: route module import registration when adding a new route module.
- `tests/api/routes/test_<domain>_routes.py`: HTTP and contract tests.
- `tests/api/test_access_control_matrix.py` or domain-specific policy tests.

Acceptance criteria before merge:

1. Route logic is thin and service-centric.
2. Permission checks are explicit and test-covered.
3. Error responses follow existing API error shape.
4. No workflow logic appears in Flask views.

### 18.2 When adding or changing UI report behavior
Change only approved seams:

- `coyote/blueprints/dna/views_reports.py` or `coyote/blueprints/rna/views_reports.py` for route handlers.
- `coyote/services/reporting/web_report_bridge.py` for API orchestration.
- `coyote/services/api_client/endpoints.py` if new API endpoint path helper needed.
- `coyote/blueprints/*/templates/*.html` for presentation.

Do not change:

- API workflow logic in UI files.
- Database access code in UI files.

### 18.3 When introducing policy and role changes
Required touchpoints:

- `api/infra/db/permissions.py` usage path for permission persistence and lookup.
- `api/infra/db/roles.py` usage path for role grants and deny rules.
- route decorators in `api/routes/*` using `require_access(...)`.
- admin UI route handlers in `coyote/blueprints/admin/views_permissions*.py` and `views_roles*.py` if user-facing management is required.

This checklist should be attached to the PR description for every policy-impacting change so reviewers can verify completeness quickly.
