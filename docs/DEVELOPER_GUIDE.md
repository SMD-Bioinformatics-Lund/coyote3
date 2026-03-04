# Coyote3 Developer Guide

## 1. Purpose and Engineering Context
This guide is the primary implementation manual for engineers who build and maintain Coyote3. The intention is not to provide only a file listing or a set of code snippets, because that style is insufficient in a clinical platform where architectural discipline is part of product safety. The goal is to explain how to work inside this repository without violating boundaries, without introducing policy drift, and without creating hidden operational risk. Every major pattern described here exists because the system supports regulated genomic workflows, where reproducibility, traceability, and controlled change matter at least as much as throughput and developer convenience.

Coyote3 combines Flask UI and FastAPI backend in a split-stack architecture. At first glance that may look like unnecessary complexity, especially if you have worked in simpler monolithic web applications. In practice, the split is deliberate. The API layer is treated as the policy and orchestration authority for all clinically meaningful actions, while the UI layer is treated as rendering and interaction orchestration. This choice enforces a repeatable mental model: if an operation changes domain state or decides authorization, it belongs in API core modules and route dependencies; if an operation determines layout, display flow, and user affordance, it belongs in Flask blueprints and templates. Engineers who follow this separation can safely evolve features with lower risk of side effects.

You should read this guide as a set of required habits rather than optional style preferences. Coyote3 is not an environment where ad hoc shortcuts become harmless technical debt. A direct database call from UI code, a hidden fallback that bypasses contract validation, or an unstructured error response can all create clinical or compliance risk. The platform is designed to make correct behavior easier than risky behavior, but it still depends on disciplined implementation. The sections below give you concrete extension patterns and explain why each pattern exists, what alternatives were evaluated, and what failure modes occur when the pattern is ignored.

## 2. Full Repository Structure Example and Rationale
The repository layout is organized around runtime ownership, domain behavior, and testability. A practical structure overview is shown below. This is intentionally verbose because understanding file placement is the first safeguard against boundary drift.

```text
coyote3/
  api/
    __init__.py
    app.py
    extensions.py
    settings.py
    runtime.py
    runtime_bootstrap.py
    contracts/
      *.py
    core/
      dna/
      rna/
      reporting/
      coverage/
      public/
      workflows/
      interpretation/
      admin/
    domain/
      __init__.py
      models/
      core/
    security/
      access.py
      auth_service.py
    audit/
      access_events.py
    infra/
      db/
      external/
    routes/
      admin.py
      common.py
      coverage.py
      dashboard.py
      dna.py
      home.py
      internal.py
      public.py
      reports.py
      rna.py
      samples.py
      system.py
    errors/
      exceptions.py
    utils/
      common_utility.py
      admin_utility.py
      dashboard_utility.py
      report/

  coyote/
    __init__.py
    blueprints/
      admin/
      common/
      coverage/
      dashboard/
      dna/
      docs/
      home/
      login/
      public/
      rna/
      userprofile/
    services/
      api_client/
        base.py
        api_client.py
        endpoints.py
        web.py
    templates/
      ...
    static/
      css/
      js/
      images/
    errors/
      exceptions.py
      handlers.py
    filters/
      registry.py
      shared.py

  tests/
    conftest.py
    api/
      fixtures/
      routes/
      services/
      test_access_control_matrix.py
      test_api_client_architecture.py
      test_api_route_auth_matrix.py
      test_api_route_security.py
      test_route_module_organization.py
      test_workflow_contracts.py
    web/
      test_web_api_boundary.py
      test_web_api_integration_helpers.py

  docs/
    index.md
    ARCHITECTURE_OVERVIEW.md
    DEVELOPER_GUIDE.md
    API_REFERENCE.md
    UI_USER_GUIDE.md
    SECURITY_MODEL.md
    DATA_MODEL.md
    DEPLOYMENT_AND_OPERATIONS.md
    TESTING_STRATEGY.md
    EXTENSION_PLAYBOOK.md
    CODE_STYLE.md
    RELEASE_PROCESS.md
    TROUBLESHOOTING.md
    GLOSSARY.md
    TRACEABILITY_MATRIX.md
    API_ENDPOINT_CATALOG.md

  docker-compose.yml
  docker-compose.dev.yml
  requirements.txt
  pyproject.toml
  pytest.ini
  README.md
```

This structure is not arbitrary. The backend is segmented into routes, core domain modules, security components, and infrastructure handlers so that request contract concerns stay separate from workflow concerns and persistence concerns. The UI has dedicated integration modules for API communication to prevent hidden direct dependencies on API internals. Tests mirror this split by organizing API behavior tests, unit workflow/core tests, and web boundary tests. If you find yourself trying to add business logic in a Flask blueprint or direct persistence in a route module, use that impulse as a signal that a boundary is being crossed and reevaluate placement.

### 2.1 2026 architecture migration (what changed and why)
The current repository state reflects a deliberate multi-commit migration that removed legacy service-bucket ambiguity and hardened API contracts.

Key changes:
- `api/services/*` was fully removed after moving modules to `api/core/*`, `api/security/*`, and `api/infra/*`.
- workflow, interpretation, DNA, RNA, reporting, coverage, and public-catalog logic now live under `api/core/*`.
- auth logic was moved to `api/security/auth_service.py`, co-located with access checks in `api/security/access.py`.
- LDAP was moved to `api/infra/external/ldap.py`.
- all `/api/v1` routes now use explicit typed response models in `api/contracts/*`; temporary generic payload contracts were removed.
- Flask UI API client now forwards `Authorization: Bearer <api_session_token>` for server-side API calls.

Why this matters for contributors:
- File placement now enforces intent. A new feature should signal ownership by its package path before reviewers even open the file.
- Contract drift risk is lower because route responses are strongly typed and validated.
- Security review is simpler because auth/session logic is centralized in `api/security`.
- Future module additions have a clear decision table:
  - domain/workflow rules -> `api/core`
  - authentication/authorization -> `api/security`
  - storage/external systems -> `api/infra`

A common mistake for new engineers is to optimize for “fewest files touched” rather than “correct ownership.” That strategy may pass quick smoke tests but usually introduces hidden coupling. In Coyote3, touching three modules in a clear route->service->handler flow is safer than pushing all behavior into one route function for convenience.

Utility placement is now strict to prevent duplicate logic between API and UI:
- `api/utils/*`: backend-only helpers used by backend modules; these may support workflow/security/persistence behavior and are never imported by Flask UI.
- `coyote/util/*`: presentation-only helpers used by Flask blueprints/templates. These helpers must stay narrow (formatting, safe parsing, view payload shaping) and must not replicate backend business decisions.
- if a helper starts affecting authorization, versioning, report computation, or persistence semantics, it must move to `api/core`, `api/security`, or `api/infra` and be consumed through API endpoints from UI.

This rule exists because duplicated helper logic creates boundary drift and divergent behavior during future changes. During refactor cleanup, `coyote/util/common_utility.py` was reduced to UI-only helpers so backend utility implementations remain the canonical source for domain-level behavior.

## 3. Module Responsibilities and Extension Boundaries
### 3.1 FastAPI route modules
Route modules in `api/routes/*` are endpoint adapters. Their responsibilities include parsing request parameters, binding dependency checks, invoking services, and shaping deterministic response contracts. Their responsibilities explicitly exclude heavy business logic and direct multi-step persistence orchestration. A route should read as “what endpoint is this and what service does it call,” not as a multi-page workflow script.

The design reason is auditability and predictability. Routes are your external contract surface; they must remain readable, stable, and easy to diff during review. If route modules accumulate domain logic, contract change review becomes difficult and side effects hide behind endpoint wrappers. That is why adding a new endpoint usually means adding a route function plus a service function plus possibly a handler method. Engineers new to this pattern may initially perceive it as ceremony; in a regulated platform, this “ceremony” is the safety structure.

### 3.2 Core modules
Core modules in `api/core/*` own domain orchestration, policy-sensitive workflow behavior, and multi-repository sequencing. They normalize business input, enforce domain invariants not covered by simple schema validation, and coordinate changes across persistence boundaries in deterministic order. Core modules should remain framework-agnostic and avoid FastAPI/Flask imports so they stay reusable and unit-test focused.

The tradeoff is that core modules require stronger unit and integration test discipline. A core function that orchestrates three repositories and one audit emitter has several failure branches. That complexity is acceptable because it is explicit and testable. The alternative, embedding workflow logic into route functions, produces complexity anyway but with poorer isolation and weaker review quality.

### 3.3 Data access handlers
Data handlers in `api/infra/db/*` encapsulate collection-specific queries and updates. They are not policy engines and not API contract validators. Their goal is stable persistence primitives with predictable input and output shapes. Handlers should expose intentional methods such as `get_sample_by_id`, `list_variants_for_sample`, or `save_report`, instead of requiring callers to build ad hoc query dictionaries repeatedly.

The reason is twofold. First, query behavior should be centralized to maintain MongoDB 3.4 compatibility rules and indexing awareness. Second, repeating ad hoc queries across service code increases inconsistency risk and makes index tuning harder because query patterns become fragmented. If a new query pattern appears in multiple places, add a handler method and use it consistently.

### 3.4 Security and auth modules
Security modules in `api/security/*` own credential checks, session token issuance/decoding, and route dependency access checks. Authentication (`api/security/auth_service.py`) is intentionally co-located with access-control logic (`api/security/access.py`) so route-level policy and session lifecycle evolve together. The design reason is to avoid split-brain semantics where credential logic changes but access dependency behavior lags.

### 3.5 Flask blueprints
Blueprint modules in `coyote/blueprints/*` control page flow, template context assembly, and user interaction handling. They should call API endpoints and render responses, not replicate backend domain logic. They should use integration helpers in `coyote/services/api_client` for URL building and header forwarding, which keeps transport behavior centralized.

A frequent mistake is computing domain decisions in blueprint code because “the UI already has the data.” Avoid this. UI code can perform presentation-level transformation (formatting, grouping for display) but must not become a second business rule engine. When in doubt, move the rule to API service and expose a field indicating resolved state.

The current pattern is to keep route handlers intentionally thin and move repeated API orchestration into focused helper modules (for example `coyote/services/api_client/home.py` and `coyote/services/api_client/reports.py`). View functions should mostly do request parsing, helper invocation, and template/response mapping.

### 3.6 Integration client modules
`coyote/services/api_client/*` modules define transport contracts from Flask to API. Endpoint builders and client wrappers ensure path conventions, headers, and error wrapping stay consistent. If you need a new API call from UI, add endpoint helper methods and keep direct hardcoded URL strings minimized.

This pattern reduces subtle drift such as typo-prone path constants, inconsistent internal token usage, or missing forwarded cookies. Centralized transport also makes global behavior changes simpler, for example adding standard request metadata headers.

## 4. Adding a New FastAPI Endpoint
Adding a new endpoint should be treated as contract design, not just function creation. Start by defining purpose, required permissions, input shape, output shape, and audit implications. Then implement route, service, and tests in sequence.

### Step-by-step pattern
1. Define endpoint contract in terms of path, method, parameters, response shape, and error behavior.
2. Determine required `require_access` constraints.
3. Add route function in appropriate module.
4. Add or extend service function for domain orchestration.
5. Add or extend handler methods if new persistence access is required.
6. Add tests for success, validation failure, unauthorized/forbidden, and not-found/conflict where relevant.
7. Update `docs/API_REFERENCE.md` and `docs/API_ENDPOINT_CATALOG.md`.

### Code example

```python
# api/routes/samples.py
from fastapi import Depends
from api.app import app, require_access
from api.services.samples_context import SamplesContextService

@app.get('/api/v1/samples/{sample_id}/quality/context')
def sample_quality_context(sample_id: str, user=Depends(require_access(min_level=1, permissions=['view_sample']))):
    data = SamplesContextService.get_quality_context(sample_id=sample_id, user=user)
    return {'status': 'ok', 'data': data}
```

```python
# api/core/workflows/samples_context.py
from api.extensions import store
from api.errors.exceptions import AppError

class SamplesContextService:
    @staticmethod
    def get_quality_context(sample_id: str, user):
        sample = store.sample_handler.get_sample(sample_id)
        if not sample:
            raise AppError(status_code=404, message='Sample not found')
        metrics = store.coverage_handler.get_quality_metrics(sample_id)
        return {
            'sample_id': sample_id,
            'assay': sample.get('assay'),
            'metrics': metrics,
            'viewer': user.username,
        }
```

### Why this pattern
The route remains thin and contract-focused, while service owns workflow logic and not-found semantics. If tomorrow the quality context requires more collections or policy-specific transformations, those changes remain in service layer and route contract can stay stable.

### Common mistakes
A recurring mistake is raising raw framework exceptions deep in handlers with inconsistent payloads. Prefer typed application errors and centralized exception normalization. Another mistake is skipping permission checks because endpoint seems “read only.” Read operations can still disclose sensitive clinical data and must be policy-protected.

## 5. Adding a New Flask Blueprint
A new blueprint should represent a coherent UI domain, not a miscellaneous set of unrelated views. When adding a blueprint, define user intent and API dependencies first.

### Step-by-step pattern
1. Create blueprint package under `coyote/blueprints/<domain>/`.
2. Register blueprint in app initialization.
3. Implement view functions that call API endpoints through integration client.
4. Add templates scoped to the domain.
5. Add tests validating boundary behavior and expected rendering context.

### Code example

```python
# coyote/blueprints/qc/__init__.py
from flask import Blueprint

qc_bp = Blueprint('qc_bp', __name__, url_prefix='/qc', template_folder='templates')

from coyote.blueprints.qc import views  # noqa: E402,F401
```

```python
# coyote/blueprints/qc/views.py
from flask import render_template
from flask_login import login_required
from coyote.blueprints.qc import qc_bp
from coyote.services.api_client.api_client import get_web_api_client, forward_headers

@qc_bp.get('/samples/<sample_id>')
@login_required
def qc_sample_page(sample_id: str):
    payload = get_web_api_client().get_json(
        f'/api/v1/samples/{sample_id}/quality/context',
        headers=forward_headers(),
    )
    return render_template('qc/sample.html', context=payload)
```

### Why this pattern
It preserves the UI boundary: UI orchestrates and renders; API decides policy and domain correctness. If the UI needs computed fields, request them explicitly from API instead of replicating service rules.

### Common mistakes
Engineers sometimes add Flask-side direct imports from `api.services` because it seems faster. This is a boundary violation and is blocked by architecture tests. Another mistake is putting endpoint URL strings everywhere in view code; use endpoint helpers where possible.

## 6. Adding a New Schema-Driven Document
Schema-driven documents are powerful and high risk because they can influence runtime behavior broadly. Treat schema additions as governed domain changes with versioning and audit requirements.

### Step-by-step pattern
1. Define schema category and version.
2. Add schema validation logic in backend service.
3. Add admin endpoint(s) for create/update/toggle where needed.
4. Ensure changelog metadata and versioning behavior are included.
5. Add tests for valid and invalid schema payloads.

### Code example

```python
# schema payload example
new_schema = {
    '_id': 'qc_panel_schema_v1',
    'schema_type': 'qc_panel',
    'version': 1,
    'fields': {
        'panel_name': {'type': 'string', 'required': True},
        'min_coverage': {'type': 'int', 'min': 0, 'default': 100},
        'genes': {'type': 'list', 'item_type': 'string', 'default': []},
    },
}
```

```python
# api/core/schema/schema_service.py
from api.errors.exceptions import AppError

class SchemaService:
    @staticmethod
    def validate_schema_payload(payload: dict) -> None:
        required = {'_id', 'schema_type', 'version', 'fields'}
        missing = required - set(payload.keys())
        if missing:
            raise AppError(status_code=400, message='Invalid schema payload', details=f'Missing fields: {sorted(missing)}')
        if not isinstance(payload['fields'], dict) or not payload['fields']:
            raise AppError(status_code=400, message='Invalid schema payload', details='fields must be non-empty object')
```

### Why this pattern
Schema flexibility is useful only when validation and governance remain strict. Without strict validation, schema-driven systems become unpredictable and difficult to debug.

### Common mistakes
Do not allow schema updates without change reason metadata. Do not bypass versioning when “minor” tweaks are made. Small schema changes can alter interpretation workflows in major ways.

## 7. Adding a New Permission Policy
Permission policy additions involve taxonomy, enforcement points, and tests. A permission entry by itself does nothing unless route dependencies and roles use it.

### Step-by-step pattern
1. Define permission identifier and category.
2. Add it to permission registry data.
3. Apply checks in relevant endpoints.
4. Add role mappings where appropriate.
5. Add tests proving allowed and denied behavior.

### Code example

```python
# new permission document
perm = {
    '_id': 'export_qc_report',
    'label': 'Export QC Report',
    'category': 'REPORTING',
    'is_active': True,
}
```

```python
# apply permission in route
@app.post('/api/v1/qc/samples/{sample_id}/report/export')
def export_qc_report(sample_id: str, user=Depends(require_access(min_level=50, permissions=['export_qc_report']))):
    ...
```

### Why this pattern
Permissions should map to concrete actions. If permissions are added without enforcement points, policy data diverges from behavior. If enforcement is added without permission registry updates, governance UI drifts.

### Common mistakes
Avoid vague permissions like `manage_everything`. Prefer granular, operation-specific permissions that map cleanly to endpoint families.

## 8. Adding a New Role
Roles are policy bundles and should be treated as configuration requiring governance, validation, and traceability.

### Step-by-step pattern
1. Define role id and numeric level.
2. Define grants and deny permissions.
3. Validate role document against role schema.
4. Add role tests for key route families.
5. Document role purpose in policy docs.

### Code example

```json
{
  "_id": "qc_reviewer",
  "label": "QC Reviewer",
  "level": 120,
  "permissions": ["view_sample", "view_variant", "export_qc_report"],
  "deny_permissions": ["delete_sample_global"]
}
```

### Why this pattern
Role behavior must be deterministic and explainable. Numeric level is useful for broad precedence checks; explicit permissions are needed for action-level gates.

### Common mistakes
Do not rely only on level thresholds and ignore permissions. Do not forget deny precedence tests when adding new roles.

## 9. Adding a New Audit Event
Audit events are not optional decoration. For privileged or clinically significant operations, event emission is part of correctness.

### Step-by-step pattern
1. Define event type taxonomy entry.
2. Emit event at service authority point.
3. Include actor, entity, action, outcome, timestamp, trace id.
4. Add tests that verify event emission on success and critical failure paths.

### Code example

```python
# service mutation with audit
def classify_variant(sample_id: str, var_id: str, tier: int, user):
    result = store.variant_handler.update_tier(sample_id=sample_id, var_id=var_id, tier=tier)
    emit_audit_event(
        event_type='variant.classify',
        entity_type='variant',
        entity_id=var_id,
        actor_id=user.id,
        result='success' if result else 'failure',
        metadata={'sample_id': sample_id, 'tier': tier},
    )
    return result
```

### Why this pattern
If audit is emitted before operation outcome is known, events become misleading. If emitted too late or outside service authority, events can be missed.

### Common mistakes
Do not include protected clinical payload fields unnecessarily in audit metadata. Include identifiers and action context, not full data dumps.

## 10. Adding a New Assay Group
Assay group additions are system-wide extensions touching schema, workflow logic, routes, reporting, UI, and tests. Treat this as a coordinated change set.

### Step-by-step pattern
1. Define assay metadata and taxonomy.
2. Add assay-specific schema defaults and validation.
3. Implement route and service behavior for assay workflows.
4. Add reporting path/template rules.
5. Add UI navigation and page support.
6. Add role/permission impacts.
7. Add fixtures and integration tests.

### Code example

```python
# api/core/assay/assay_registry.py
ASSAY_GROUPS = {
    'DNA': {'analysis_types': ['SNV', 'CNV', 'TRANSLOC']},
    'RNA': {'analysis_types': ['FUSION']},
    'QC': {'analysis_types': ['COVERAGE', 'QUALITY']},
}
```

```python
# reporting path rule
def report_subpath_for_assay_group(group: str) -> str:
    mapping = {'DNA': 'reports/dna', 'RNA': 'reports/rna', 'QC': 'reports/qc'}
    return mapping.get(group, 'reports/other')
```

### Why this pattern
Assay groups alter workflow semantics broadly. A narrow patch in one route module is insufficient and can leave inconsistent behavior across API/UI/reporting.

### Common mistakes
A frequent mistake is adding assay values in one collection but not updating schema options and UI context endpoints. Another mistake is failing to add report path handling, causing runtime save errors.

## 11. MongoDB Access Patterns and 3.4 Constraints
MongoDB 3.4 compatibility is an architectural constraint, not a temporary inconvenience. Avoid patterns that assume transactions or modern operators unavailable in 3.4.

### Access pattern guidelines
- Use handler methods with intentional query interfaces.
- Keep query predicates aligned with indexed fields.
- Avoid large unbounded scans in interactive routes.
- Prefer explicit projection to reduce payload overhead.
- Keep write sequences deterministic for multi-collection workflows.

### Example handler pattern

```python
class SampleHandler:
    def get_sample(self, sample_id: str):
        return self.col.find_one({'_id': sample_id}, {'_id': 1, 'name': 1, 'assay': 1, 'case_id': 1})

    def list_samples(self, page: int, page_size: int):
        cursor = self.col.find({}, {'_id': 1, 'name': 1}).skip((page - 1) * page_size).limit(page_size)
        return list(cursor)
```

### Why this pattern
Consistency and performance depend on predictable query behavior. Ad hoc query construction in routes/services tends to proliferate and weakens index strategy discipline.

### Common mistakes
Do not assume write atomicity across collections. Do not use unsupported operators and then discover failures only in production-like environments.

## 12. Indexing Guidelines
Indexes should reflect actual query workloads, not speculative patterns. Build index policy from route-family usage and service query signatures.

### Guidelines
- Index sample and case identifiers used in lookup routes.
- Index frequently filtered variant/fusion fields.
- Index report identifiers and sample-report references.
- Index policy lookup fields (`role`, permission id).
- Review slow queries and adjust indexes intentionally.

### Example index definitions

```javascript
db.samples.createIndex({"_id": 1})
db.samples.createIndex({"case_id": 1})
db.variants.createIndex({"SAMPLE_ID": 1, "POS": 1})
db.reports.createIndex({"report_id": 1}, {unique: true})
```

### Why this pattern
Clinical workflow pages rely on predictable latency. Bad indexing causes analyst friction and can trigger unsafe workarounds.

### Common mistakes
Do not add broad compound indexes without confirming query selectivity. Do not leave old indexes unmanaged after query shape changes.

## 13. Logging Conventions
Logging in Coyote3 has two tracks: operational logs and audit logs. They serve different audiences and retention models.

### Operational logs
Operational logs support debugging and runtime monitoring. They should include timestamp, severity, service/module, request correlation id, and concise contextual metadata.

### Audit logs
Audit logs support compliance and forensic review. They should include actor, action, target, outcome, and timestamp with minimal ambiguity.

### Example structured log

```python
logger.info(
    'report_save_completed',
    extra={
        'trace_id': trace_id,
        'sample_id': sample_id,
        'report_id': report_id,
        'actor': user.username,
        'result': 'success',
    },
)
```

### Why this pattern
Unstructured logs are difficult to query and correlate during incidents. Structured logs improve incident response and audit evidence extraction.

### Common mistakes
Do not log raw sensitive payloads. Do not mix audit and operational semantics in one ad hoc log entry.

## 14. Error Handling Strategy
Error behavior should be deterministic and explicit. Use typed application errors for domain and workflow issues, then normalize responses centrally.

### Strategy
- Use `AppError` for expected application-level failures.
- Use clear status codes (`400`, `401`, `403`, `404`, `409`, `500`).
- Keep error payload shape stable.
- Avoid leaking stack traces in client responses.

### Example

```python
if not sample:
    raise AppError(status_code=404, message='Sample not found', details=f'sample_id={sample_id}')
```

### Why this pattern
Stable error contracts simplify UI handling and reduce brittle conditionals. They also improve audit/review quality by standardizing failure semantics.

### Common mistakes
Do not use generic `Exception` with arbitrary messages as client-facing payloads. Do not return inconsistent error key names across route families.

## 15. Naming Conventions
Naming conventions are part of maintainability. Choose names that expose domain intent.

### Guidelines
- Route functions: `<domain>_<action>_<mode>` where helpful.
- Service classes/functions: domain-first naming (`DNAWorkflowService`, `persist_report_and_snapshot`).
- Permission ids: action-oriented (`view_sample`, `export_qc_report`).
- Audit event types: `<domain>.<action>` (`report.save`, `variant.classify`).

### Why this pattern
Clear names reduce onboarding time and review ambiguity. Generic names like `process_data` or `handle_action` are costly in large regulated systems.

### Common mistakes
Avoid abbreviations that hide clinical meaning unless they are standard in the codebase and domain.

## 16. Configuration Strategy
Configuration must be explicit, environment-specific, and secret-safe.

### Strategy
- Keep non-secret defaults in environment files or config modules.
- Inject secrets via environment or secret manager.
- Separate dev and prod behavior with explicit profile values.
- Avoid silent fallback secrets in production.

### Example configuration categories

```env
# runtime
ENV_NAME=production
API_BASE_URL=http://api:8001

# security
SECRET_KEY=<redacted>
INTERNAL_API_TOKEN=<redacted>

# data
MONGO_URI=mongodb://mongo:27017/coyote3

# reporting
REPORTS_BASE_PATH=/data/reports
```

### Why this pattern
Configuration drift causes subtle production failures. Explicit categories and validation checks reduce misconfiguration risk.

### Common mistakes
Do not overload one setting for unrelated behaviors. Do not commit production secrets in env files.

## 17. Testing Each Layer
A robust test strategy must prove behavior, contracts, and boundaries.

### 17.1 Service tests
Service tests verify domain orchestration, validation, and error branches with mocked handlers.

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/unit
```

### 17.2 Route-family tests
Route tests validate endpoint behavior and policy gates.

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/api/routes
```

### 17.3 Architecture guardrails
Boundary and security tests prevent structural regressions.

```bash
PYTHONPATH=. .venv/bin/pytest -q tests/api/test_api_route_security.py tests/web/test_web_api_boundary.py
```

### 17.4 Full coverage runs

```bash
PYTHONPATH=. .venv/bin/pytest -q tests --cov=api --cov=coyote --cov-report=term-missing --cov-report=xml
```

### Why this pattern
Each layer test type answers different risk questions. Combining all types gives strong confidence that behavior and architecture remain aligned.

### Common mistakes
Do not rely only on happy-path route tests. Do not skip permission-negative tests when adding endpoints.

## 18. Debugging Common Issues
Debugging should start with layer isolation and deterministic reproduction.

### Common issue: 403 on expected action
- Check role grants and deny permissions.
- Check route dependency requirements.
- Verify session user context from `/api/v1/auth/whoami`.

### Common issue: report save fails with conflict
- Verify report id/path generation logic.
- Check file existence and permissions.
- Confirm expected conflict handling behavior.

### Common issue: UI page breaks after API change
- Compare API response contract to template expectations.
- Review integration helper endpoint path usage.
- Add/adjust contract tests and template context assertions.

### Common issue: slow list endpoints
- Capture query pattern from handler.
- Verify supporting indexes.
- Check page size and filter behavior.

### Debugging pattern
1. Reproduce with exact input identifiers.
2. Identify failing layer.
3. Verify policy context.
4. Inspect service logic and handler query.
5. Add regression test before final fix.

## 19. CI/CD Expectations
CI/CD pipeline should enforce structural and behavioral quality gates.

### Required pipeline stages
1. dependency install and environment validation
2. compile/import checks
3. tests (service, route, guardrails)
4. coverage generation
5. documentation impact checks
6. optional mutation and performance checks (scheduled)

### Example CI command sequence

```bash
PYTHONPATH=. .venv/bin/python -m compileall -q api coyote tests
PYTHONPATH=. .venv/bin/pytest -q tests
PYTHONPATH=. .venv/bin/pytest -q tests --cov=api --cov=coyote --cov-report=xml
```

### Why this pattern
CI should catch not just syntax errors but architectural regressions. If boundary tests fail, merges should stop because those failures indicate structural risk.

### Common mistakes
Do not treat docs as optional in CI for architecture-impacting changes. Do not allow unreviewed permission model changes into production branches.

## 20. Extension Boundaries and Anti-Patterns
Extension boundaries exist to keep the platform coherent as it grows.

### Boundaries
- UI cannot own backend domain policy.
- Route modules cannot become orchestration monoliths.
- Handlers cannot embed authorization semantics.
- Utility modules cannot silently absorb domain behavior.

### Anti-patterns
- Direct `coyote` imports from `api` internals and vice versa for business logic.
- Copy-pasted query dictionaries in routes.
- Inconsistent error payload structures.
- Permission additions without route checks and tests.

### Why boundaries matter
Most production regressions in split-stack systems are boundary regressions, not algorithm regressions. Holding boundaries reduces emergent complexity and improves predictability.

## 21. Operational Mentoring Notes for New Backend Engineers
You are expected to prioritize clarity and deterministic behavior over cleverness. If you can implement a feature with less code by bypassing service decomposition, do not assume that is better. Simpler code at one layer often creates hidden complexity in policy validation and future maintenance. A valuable heuristic is to ask: can another engineer trace this workflow from endpoint to persistence and understand all authorization and audit points in one pass? If not, refactor before merging.

Another important habit is writing tests that reflect clinical risk rather than just code paths. When you add a new mutation endpoint, include tests for denied permissions, malformed payloads, not-found entities, and conflicting states. Happy-path tests are necessary but insufficient. The system should fail predictably and safely under bad inputs and constrained policies.

Finally, when you are uncertain about ownership or design direction, prefer explicit consultation and documentation updates over silent local decisions. Architectural consistency across contributors is the strongest long-term performance optimization this platform can have.

## 22. Future Evolution Considerations
The current architecture provides a stable and governed foundation, but planned evolution should occur in controlled stages. Immediate priorities include deepening coverage on large route and service modules, adding machine-generated API contract artifacts, and formalizing isolated mutation testing workflows. Mid-term evolution should include controlled Mongo upgrade planning, asynchronous processing for heavy non-interactive operations, and stronger policy-as-code experiments for explainable authorization. Long-term evolution can include domain-oriented service decomposition where load and ownership justify it, immutable signed audit streams, and stronger external integration tooling with generated SDKs.

## 23. Advanced Operational Diagnostics for Backend Engineers
When you are debugging in production-like environments, you should avoid random exploratory changes and instead follow a diagnostic chain that maps to architecture boundaries. The first step is always to identify whether the symptom is contract-level, policy-level, orchestration-level, or persistence-level. A page error in the browser does not mean the bug is in Flask. It can be a backend contract mismatch, an authorization failure, a data-shape evolution issue, or a report-file path collision. A disciplined diagnostic path prevents wasted time and reduces the risk of introducing secondary regressions while chasing the wrong layer.

Start by identifying the exact endpoint call and response status. If status is `401` or `403`, inspect actor context, required permission set, and deny overlays before inspecting domain logic. If status is `400`, inspect payload contract and schema-driven validation behavior first, because malformed request shape should fail before domain persistence logic is reached. If status is `500`, inspect service orchestration logs and handler interactions in sequence rather than jumping directly to database assumptions. When status is `200` but UI displays wrong information, compare response payload fields to template expectations and check whether new optional fields introduced by API changes are handled in templates with sensible defaults.

You should also use correlation identifiers aggressively. Every request should produce log records that can be stitched across UI and API layers. If that is not currently fully implemented for a route family, prioritize adding it rather than adding temporary print debugging. In incident review, correlation IDs reduce ambiguity and allow faster evidence generation for operational and audit stakeholders. Engineers often underestimate the value of this until they have to reconstruct a multi-step failure across dozens of logs under time pressure.

### Diagnostic command examples

```bash
# Run targeted failing suite after reproducing issue in tests
PYTHONPATH=. .venv/bin/pytest -q tests/api/routes/test_reports_routes.py -k "save"

# Validate import/compile health after refactor
PYTHONPATH=. .venv/bin/python -m compileall -q api coyote tests

# Re-run full regression after fix
PYTHONPATH=. .venv/bin/pytest -q tests
```

## 24. Data Migration and Backward-Compatible Change Playbook
Data-shape changes in Coyote3 must be treated as migration programs, not incidental commits. Because MongoDB 3.4 compatibility constraints prevent transactional multi-document operations at modern levels, migrations must be phased with explicit compatibility windows and rollback logic. The recommended method is additive-first evolution, dual-shape read support, controlled backfill, validation, and only then removal of legacy handling. This may feel slower than direct rewrite patterns, but it dramatically reduces production breakage risk in clinical workflows.

When adding a field that becomes required in future behavior, introduce it first as optional with safe defaults and ensure all downstream code paths can handle both old and new documents. Then implement migration script(s) with read-only dry-run mode and explicit batch sizing controls. Dry-run output should show counts for documents eligible for update, documents skipped by predicate, and potential anomalies. You should not run write migration scripts in production until dry-run evidence is reviewed and rollback assumptions are documented.

After migration execution, run validation queries and route-level smoke checks. Validation should include both direct collection checks and endpoint-level behavior checks, because schema correctness is necessary but not sufficient; API contracts and UI rendering must remain coherent. Only after this validation window should you remove legacy-path handling from services and templates. In practice, leaving compatibility paths indefinitely creates confusion and increases cognitive load, so deprecate intentionally with a tracked removal date.

### Migration script pattern example

```python
# migration_scripts/add_qc_defaults.py
from api.extensions import store

DRY_RUN = True
BATCH_SIZE = 500


def run():
    query = {'assay': 'QC', 'filters.min_quality': {'$exists': False}}
    cursor = store.sample_handler.collection.find(query, {'_id': 1}).limit(BATCH_SIZE)
    targets = [doc['_id'] for doc in cursor]
    print({'eligible': len(targets), 'dry_run': DRY_RUN})
    if DRY_RUN:
        return
    for sid in targets:
        store.sample_handler.collection.update_one({'_id': sid}, {'$set': {'filters.min_quality': 20}})


if __name__ == '__main__':
    run()
```

## 25. CI/CD Pipeline Implementation Detail and Governance Expectations
A robust CI/CD design for Coyote3 is not limited to test execution. It should enforce architecture integrity, policy correctness, and documentation consistency. Your pipeline should run deterministic stages with fail-fast behavior for critical controls. An effective order is: environment preparation, static checks, compile checks, test matrix, coverage generation, artifact publication, and deployment gate decisions. This ordering surfaces structural failures early and avoids wasting compute on full test matrices when imports or syntax are broken.

You should also separate blocking and advisory checks. For example, boundary tests, route protection tests, and regression tests should be blocking, while longer-running mutation or extended performance suites can run on schedule or as pre-release gates. This avoids slowing daily development excessively while preserving high-confidence release workflows. In regulated contexts, release gate criteria should be explicit, documented, and reviewed periodically; implicit “looks good” decisions are insufficient.

Documentation change detection should be integrated into CI policy. If an endpoint contract changes or a permission model changes, pipeline should require corresponding documentation updates. This can be lightweight at first, such as path-based checks and PR templates requiring explicit “docs impact” fields. Over time, you can evolve this into structured traceability checks where requirement IDs map to tests and docs sections.

### Example CI pseudo-workflow

```yaml
name: coyote3-ci

on: [pull_request]

jobs:
  quality:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python -m venv .venv
      - run: .venv/bin/pip install -r requirements.txt
      - run: PYTHONPATH=. .venv/bin/python -m compileall -q api coyote tests
      - run: PYTHONPATH=. .venv/bin/pytest -q tests
      - run: PYTHONPATH=. .venv/bin/pytest -q tests --cov=api --cov=coyote --cov-report=xml
      - run: test -f docs/DEVELOPER_GUIDE.md
```

### Governance expectations
Release approval in Coyote3 should include evidence bundles, not only commit hashes. A minimal evidence bundle includes test results, coverage output, notable risk annotations, and docs impact statement. For policy-sensitive changes, include access matrix diff and audit event behavior confirmation. For reporting changes, include deterministic preview/save validation evidence. This level of rigor may appear heavy compared with startup-style pipelines, but it is appropriate for clinical environments where operational mistakes can propagate beyond engineering boundaries.

## 26. Code Review Standards and Frequent Failure Modes
Code review in Coyote3 should explicitly evaluate architecture boundaries and policy integrity, not only coding style and test pass status. A useful review checklist is to ask: does this change introduce domain logic in UI layer, does this route remain thin and contract-oriented, are policy checks explicit, are error payloads deterministic, does audit emission exist where state changes occur, and are tests proving both positive and negative access paths. If any answer is uncertain, request revision before merge.

A frequent failure mode is “quiet coupling,” where a developer adds a helpful shortcut that bypasses established flow, such as reading a collection directly inside a service that should call a handler abstraction or importing backend helper logic from a UI blueprint to avoid adding an endpoint. These changes may work initially but create hard-to-track technical debt and can break future refactors. Another failure mode is “partial extension,” where one part of a feature is implemented (for example, permission added in registry) but enforcement or tests are missing, creating mismatch between governance data and runtime behavior.

Reviewers should also look for data-shape assumptions that are not backward-safe. If a service now assumes a new field always exists, reviewer should ask whether migration and dual-shape compatibility are handled. This is especially important under MongoDB 3.4 compatibility where legacy documents may persist for longer than expected. It is safer to explicitly normalize fields in workflow services than to rely on optimistic assumptions that all documents were backfilled.

Finally, reviewers should demand clear naming and explicit intent in function design. Ambiguous naming is not a stylistic nit in this codebase; it creates architecture drift. If a function is called `update_data`, ask what data and what policy context. If a route returns a payload called `context`, ask what fields and contractual guarantees are expected. Precision in naming and contracts is one of the cheapest forms of risk reduction available to engineering teams.

## 27. Additional Future Evolution Considerations for Developer Workflow
Developer workflow should evolve toward higher automation while preserving human review for policy-critical changes. One practical direction is auto-generated endpoint catalogs and contract examples from current route decorators and OpenAPI outputs, reducing documentation drift. Another direction is structured linting for architecture boundaries, such as static checks preventing imports across forbidden layer boundaries or validating event type taxonomy consistency. These investments reduce reviewer burden and make quality controls more scalable as contributor count grows.

Mutation testing should remain isolated from primary virtual environment to avoid dependency conflicts, but it should still become a recurring quality signal for high-risk modules. A scheduled non-blocking mutation pipeline can surface weak assertions in authorization, reporting, and schema validation paths. Over time, as confidence and tooling mature, selected mutation thresholds can become release advisories for critical modules. This approach balances practicality with meaningful quality improvement.

The long-term engineering objective is not maximum complexity or maximum abstraction. It is controlled evolvability. Coyote3 should remain understandable to new senior engineers while scaling in capability. That requires regular pruning of obsolete compatibility paths, disciplined documentation updates, and periodic review of architecture decisions against operational evidence. Engineers who keep those principles in mind will build features faster in the long run, because they will spend less time untangling accidental complexity and more time delivering reliable workflow improvements.
