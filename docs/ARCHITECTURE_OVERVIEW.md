# Coyote3 Architecture Manual

## Audience and Purpose
This manual is written for senior backend engineers onboarding to Coyote3, a production clinical genomics platform operating in a regulated environment. The document is intentionally detailed and operationally oriented. It explains architectural structure, ownership boundaries, policy mechanisms, consistency rules, and extension patterns with emphasis on why specific decisions were taken under clinical, security, and backward-compatibility constraints.

Coyote3 contains three foundational runtime units: a Flask-based web application, a FastAPI backend API, and a MongoDB datastore constrained to MongoDB 3.4 compatibility. Around those runtime units, the platform implements role-based access control, audit event generation, schema-driven dynamic configuration, versioned document lifecycle with rewind capability, and Docker-driven deployment patterns.

This architecture should not be read as a static model. It is a controlled operating framework. The system must evolve as assays evolve, clinical policy evolves, and infrastructure evolves. The architecture therefore prioritizes explicit contracts, deterministic behavior, and auditable state transitions over convenience patterns that hide side effects.

---

## 1. System Context (C4 Style)
### Concept explanation
At context level, Coyote3 is a bounded clinical software system placed between human decision-makers and genomic data persistence. It is not only a user-facing workflow application; it is an accountability and traceability boundary for clinically meaningful operations. The principal actors are analysts, clinical geneticists/pathologists, administrators, and auditors. Each actor has distinct responsibilities and corresponding access surfaces.

In C4 terms, the context diagram is expressed textually as follows:

```text
[Clinical Analyst / Doctor / Admin / Auditor]
                |
                v
          [Coyote3 Web UI]
                |
                v
          [Coyote3 API Service]
                |
                v
             [MongoDB]
                |
                +--> [Audit + Operational Logging Infrastructure]
```

The key architectural statement at this level is that clinically significant actions must pass through a single policy enforcement surface before data mutation or report persistence occurs. In Coyote3, that surface is the API service.

### Design reasoning
Clinical software architecture must optimize for reproducibility, explainability, and controlled failure behavior. Context-level centralization of business policy in API service prevents policy drift that can occur when presentation code embeds access or domain logic. It also allows consistent treatment of current and future clients, including non-web consumers.

The web UI remains important, but it is intentionally treated as an orchestration client for user interaction and templating, not a policy authority. This prevents hidden pathways to state mutation and keeps audit semantics coherent.

### Tradeoffs
This context model introduces additional integration contracts. UI and API need strong alignment. Breakage can occur if API response shapes change without UI adaptation. However, this tradeoff is preferred because it keeps authorization, validation, and workflow side effects centralized and testable.

### Alternatives considered
A Flask-monolith architecture was considered in early evolution stages. It simplifies runtime topology but tends to distribute policy logic across views, helpers, and templates. That pattern weakens audit confidence and complicates external integration. A separate SPA front end was also considered, but current institutional constraints and existing rendering model favored Flask UI continuity.

### Implementation pattern
System-level flow:
1. User initiates workflow action in UI.
2. UI invokes API endpoint with session context.
3. API validates authentication and authorization.
4. API orchestrates domain services and persistence handlers.
5. API emits audit event and returns deterministic response.

### Example configuration

```env
API_BASE_URL=http://api:8001
MONGO_URI=mongodb://mongo:27017/coyote3
INTERNAL_API_TOKEN=<redacted>
REPORTS_BASE_PATH=/data/reports
```

---

## 2. Container Architecture
### Concept explanation
Container architecture defines deployable process boundaries and runtime responsibilities. Coyote3 has a minimum three-container topology: `web` (Flask), `api` (FastAPI), and `mongo` (MongoDB 3.4 compatible). Optional containers include ingress proxy, centralized logging collectors, and monitoring agents.

The Flask container owns user navigation and templating behavior. The FastAPI container owns contract validation, policy enforcement, and domain workflow orchestration. MongoDB owns persistence. This is a strict role partition that underpins auditability and maintainability.

### Design reasoning
Explicit container boundaries produce operational observability clarity. API latency, policy-denial rates, report save failures, and UI rendering metrics can be monitored independently. During incidents, this improves fault isolation and recovery speed.

Container boundaries also reduce blast radius for changes. For example, a CSS/template deployment does not require backend service logic redeployment. Conversely, backend rule changes can be validated through API smoke suites independently of UI asset changes.

### Tradeoffs
Containerization increases operational complexity: environment management, networking, health check coordination, and release ordering. These costs are acceptable in regulated systems because auditable behavior and deterministic deployment discipline are higher priorities than minimal process count.

### Alternatives considered
Single-process deployment was considered and rejected due to boundary collapse risk. Full microservice decomposition per domain was considered and deferred; given current MongoDB constraints and operational maturity, distributed consistency complexity would outweigh immediate benefits.

### Implementation pattern
Canonical deployment sequence:
1. Start MongoDB and verify readiness.
2. Start API and verify `/api/v1/health`.
3. Start Web and verify UI-to-API connectivity.
4. Execute workflow smoke checks (auth, sample read, report preview/save).

### Example Compose structure

```yaml
services:
  api:
    command: uvicorn api.app:app --host 0.0.0.0 --port 8001
    environment:
      - MONGO_URI=${MONGO_URI}
      - INTERNAL_API_TOKEN=${INTERNAL_API_TOKEN}

  web:
    command: gunicorn "coyote:create_app()"
    environment:
      - API_BASE_URL=http://api:8001
      - SECRET_KEY=${SECRET_KEY}
    depends_on:
      - api

  mongo:
    image: mongo:3.4
```

---

## 3. Component Breakdown
### Concept explanation
Within each container, Coyote3 uses component decomposition to enforce ownership and testability. Backend components are organized around route adapters, services, persistence handlers, domain models, and error primitives. UI components are organized around blueprints, templates, filters, and API integration transport.

This decomposition exists to keep sensitive responsibilities explicit. Route handlers should not become business engines. Templates should not become persistence orchestrators. Data handlers should not implement policy semantics.

### Design reasoning
Component decomposition reduces accidental coupling and simplifies review. In regulated systems, code review is not only correctness-oriented; it is evidence-oriented. Reviewers must trace policy checks, audit emission, and state transitions cleanly.

### Tradeoffs
Fine-grained decomposition can increase navigation depth in the codebase. Engineers may traverse routes, services, and handlers for a single user action. This is a manageable cost when naming conventions and route-family documentation are strong.

### Alternatives considered
Large “utility” modules and multi-purpose controller files were evaluated and avoided as default patterns because they typically become unbounded and difficult to reason about.

### Implementation pattern
Backend decomposition:
- `api/routes/*`: request parsing, dependency wiring, response shaping.
- `api/services/*`: orchestration, workflow rules, policy-sensitive decisions.
- `api/db/*`: collection-specific query/write operations.
- `api/domain/*`: shared domain structures.
- `api/errors/*`: typed application exception model.

UI decomposition:
- `coyote/blueprints/*`: page-level composition.
- `coyote/templates/*`: rendering assets.
- `coyote/services/api_client/*`: transport abstractions.

### Example route-service split

```python
@app.post('/api/v1/dna/samples/{sample_id}/report/save')
def save_report(sample_id: str, payload: dict, user=Depends(require_access(...))):
    return dna_report_service.save(sample_id=sample_id, payload=payload, user=user)
```

---

## 4. Authentication and Session Ownership Model
### Concept explanation
Authentication identifies the actor. Session ownership defines which layer is authoritative for session validity and identity context. In Coyote3, API is authoritative for authenticated user context used in permission decisions. UI mediates session transport and user experience.

### Design reasoning
Centralized authentication semantics prevent divergence between UI and API behavior. If UI were authoritative for session state while API were authoritative for data policy, edge cases would emerge where UI believes a user is valid while API does not, or vice versa. This ambiguity is unacceptable for clinical actions.

### Tradeoffs
The UI is dependent on API-auth semantics and token/cookie propagation behavior. Additional integration tests are required to guarantee stable login/logout/whoami patterns.

### Alternatives considered
A purely UI-owned session model was rejected because it weakens API client extensibility and can force policy duplication. Token-only detached client model was considered but requires additional revocation and lifecycle complexity not necessary for current operational scope.

### Implementation pattern
1. User posts credentials.
2. API validates and issues session token/cookie.
3. UI stores and forwards request headers/cookies.
4. API dependency resolves actor each request.
5. Logout invalidates session representation.

### Example authentication endpoint pattern

```python
@app.post('/api/v1/auth/login')
def auth_login(payload: ApiAuthLoginRequest):
    user_doc = authenticate_credentials(payload.username, payload.password)
    if not user_doc:
        raise HTTPException(status_code=401, detail={'status': 401, 'error': 'Invalid credentials'})
    token = create_api_session_token(str(user_doc['_id']))
    response = JSONResponse({'status': 'ok', 'session_token': token})
    response.set_cookie('api_session', token, httponly=True, secure=True, samesite='lax')
    return response
```

---

## 5. Permission Evaluation Flow
### Concept explanation
Permission evaluation in Coyote3 uses a layered RBAC model: role grants, explicit user grants, explicit denies, and optional minimum access-level constraints. Deny precedence is explicit and mandatory.

### Design reasoning
Clinical organizations often require broad role templates with targeted exceptions. Deny precedence ensures safety when role defaults are broad. Access level constraints provide coarse control; explicit permissions provide operation-level control.

### Tradeoffs
Policy complexity increases test burden and review burden. Without disciplined access-matrix testing, regressions are likely. This burden is an intentional architectural cost.

### Alternatives considered
Flat ACL-only patterns were considered but become difficult to maintain with evolving organizational structures. ABAC was considered for future but deferred due to policy and implementation complexity.

### Implementation pattern
Policy evaluation sequence:
1. Resolve actor and role.
2. Compute effective grants.
3. Apply deny set.
4. Validate required permissions.
5. Validate required level.
6. Return deterministic authorization error on failure.

### Example dependency implementation

```python
def require_access(min_level: int = 0, permissions: list[str] | None = None):
    def _dep(user: ApiUser = Depends(get_current_user)):
        if user.access_level < min_level:
            raise HTTPException(status_code=403, detail={'status': 403, 'error': 'Insufficient level'})
        needed = set(permissions or [])
        effective = set(user.permissions) - set(user.denied_permissions)
        if not needed.issubset(effective):
            missing = sorted(needed - effective)
            raise HTTPException(status_code=403, detail={'status': 403, 'error': f'Missing permission: {missing}'})
        return user
    return _dep
```

---

## 6. Schema-Driven Rendering Pipeline
### Concept explanation
Coyote3 uses schema-driven dynamic configuration for selected admin and workflow surfaces. Schemas define field structures, options, defaults, and constraints consumed by UI and validated by API.

### Design reasoning
Assay and governance configuration evolves rapidly in genomics programs. A schema-driven model allows controlled runtime flexibility while preserving backend validation authority.

### Tradeoffs
Dynamic behavior introduces complexity in validation and change governance. Malformed schema updates can affect multiple workflows. Therefore schema updates are treated as governed, versioned changes, not casual edits.

### Alternatives considered
Purely hardcoded forms were considered simpler for type safety but too rigid operationally. Full client-side dynamic rendering without backend schema validation was rejected as unsafe.

### Implementation pattern
1. Schema definitions stored in versioned collection.
2. UI requests schema context from API.
3. UI renders form elements from schema.
4. Submission sent to API.
5. API validates payload against schema and policy.

### Example schema document

```json
{
  "_id": "rbac_role_schema_v1",
  "schema_type": "rbac_role",
  "version": 1,
  "fields": {
    "permissions": {"type": "list", "default": []},
    "deny_permissions": {"type": "list", "default": []}
  }
}
```

---

## 7. Versioning and Rewind Mechanism
### Concept explanation
Versioning preserves historical states of governed entities. Rewind applies a prior state as a new current revision without deleting history. This is critical for correction workflows under compliance constraints.

### Design reasoning
Operational mistakes are inevitable even with review controls. Rewind allows safe correction while preserving complete provenance. In clinical contexts, “undo” must be explainable and attributable.

### Tradeoffs
Versioning increases storage and complexity. Engineers must consistently include actor, timestamp, and change reason metadata.

### Alternatives considered
Destructive overwrite was rejected due to audit risk. Full event sourcing was considered but postponed due to migration overhead and infrastructure complexity.

### Implementation pattern
- Update operation: append revision metadata.
- Rewind operation: load target revision, apply as new current revision, append rewind event.
- Keep historical chain intact.

### Example changelog event

```json
{
  "entity_id": "aspc_wgs_v3",
  "action": "rewind",
  "from_revision": 14,
  "to_revision": 12,
  "reason": "Validated rollback after incorrect thresholds",
  "actor": "admin_user",
  "timestamp": "2026-03-03T12:00:00Z"
}
```

---

## 8. Audit Event Lifecycle
### Concept explanation
Audit lifecycle includes event creation, context enrichment, persistence, retention, and retrieval. Audit events capture who did what, to which entity, when, and with what outcome.

### Design reasoning
Service-layer audit emission ensures events represent true business actions, not UI intent only. This distinction is essential for forensic clarity.

### Tradeoffs
Strict audit requirements impose engineering discipline. Every privileged action path must include audit behavior and tests.

### Alternatives considered
Database-trigger-only auditing was considered but rejected due to insufficient business context and reduced portability under MongoDB constraints.

### Implementation pattern
1. Authorized action enters service.
2. Service executes mutation/read event.
3. Service emits structured audit event.
4. Event persisted and/or forwarded.
5. Event retrieval controlled by policy.

### Example event envelope

```json
{
  "event_type": "report.save",
  "entity_type": "report",
  "entity_id": "RID-20260303-0001",
  "actor_id": "u42",
  "result": "success",
  "trace_id": "req-abc-123",
  "timestamp": "2026-03-03T18:20:00Z",
  "metadata": {"sample_id": "SAMPLE_001"}
}
```

---

## 9. UI–API Interaction Model
### Concept explanation
UI–API interaction model defines how Flask consumes FastAPI contracts and translates them to page rendering behavior. UI must not introduce policy authority or persistence side effects outside API calls.

### Design reasoning
Centralizing business logic and policy in API ensures consistent behavior across UI pages and future programmatic clients.

### Tradeoffs
UI and API must maintain strict contract synchronization. Breaking changes require coordinated rollout and integration testing.

### Alternatives considered
Direct UI-to-database patterns were rejected due to policy bypass and traceability weaknesses. Dual-logic validation models were rejected due to drift risk.

### Implementation pattern
- UI builds endpoint path via helper builders.
- UI forwards controlled session headers/cookies.
- UI renders API payloads via templates.
- API errors are mapped to user-safe messages.

### Example UI client usage

```python
payload = get_web_api_client().get_json(
    '/api/v1/home/samples/SAMPLE_001/edit_context',
    headers=forward_headers(),
)
return render_template('home/edit_sample.html', context=payload)
```

---

## 10. Data Consistency Strategy
### Concept explanation
Under MongoDB 3.4, multi-document transactions are unavailable. Coyote3 consistency strategy therefore relies on ordered write orchestration, idempotent identifiers, explicit error handling, and reconciliation procedures.

### Design reasoning
Clinical reporting workflows often cross multiple collections and file artifacts. Consistency must be preserved without assuming transactional atomicity.

### Tradeoffs
Application-level consistency logic is more complex and requires careful testing. This complexity is accepted to preserve compatibility constraints.

### Alternatives considered
Immediate migration to transactional data platform was considered but not adopted due to infrastructure and migration risk.

### Implementation pattern
1. Validate preconditions.
2. Execute ordered writes.
3. Abort on first critical failure.
4. Emit failure audit event with context.
5. Trigger reconciliation path where needed.

### Example report persistence sequence

```python
prepare_report_output(report_path, report_file)
if not write_report(html, report_file):
    raise AppError(500, 'Failed to write report')
report_oid = save_report_metadata(...)
bulk_upsert_snapshot_rows(report_oid=report_oid, rows=snapshot_rows or [])
```

---

## 11. Performance Considerations
### Concept explanation
Performance in Coyote3 is managed as controlled responsiveness under policy and audit constraints. The system values deterministic behavior and bounded workloads over raw throughput metrics.

### Design reasoning
Clinical workflows involve repeated list/search operations and context rendering. Hot paths must be index-aware and paginated.

### Tradeoffs
Strong validation and policy checks add overhead. This is accepted to maintain safety and traceability.

### Alternatives considered
Aggressive cache-everywhere strategies were considered but rejected for policy-sensitive and frequently evolving data.

### Implementation pattern
- index-driven query plans
- bounded result sets with pagination
- avoid N+1 handler calls
- monitor latency percentiles by route family

### Example response pagination

```json
{
  "status": "ok",
  "data": [...],
  "pagination": {"page": 1, "page_size": 50, "total": 117, "pages": 3}
}
```

---

## 12. Backward Compatibility Constraints
### Concept explanation
Compatibility constraints ensure existing workflows, data shapes, and integrations remain functional during iterative evolution.

### Design reasoning
Clinical operations cannot tolerate frequent breaking change cascades. Coyote3 uses additive evolution patterns and explicit deprecation windows.

### Tradeoffs
Some modern features are delayed due to compatibility policy. This is deliberate risk management.

### Alternatives considered
Break-and-migrate major upgrades were considered but rejected for routine change cycles.

### Implementation pattern
- additive schema changes first
- dual-shape read support during migration windows
- documented deprecation and removal criteria
- migration scripts with validation and rollback

### Example deprecation policy

```text
Mark endpoint deprecated -> provide replacement -> maintain compatibility window -> remove after validated migration closure
```

---

## 13. Scaling Considerations
### Concept explanation
Scaling strategy addresses throughput growth while preserving policy correctness and audit fidelity. Scaling is not solely about replicas; it includes query design, workload partitioning, and observability discipline.

### Design reasoning
As sample volume grows, route families such as DNA variant listing and report generation become performance-sensitive. Scaling must not bypass authorization checks or degrade audit completeness.

### Tradeoffs
Horizontal scaling increases distributed debugging complexity and may expose race conditions if idempotency is weak.

### Alternatives considered
Premature domain microservice split was considered and deferred to avoid distributed consistency overhead under current constraints.

### Implementation pattern
- scale API replicas behind load balancer
- preserve stateless request handling where possible
- optimize indexes and page sizes
- introduce asynchronous processing for heavy non-interactive workloads

### Example scaling snippet

```yaml
api:
  deploy:
    replicas: 3
  resources:
    limits:
      cpus: '2.0'
      memory: 2G
```

---

## 14. Failure Scenarios and Recovery
### Concept explanation
Failure architecture in Coyote3 includes detection, containment, recovery, verification, and evidence preservation. Failure handling is designed to avoid ambiguous partial success outcomes.

### Design reasoning
Clinical systems require explicit failure semantics. Silent fallback behavior can create hidden divergence between expected and actual state.

### Tradeoffs
Users and operators may see stricter explicit errors. This is preferable to hidden data integrity risk.

### Alternatives considered
Best-effort retries without explicit conflict/error signaling were rejected due to traceability concerns.

### Implementation pattern
- typed application errors
- deterministic HTTP status and payloads
- conflict detection (`409`) for report/file collisions
- rollback and restore runbooks
- post-incident regression test additions

### Example conflict check

```python
if os.path.exists(report_file):
    raise AppError(status_code=409, message='Report already exists', details=report_file)
```

Recovery sequence:
1. classify incident
2. contain scope
3. restore consistency
4. verify critical workflows
5. archive incident evidence

---

## 15. Future Evolution Strategy
### Concept explanation
Future evolution strategy defines phased modernization while preserving production stability and compliance posture.

### Design reasoning
Regulated systems should evolve through controlled increments rather than disruptive rewrites. Each phase must maintain audit continuity and compatibility guarantees.

### Tradeoffs
Incremental modernization is slower but lower risk than all-at-once transformation.

### Alternatives considered
Immediate architectural rewrite to distributed services was considered and deferred pending stronger policy tooling and migration readiness.

### Implementation pattern
Near-term:
1. increase coverage on large route/service modules
2. automate API contract artifact generation
3. add mutation testing in isolated pipeline
4. formalize traceability evidence bundles

Mid-term:
1. Mongo upgrade path with staged compatibility checks
2. asynchronous workflow support for heavy compute paths
3. policy-as-code experimentation for explainable authorization

Long-term:
1. domain service decomposition where justified
2. signed immutable audit streams
3. external API consumer governance model with SDK lifecycle

### Example evolution gate checklist

```text
- compatibility impact reviewed
- migration and rollback plan approved
- audit event changes validated
- security review completed
- tests and docs updated together
```

## Assumptions
ASSUMPTION:
- API major version remains `/api/v1` for current integration surfaces.
- MongoDB 3.4 compatibility remains mandatory in current deployment envelope.
- Identity verification integration is organization-managed but consumed through API auth services.

---

## 16. End-to-End Sequence Narratives for Critical Clinical Flows
### Concept explanation
Architecture quality in regulated systems is not proven by static module diagrams alone. It is proven by deterministic behavior over complete workflows, including nominal and non-nominal paths. For Coyote3, sequence narratives are necessary because the most critical risk surfaces are distributed across authentication, policy evaluation, domain orchestration, persistence, and report lifecycle handling.

The following sequences are presented as architecture-level contracts. Any code change affecting these sequences must be treated as architecture-impacting and must include test and documentation updates.

#### 16.1 Sequence: Analyst opens DNA sample context
```text
User -> Flask route (/dna/...)
Flask -> API (/api/v1/dna/samples/{sample_id}/variants)
API -> auth dependency
API -> RBAC dependency
API -> DNA service orchestration
DNA service -> data handlers (samples, variants, config)
API <- aggregated payload
Flask <- payload
Flask -> template render
User <- rendered context
```

### Design reasoning
This sequence ensures that every clinically relevant list/detail view is policy-checked at API layer before data retrieval output is returned. Even if a UI route exists, it cannot serve unauthorized clinical context without API approval. That model is essential for segregation of duties and minimizes accidental leakage through template-level code.

A second design property is that service orchestration composes data from multiple handlers before returning context. This avoids route-level data assembly complexity and allows domain-centric testability.

### Tradeoffs
The sequence introduces latency overhead because each request includes auth and policy checks, plus potentially several data handler calls. This is accepted because bypassing those checks is a security and compliance risk. The architecture therefore favors secure determinism over unchecked rendering speed.

### Alternatives considered
A direct UI-to-read-model pattern (where precomputed denormalized documents are fetched directly from Flask) was considered. It would reduce request depth but significantly increases the risk of policy bypass and stale policy behavior, because policy decisions would be weakly coupled to retrieval paths.

### Implementation pattern
- API route dependencies enforce auth and permission first.
- Service layer normalizes filters and query context.
- Data handlers provide indexed retrieval.
- API returns stable contract envelope.
- UI renders without reinterpreting policy semantics.

### Example route-to-service orchestration

```python
@app.get('/api/v1/dna/samples/{sample_id}/variants')
def dna_variants(sample_id: str, user=Depends(require_access(min_level=1, permissions=['view_variant']))):
    context = dna_workflow_service.build_variant_context(sample_id=sample_id, user=user)
    return {'status': 'ok', 'data': context}
```

#### 16.2 Sequence: Report preview and save
```text
User -> Flask report preview page action
Flask -> API report preview endpoint
API -> workflow services (DNA/RNA)
API <- preview payload (html-ready context and snapshot rows)
Flask -> render preview template
User validates preview
User triggers save
Flask -> API report save endpoint
API -> report path generation and conflict check
API -> report write + metadata save + snapshot upsert
API -> audit event emit
API <- success payload
Flask <- success payload
User <- saved report confirmation
```

### Design reasoning
Preview and save are separated because they have different risk profiles. Preview is a read-oriented operation with no persistent side effects. Save is side-effectful and must enforce conflict detection, persistence ordering, and audit emission. Treating preview and save as distinct contracts prevents accidental write behavior during read workflows.

### Tradeoffs
Two-step report flow can increase user interactions and requires additional state tracking between preview and save. However, in clinical contexts, explicit confirmation steps are often required by workflow governance.

### Alternatives considered
A single endpoint that previews and saves in one step was considered but rejected. It weakens opportunity for human review and makes error handling less transparent.

### Implementation pattern
- Preview service builds deterministic context.
- Save service validates output path and write preconditions.
- Save operation executes ordered writes and snapshot upsert.
- Audit event captures actor, report id, sample id, and outcome.

### Example save sequence code fragment

```python
report_id, report_path, report_file = build_report_file_location(...)
prepare_report_output(report_path, report_file)
report_oid = persist_report_and_snapshot(
    sample_id=sample_id,
    sample=sample,
    report_num=next_num,
    report_id=report_id,
    report_file=report_file,
    html=html,
    snapshot_rows=snapshot_rows,
    created_by=user.username,
)
emit_audit_event('report.save', entity_id=report_oid, actor=user.username, result='success')
```

#### 16.3 Sequence: Admin updates role/permission policy
```text
Admin -> Flask admin page
Flask -> API admin context endpoint
API -> role/permission schema + policy state
Flask <- context payload
Admin submits update
Flask -> API admin update endpoint
API -> auth + admin policy checks
API -> schema validation
API -> versioned policy write
API -> audit event emit
API <- updated policy payload
Flask <- confirmation
Admin <- update result
```

### Design reasoning
Policy updates require stricter guardrails than normal data mutations because policy changes alter future authorization outcomes. Therefore update flow combines high-level permission checks, schema validation, version metadata, and audit event emission.

### Tradeoffs
Admin operations become heavier in validation and metadata requirements, but this is necessary for compliance and operational safety.

### Alternatives considered
Manual direct database edits by administrators were rejected because they bypass schema and audit controls.

### Implementation pattern
- Admin routes require high-level permissions.
- Schema-driven validation prevents malformed policy documents.
- Version/changelog is mandatory for governance entities.
- Rewind capability supports corrective rollback without history loss.

### Example policy update metadata

```json
{
  "entity_type": "role",
  "entity_id": "analyst",
  "revision": 18,
  "updated_by": "admin_user",
  "change_reason": "Added read-only public catalog permission"
}
```

---

## 17. Architecture Decision Records (ADR-Style Operational Record)
### Concept explanation
Architecture decisions in regulated environments should be explicit and reviewable. Even if a separate ADR repository does not yet exist, architecture documentation must communicate decision intent, accepted consequences, and change criteria. This section captures the highest-impact decisions currently shaping Coyote3.

### Design reasoning
Without explicit decision records, teams tend to reinterpret historical choices as accidental or outdated constraints, leading to uncoordinated refactors that can undermine policy behavior or data integrity. Recording decisions inside the architecture manual provides stable onboarding context until a full ADR process is formalized.

### Tradeoffs
Decision records require maintenance effort and periodic review. However, lack of decision traceability creates significantly larger long-term costs through inconsistent architecture changes.

### Alternatives considered
Relying solely on commit history was considered insufficient. Commit logs show what changed, not why specific architectural constraints exist in a compliance context.

### Implementation pattern
Each record includes:
- Decision statement
- Rationale
- Accepted consequences
- Revisit triggers
- Implementation anchors

#### ADR-001: API owns all policy and business logic
Decision: FastAPI is the authoritative layer for access checks and domain side effects.

Rationale:
- Prevent policy drift across UI modules.
- Keep audit emission aligned with true state transitions.

Accepted consequences:
- UI depends on API contracts for all meaningful operations.
- Additional integration testing required.

Revisit triggers:
- Introduction of additional trusted clients.
- Need for external API products.

Implementation anchors:
- route dependencies in `api/routes/*`
- service orchestration in `api/services/*`
- boundary tests preventing UI direct backend coupling

#### ADR-002: MongoDB 3.4 compatibility maintained
Decision: Maintain MongoDB 3.4-compatible query and write behavior until upgrade program is approved.

Rationale:
- Operational continuity and environment constraints.

Accepted consequences:
- No multi-document transaction reliance.
- Application-layer consistency orchestration required.

Revisit triggers:
- Approved upgrade window and migration budget.
- Validated compatibility test suite for upgraded database features.

Implementation anchors:
- handler methods under `api/db/*`
- migration strategy and rollback requirements

#### ADR-003: Schema-driven configuration for governed flexibility
Decision: Use schema documents to drive configurable forms and policy-managed settings.

Rationale:
- Frequent assay/governance configuration changes.
- Need to reduce code-only deployment pressure for minor configuration evolution.

Accepted consequences:
- Increased schema validation complexity.
- Strong governance needed for schema edits.

Revisit triggers:
- Excessive schema complexity impacting maintainability.
- Need for richer schema language/runtime.

Implementation anchors:
- schema collections and admin routes
- validation services and changelog metadata

#### ADR-004: Versioning and rewind mandatory for governed entities
Decision: Preserve revision history and enable rewind for policy/config/report-adjacent entities.

Rationale:
- Regulatory traceability and corrective safety.

Accepted consequences:
- Additional metadata requirements per update.
- Storage growth and retrieval complexity.

Revisit triggers:
- Introduction of specialized revision storage service.
- Policy update requiring cryptographic revision proofs.

Implementation anchors:
- version/changelog patterns in services and handlers
- audit events for rewind actions

#### ADR-005: Service-level audit emission
Decision: Emit audit events from backend services at authority points.

Rationale:
- Guarantees event fidelity for state transitions.

Accepted consequences:
- Developers must add audit hooks on new privileged mutations.
- Testing must include event validation in critical flows.

Revisit triggers:
- Adoption of event middleware with equivalent context fidelity.

Implementation anchors:
- report save services
- admin mutation services
- authorization-sensitive action handlers

#### ADR-006: Deterministic error model for all API contracts
Decision: Enforce stable error payload and status semantics across route families.

Rationale:
- Prevent ambiguous client behavior and simplify incident triage.

Accepted consequences:
- Additional normalization logic around exceptions.
- Stricter standards for route/service error handling.

Revisit triggers:
- API version increment requiring formalized error schema migration.

Implementation anchors:
- global exception handlers
- typed application errors
- route-family contract tests

### Additional implementation example: ADR compliance checklist

```text
For any architecture-impacting change:
1. identify relevant ADR(s)
2. document whether decision remains valid
3. add tests for changed invariants
4. update architecture manual and traceability matrix
5. include rollback plan for operational changes
```

### Future evolution implications
As Coyote3 evolves, these decisions should move into a dedicated ADR process with IDs, status, supersession links, and governance approvals. Until then, this section serves as the operating decision baseline.
