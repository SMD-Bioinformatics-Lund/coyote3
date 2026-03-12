# Coyote3 Security Model

## 1. Purpose, Scope, and Intended Audience
This document defines the security architecture and enforcement model for Coyote3, a clinical genomics platform operating in a regulated environment. The intended audience includes backend engineers, security auditors, compliance reviewers, operations engineers, and technical leads responsible for policy design and implementation assurance.

The scope includes application-layer security for the FastAPI backend, security boundary expectations for Flask UI integration, role-based authorization behavior, audit immutability principles, secure logging expectations, and deployment-level controls that materially affect confidentiality, integrity, and accountability. This document does not replace institutional legal policy or governance procedures; rather, it translates security design into technical controls and implementation expectations.

Security in Coyote3 is not treated as a separate feature area. It is a cross-cutting architectural concern embedded into route dependencies, service orchestration, audit events, configuration handling, and deployment standards. Because Coyote3 handles clinical genomics context, the cost of policy ambiguity is high. A security model that is technically “possible” but operationally ambiguous is not acceptable. The model therefore prioritizes deterministic control flow, explainable authorization outcomes, and explicit traceability.

---

## 2. Security Objectives and Control Philosophy
Coyote3 security objectives are defined as concrete operational outcomes rather than abstract principles.

### Objective 1: Restrict access to clinical data and privileged actions
Only authenticated and authorized users should be able to access protected data and operations. Authorization decisions must be policy-driven and reproducible.

### Objective 2: Preserve action-level accountability
Security-relevant actions must produce attributable records with actor, target, result, and timestamp context.

### Objective 3: Minimize accidental overexposure
Response payloads, logs, and exports should expose only required information for the operation.

### Objective 4: Ensure controlled evolution of policy
Role and permission changes must be governed, validated, and auditable. Policy behavior should not drift due to undocumented defaults or ad hoc manual changes.

### Objective 5: Maintain secure operations under infrastructure constraints
The model must work with MongoDB 3.4-compatible workflows and Docker deployment topology without relying on unsupported assumptions.

The control philosophy is layered defense with explicit trust boundaries. Coyote3 does not assume any single control is sufficient. Authentication, RBAC, route-level checks, service-level validation, and audit traces work together. If one control weakens, others should still reduce exploitation or silent misbehavior.

---

## 3. Threat Model
The threat model enumerates realistic attack and failure classes for an internal clinical platform.

## 3.1 Threat classes
### 3.1.1 Unauthorized data access
A user without required privileges attempts to access clinical records, reports, or governance metadata.

### 3.1.2 Privilege escalation
A user with limited permissions attempts to perform actions reserved for higher roles.

### 3.1.3 Policy drift exploitation
Mismatches between documented policy and enforced behavior allow unauthorized operations due to misconfiguration or stale assumptions.

### 3.1.4 Session abuse
Compromised session context is reused to impersonate valid user behavior.

### 3.1.5 Audit tampering or omission
Security-relevant actions occur without reliable audit records, reducing forensic confidence.

### 3.1.6 Sensitive data leakage through logs
Operational logs accidentally contain protected clinical payloads or credentials.

### 3.1.7 Insecure deployment exposure
Network segmentation, secret management, or TLS assumptions are misconfigured, increasing exposure surface.

## 3.2 Threat actors
- Internal user with excessive permissions or malicious intent
- Compromised internal account
- External adversary with stolen credentials
- Operator mistakes causing policy misconfiguration
- Automation or integration client using outdated/deprecated endpoints incorrectly

## 3.3 Security assumptions
ASSUMPTION:
- Institutional identity source and user lifecycle processes exist.
- Infrastructure-level perimeter controls are managed separately but aligned with application requirements.
- Coyote3 remains internal-facing or protected by controlled ingress.

## 3.4 Threat treatment strategy
Each threat class maps to controls:
- unauthorized access -> route-level RBAC + deny precedence + least privilege
- privilege escalation -> explicit permission checks + role governance + access matrix tests
- session abuse -> secure session handling + logout invalidation + transport controls
- audit tampering -> append-style event model + restricted audit write path
- data leakage -> structured redacted logging standards + controlled response payloads

---

## 4. RBAC Architecture
RBAC is the central authorization model in Coyote3. It combines role defaults, explicit permission grants, explicit denials, and optional minimum-level constraints for endpoint families.

## 4.1 Role model
Role documents define:
- role identity (`_id`)
- human-readable label
- numeric level (coarse priority)
- granted permissions
- denied permissions
- active/inactive status

Roles represent governance bundles. They are not static forever; they evolve through controlled admin flows with changelog metadata.

## 4.2 Permission model
Permissions represent action-specific capabilities. Example categories include SAMPLE, VARIANT, REPORTING, ADMIN, and PUBLIC-CATALOG interactions. Permission identifiers are stable policy keys used by route dependencies.

## 4.3 Deny-overrides model
Deny permissions explicitly remove capability even when a role grant or user-specific grant exists. Deny precedence is mandatory and non-negotiable in evaluation flow.

## 4.4 Why RBAC is implemented this way
Clinical organizations often need broad role templates but selective exceptions. A deny-override model enables safe exception handling without rewriting entire role structures.

## 4.5 Tradeoffs
RBAC with grants and denies is more complex than simple role lists. Complexity is justified because it supports least privilege and reduces accidental over-grant behavior.

## 4.6 Failure if misused
If developers bypass RBAC checks in route dependencies or service authority paths, policy is effectively optional and cannot be audited reliably. If permission ids are inconsistently named, enforcement quality degrades.

---

## 5. Permission Resolution Algorithm
This section defines the normative algorithm used to resolve effective permissions for a request.

## 5.1 Resolution stages
1. Resolve authenticated principal.
2. Load role document and role-level metadata.
3. Build initial grant set from role permissions.
4. Merge explicit user permissions (if configured).
5. Build deny set from role/user deny permissions.
6. Remove deny set from grant set.
7. Evaluate endpoint required permissions against effective grant set.
8. Evaluate minimum-level gate if defined.
9. Return allow or deterministic deny response.

## 5.2 Textual permission flow diagram
```text
[Authenticated User]
   -> [Load Role]
   -> [Role Grants + User Grants]
   -> [Apply Role/User Denies]
   -> [Effective Permission Set]
   -> [Route Required Permissions Check]
   -> [Access Level Gate]
   -> [Allow | Deny]
```

## 5.3 Deterministic deny behavior
Denied access should return `403` with safe explanatory detail (for example missing required permission). Unauthenticated requests return `401`.

## 5.4 Why deterministic algorithm matters
Security auditors need reproducible access outcomes. A deterministic algorithm prevents role-check side effects and hidden fallback behavior.

## 5.5 Example implementation sketch

```python
def resolve_effective_permissions(user_doc: dict, role_doc: dict) -> set[str]:
    grants = set(role_doc.get('permissions', [])) | set(user_doc.get('permissions', []))
    denies = set(role_doc.get('deny_permissions', [])) | set(user_doc.get('deny_permissions', []))
    return grants - denies
```

---

## 6. Role Priority Model
Role priority in Coyote3 uses numeric access levels as coarse gates and explicit permissions for fine-grained gates.

## 6.1 Level semantics
- Higher level generally represents broader operational scope.
- Level is not a substitute for specific permission checks.
- Many endpoints require both minimum level and explicit permission.

## 6.2 Why level + permission hybrid exists
Levels simplify broad segmentation (for example admin-only feature spaces), while permission keys provide operation-level precision.

## 6.3 Misuse risks
If level is used alone, granular least-privilege goals are weakened. If permissions are used without level gates in sensitive admin zones, policy management can become fragmented.

## 6.4 Performance implications
Level checks are constant-time and cheap. Permission checks involve set operations that remain efficient if permission lists are bounded and normalized.

---

## 7. Permission Inheritance and Overrides
Inheritance and overrides define how role and user-level policy entries combine.

## 7.1 Inheritance
User inherits role permissions by default.

## 7.2 User-level grants
User-specific grants can extend role capabilities where governance allows.

## 7.3 User-level denies
User-level denies can remove role capabilities for restrictive exceptions.

## 7.4 Override rules
- Deny always overrides grant.
- Explicit endpoint requirements always evaluated against effective set after overrides.

## 7.5 Textual override flow
```text
Role Grants
   + User Grants
   - Role Denies
   - User Denies
= Effective Permissions
```

## 7.6 Why this model exists
It supports institutional realities where role templates need controlled exception handling without creating many near-duplicate roles.

## 7.7 What fails if model is inconsistent
Non-deterministic override order can produce unpredictable authorization outcomes and severe audit concerns.

---

## 8. Session Management Model
Session management defines identity continuity between requests and controls exposure to session abuse.

Detailed runtime auth mode documentation (LDAP vs local allowlist, internal token usage, measured dev stats) is maintained in:
- `docs/AUTH_LOGIN_MODEL_AND_STATS.md`

## 8.1 Session lifecycle
1. Login endpoint validates credentials.
2. Session token/cookie issued.
3. Session context used on subsequent requests.
4. Logout invalidates session representation.

## 8.2 Session transport
UI forwards necessary session context when calling backend. Current transport behavior is:
- API issues HttpOnly session cookie on login.
- Flask reads the API session cookie from request context.
- Flask forwards `Authorization: Bearer <api_session_token>` to API on server-side calls.
- Flask also forwards cookie header for compatibility with existing route-family behavior.

This architecture keeps browser-side tokens non-scriptable (HttpOnly) while giving API a deterministic auth header path for policy checks.

## 8.3 Session hardening expectations
- use HttpOnly cookie where applicable
- use secure transport in production
- apply same-site controls to reduce cross-site abuse risk
- maintain predictable session TTL policy

## 8.4 Why this model exists
Session continuity improves usability and allows consistent policy checks without repeated credential prompts, while still preserving backend authority.

## 8.5 Session misuse risks
- stale sessions after role change if invalidation logic is absent
- accidental token leakage via logs
- insecure local environment forwarding patterns

## 8.6 CSRF considerations for UI and API boundary
Coyote3 uses server-rendered forms with Flask-WTF CSRF protection at the browser->Flask boundary. Most privileged operations are then executed by Flask->API server-side calls, not by direct browser->API requests. This reduces classical browser-to-API CSRF exposure on protected API routes.

Design implications:
- Browser form submissions must include valid CSRF tokens (`Flask-WTF`).
- Flask route handlers must not bypass form validation for mutation forms.
- API remains session/permission authority and does not trust UI-side role assumptions.
- If future features introduce direct browser->API mutation calls, explicit API-side CSRF strategy must be implemented for those paths.

---

## 9. UI vs API Security Boundary
Coyote3 enforces a strict security boundary between Flask UI and FastAPI backend.

## 9.1 Boundary definition
- UI is presentation and interaction orchestration layer.
- API is policy and domain side-effect authority.

## 9.2 Security implications
If UI tries to own policy decisions, controls become inconsistent and auditable behavior weakens. API must remain final authority for access and mutation validation.

## 9.3 Practical enforcement
- UI calls API endpoints through integration client abstractions.
- UI does not perform direct domain persistence operations.
- Boundary tests verify no direct policy logic leakage from API to UI imports.
- UI does not authoritatively emit audit events; audit ownership is backend-only.

## 9.4 Why this matters for auditors
Auditors need a clear control surface where policy is enforced. A mixed policy model across templates and backend routes is difficult to validate and maintain.

---

## 10. Access Control Enforcement at Route Level
Route-level enforcement is the first active security gate for endpoint requests.

## 10.1 Enforcement pattern
FastAPI middleware enforces authentication by default for `/api/v1/*` before route execution.
Only explicitly classified public/internal/doc endpoints are exempt from default session auth.
After default authentication, endpoints use `require_access(...)` dependencies to enforce RBAC permission/role/level policy before business logic execution.

## 10.2 Example route decorator and dependency usage

```python
from fastapi import Depends
from api.main import app
from api.security.access import require_access

@app.post('/api/v1/admin/permissions/create')
def create_permission(payload: dict, user=Depends(require_access(min_level=900, permissions=['create_permission']))):
    return permission_service.create(payload=payload, actor=user)
```

## 10.3 Why route-level enforcement exists
It prevents accidental execution of sensitive service logic when auth/policy checks are omitted in service function callers.

## 10.4 Misuse risks
If a route lacks required RBAC dependency, authenticated users may bypass intended least-privilege policy for that operation.
If a sensitive endpoint is incorrectly classified as public, unauthenticated exposure risk increases.

## 10.5 Additional core-layer checks
Route checks are necessary but not sufficient in all cases. Services should validate domain-level invariants and sensitive transition preconditions.

---

## 11. Audit Immutability Principles
Audit logs are security artifacts and compliance evidence, not convenience logs.

## 11.1 Immutability principles
- audit entries are append-only from application behavior perspective
- update/delete operations on audit records are restricted by policy
- rewind and corrective operations emit new events instead of mutating old events

## 11.2 Event minimum envelope
- event type
- actor id
- entity type/id
- timestamp
- result
- correlation/trace id
- context metadata (safe scope)

## 11.3 Example audit event lifecycle
1. request enters authorized route
2. service executes operation
3. operation outcome resolved (success/failure)
4. audit event generated with actor/target/outcome
5. event persisted or forwarded to configured sink
6. authorized users can review event history

The authoritative audit event is emitted by API/backend execution paths after authorization and domain validation. Flask UI actions are client-side requests to API operations and are not treated as independent audit-authority sources.

Example event:

```json
{
  "event_type": "report.save",
  "actor_id": "u42",
  "entity_type": "report",
  "entity_id": "r1",
  "result": "success",
  "timestamp": "2026-03-03T18:30:00Z",
  "trace_id": "req-123abc",
  "metadata": {"sample_id": "SAMPLE_001"}
}
```

## 11.4 Why immutability matters
Mutable audit records undermine forensic trust and compliance defensibility.

---

## 12. Secure Logging Practices
Operational logging and audit logging are separate concerns and should not be conflated.

## 12.1 Operational logs
Used for runtime diagnosis and monitoring.

Required characteristics:
- structured fields where possible
- route/module metadata
- correlation id (`request_id`, propagated through `X-Request-ID`)
- request method/path/status/duration and resolved actor identity when available
- no sensitive payload dumps by default

## 12.2 Audit logs
Used for governance and forensic evidence.

Required characteristics:
- actor attribution
- target object
- action and result
- request correlation (`request_id`)
- timestamp integrity
- API/backend emission authority for mutation events (UI is not authoritative for audit writes)

## 12.3 Redaction standards
Do not log:
- credentials
- session tokens
- protected clinical content unless policy explicitly permits and controls retention

## 12.4 Example structured operational log

```python
logger.info('variant_list_request', extra={
    'trace_id': trace_id,
    'route': '/api/v1/dna/samples/{sample_id}/variants',
    'actor': user.username,
    'sample_id': sample_id,
})
```

---

## 13. Data Exposure Minimization
Exposure minimization means returning only the information necessary for an authorized operation.

## 13.1 Response minimization
- avoid returning entire documents when small context subset is sufficient
- use projection and response mapping in services

## 13.2 Endpoint segregation
Use separate endpoints for public catalog context and clinical-sensitive sample context.

## 13.3 UI rendering minimization
UI should render required fields only and avoid caching unnecessary sensitive payloads in client-exposed contexts.

## 13.4 Why this matters
Reduced data exposure lowers impact of accidental logs, client-side inspection, and integration misuse.

---

## 14. Clinical Data Protection Posture
Coyote3 assumes clinical genomics data is sensitive and requires strict access governance.

## 14.1 Protection posture components
- authenticated access controls
- RBAC with deny-overrides
- route-level enforcement
- audit traceability
- controlled report persistence and history
- logging redaction discipline

## 14.2 Clinical workflow implications
A user action that appears routine in UI may still require strict authorization because it affects clinically relevant interpretation context or report artifacts.

## 14.3 Data lifecycle perspective
Protection applies across:
- in-transit request/response handling
- at-rest document storage
- report artifact storage
- audit evidence retention

## 14.4 Reviewer note
The platform is designed to reduce unauthorized disclosure and policy bypass risk, but institutional controls (identity management, endpoint exposure policy, endpoint hardening) remain essential.

---

## 15. Secure Deployment Recommendations
Security posture depends on deployment controls as much as application code.

## 15.1 Network controls
- restrict direct public access to MongoDB
- segment API and web service networks
- enforce ingress controls and TLS termination

## 15.2 Secret management
- inject secrets through secure environment channels
- avoid hardcoded secrets in source or image layers
- rotate secrets periodically and on incident

## 15.3 Container hardening
- run least-privileged container users where possible
- avoid unnecessary host mounts
- restrict debug interfaces in production

## 15.4 Operational monitoring
- track auth failures and forbidden rates
- monitor anomaly spikes on sensitive endpoints
- monitor audit event throughput continuity

## 15.5 Why deployment controls matter
Even correct application code can be undermined by weak secret handling or open network posture.

---

## 16. Permission Flow Diagram Narratives (Textual)
This section provides auditor-friendly textual diagrams for permission control flow.

## 16.1 Standard protected route flow
```text
Request -> Authenticate user -> Load role + user permissions
       -> Apply deny overrides -> Check required permissions
       -> Check minimum access level -> Allow or Deny
```

## 16.2 Internal route flow
```text
Request -> Authenticate (if required by route family)
       -> Validate internal token header
       -> Load role + user permissions
       -> Apply deny overrides
       -> Evaluate internal route requirements
       -> Allow or Deny
```

## 16.3 Mutation with audit flow
```text
Request -> AuthZ success -> Execute mutation service
       -> Evaluate success/failure outcome
       -> Emit audit event with actor/target/result
       -> Return response
```

These textual diagrams should be interpreted as normative control sequences. Deviations require explicit design review.

---

## 17. Example Permission Policy Definitions
### 17.1 Permission entry example

```json
{
  "_id": "export_report",
  "label": "Export report",
  "category": "REPORTING",
  "is_active": true,
  "description": "Allows report save/export operations"
}
```

### 17.2 Role policy example

```json
{
  "_id": "analyst",
  "level": 100,
  "permissions": ["view_sample", "view_variant", "preview_report"],
  "deny_permissions": ["delete_sample_global"]
}
```

### 17.3 User override example

```json
{
  "_id": "u_analyst_special",
  "role": "analyst",
  "permissions": ["export_report"],
  "deny_permissions": ["preview_report"]
}
```

Resulting behavior: user receives role grants + user grants, then denies are applied. `preview_report` is denied even if granted by role.

---

## 18. Compliance and Audit Review Considerations
Auditors and compliance reviewers typically evaluate whether controls are explicit, consistently enforced, and evidenced.

### 18.1 Evidence categories to maintain
- route-level authorization tests
- access matrix test outputs
- audit event samples for critical workflows
- release records showing policy-impact changes
- deprecation and migration logs for security-relevant endpoints

### 18.2 Reviewer concerns to address
- Is authorization deterministic?
- Are denies applied correctly?
- Can privileged actions be reconstructed from logs?
- Are session and token controls suitable for environment?
- Is clinical data exposure minimized by endpoint design?

### 18.3 Engineering expectations
Security-impacting changes should include documentation updates and explicit review notes for policy implications.

---

## 19. Future ABAC Evolution Considerations
RBAC remains primary in Coyote3, but ABAC (attribute-based access control) can provide finer-grained controls in future.

## 19.1 Why ABAC may be needed
- project/cohort-specific restrictions
- contextual constraints (time/location/system state)
- dynamic policy requirements beyond static role bundles

## 19.2 Controlled evolution approach
1. keep RBAC as baseline
2. introduce ABAC for limited high-value scenarios
3. ensure decision explainability and auditability
4. avoid silent fallback from ABAC to permissive defaults

## 19.3 Risks of premature ABAC adoption
- policy complexity explosion
- reduced reviewer clarity
- harder incident triage without tooling

## 19.4 Recommended prerequisites
- policy decision logging framework
- simulation/testing environment for policy rules
- governance process for rule lifecycle

---

## 20. Assumptions
ASSUMPTION:
- Coyote3 API remains the authoritative policy enforcement boundary.
- Session-based auth model remains primary for internal clients/UI.
- MongoDB 3.4-compatible data and workflow constraints remain active.

---

## 21. Future Evolution Considerations
1. Introduce signed immutable audit chains for stronger non-repudiation guarantees.
2. Add policy decision trace artifacts for every denied/allowed sensitive route.
3. Expand route-level security metadata registry for automated compliance reporting.
4. Integrate periodic permission drift scans and role attestation workflows.
5. Add phased ABAC support with strict explainability requirements.

---

## 22. Security Verification Controls and Evidence Operations
Security architecture is only as strong as its verification discipline. In Coyote3, route-level policy checks, permission resolution behavior, and audit emission rules must be validated continuously through automated tests and release evidence reviews. Verification should include both expected-success and expected-deny scenarios, because permissive regressions often appear only in negative-path behavior. A route that returns correct payloads for authorized users but incorrectly allows access to unauthorized users is a security defect even if all happy-path tests pass.

A practical verification model should include three layers. The first layer is static and structural verification, such as boundary tests ensuring UI modules do not directly import backend policy internals. The second layer is dynamic route-level security testing, including authentication-required checks, permission matrix checks, and internal-token gate checks where applicable. The third layer is operational evidence verification, where release candidates are validated against audit event expectations and critical action trails.

For compliance reviewers, evidence packaging is essential. Security controls should be demonstrable through artifacts such as test outputs, coverage snapshots for critical security modules, and representative audit event records from controlled test workflows. The purpose is not bureaucratic overhead; the purpose is to make security posture reviewable and repeatable across releases. Without evidence packaging, teams rely on memory and manual interpretation, which is fragile under audit or incident conditions.

A release-level security evidence checklist can be operationalized as follows: confirm protected route tests pass; confirm access matrix tests include newly introduced permissions or roles; confirm audit events are emitted for new privileged mutations; confirm no sensitive data was introduced in default logs; confirm deployment configuration changes did not weaken network or secret controls. This checklist should be attached to release approvals for security-impacting changes.

These verification practices exist to preserve trust in the enforcement model over time. Security architecture is not static; it can degrade through small, local changes if verification is weak. Continuous evidence-backed verification is therefore part of the architecture itself, not an optional afterthought.
