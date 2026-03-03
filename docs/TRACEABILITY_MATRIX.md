# Coyote3 Traceability Matrix

This matrix links system concerns to implementation areas, controls, and verification evidence. It is intended for engineering governance, audit readiness, and release review.

| Concern | Primary Modules | Control Mechanism | Verification Evidence |
|---|---|---|---|
| Route-level access control | `api/app.py`, `api/routes/*` | `require_access(...)` checks permission, role, and level | API auth tests, access matrix tests |
| Sample-level assay isolation | `_get_sample_for_api(...)` in `api/app.py` | sample assay must exist in user allowed assays | route negative tests with mismatch samples |
| Permission governance | `api/db/permissions.py`, admin policy views | centralized permission definitions and category grouping | policy CRUD tests, role-permission mapping tests |
| Role governance | `api/db/roles.py`, admin role views | role definitions with permissions + deny overrides | role management tests |
| Access audit trail | `api/app.py` access audit hooks | authorized/denied access events logged | log assertions in route tests |
| UI action audit trail | `coyote/services/audit_logs/*` | decorator-based action logging metadata | web action tests, log review |
| DNA workflow integrity | `api/routes/dna.py`, `api/services/workflow/dna_workflow.py` | service-layer invariants and normalized filters | DNA route/service tests |
| RNA workflow integrity | `api/routes/rna.py`, `api/services/workflow/rna_workflow.py` | service-layer filter normalization and context generation | RNA route/service tests |
| Report preview/save boundary | `api/routes/reports.py`, `coyote/services/reporting/web_report_bridge.py` | API provides template context; Flask renders and submits save | report route tests, web bridge tests |
| Schema-driven config correctness | `api/db/schemas.py`, admin schema views, admin utility modules | schema validation + version metadata | schema tests, admin flow tests |
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
