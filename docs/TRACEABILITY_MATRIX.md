# Coyote3 Traceability Matrix

This matrix links system concerns to implementation areas, controls, and verification evidence. It is intended for engineering governance, audit readiness, and release review.

| Concern | Primary Modules | Control Mechanism | Verification Evidence |
|---|---|---|---|
| Route-level access control | `api/security/access.py`, `api/routers/*` | `require_access(...)` checks permission, role, and level | API auth tests, access matrix tests |
| Sample-level assay isolation | `_get_sample_for_api(...)` in `api/security/access.py` | sample assay must exist in user allowed assays | route negative tests with mismatch samples |
| Permission governance | `api/infra/db/permissions.py`, admin policy views | centralized permission definitions and category grouping | policy CRUD tests, role-permission mapping tests |
| Role governance | `api/infra/db/roles.py`, admin role views | role definitions with permissions + deny overrides | role management tests |
| Access audit trail | `api/audit/access_events.py`, `api/security/access.py` | authorized/denied access events logged | log assertions in route tests |
| Auth service authority | `api/security/auth_service.py`, `api/routers/auth.py` | credentials validated in security layer before session issue | auth route tests |
| Typed API contracts | `api/contracts/*`, `api/routers/*` | explicit response_model for all `/api/v1` routes | route-family response tests, OpenAPI contract checks |
| UI action audit trail | `api/audit/access_events.py`, `api/security/access.py` | audit ownership is backend-only; UI actions are recorded through API requests | API route/audit tests, access-control matrix tests |
| DNA workflow integrity | `api/routers/variants.py`, `api/core/workflows/dna_workflow.py` | core-layer invariants and normalized filters | DNA route/workflow tests |
| RNA workflow integrity | `api/routers/rna.py`, `api/core/workflows/rna_workflow.py` | core-layer filter normalization and context generation | RNA route/workflow tests |
| Report preview/save boundary | `api/routers/reports.py`, `api/core/reporting/*`, `coyote/services/api_client/reports.py` | API provides template context + save validation; Flask renders and submits save via API client | report route tests, web API integration helper tests |
| UI->API auth transport | `coyote/services/api_client/api_client.py`, `api/security/access.py` | Flask forwards `Authorization: Bearer <api_session_token>` | web integration helper tests, auth route tests |
| Schema-driven config correctness | `api/infra/db/schemas.py`, admin schema views, admin utility modules | schema validation + version metadata | schema tests, admin flow tests |
| Version rewind capability | admin utility version helpers | delta generation/apply behavior | unit tests for version delta and rewind |
| Error contract consistency | `api/errors/*`, route error helpers | structured API errors and HTTP status codes | route error tests |
| API/UI boundary separation | `coyote/services/api_client/*`, blueprints | Flask accesses backend only through API client | web boundary tests |
| Deployment reproducibility | compose files + env config | containerized startup and explicit env vars | deployment smoke tests |
| Incident diagnosis | logs + health endpoints + troubleshooting docs | structured logging and runbook alignment | operations review checklist |

## 1. Matrix Usage Guidance
1. Every high-impact change should identify which matrix rows are affected.
2. PR descriptions should explicitly state control and verification updates for changed rows.
3. New architectural capabilities should add a new matrix row with ownership and tests.

## 2. Audit-Readiness Notes
- Matrix rows should map to living tests, not aspirational controls.
- Missing verification evidence should block release for policy-sensitive changes.
- When route contracts change, corresponding matrix entries and evidence links should be updated in the same change set.
