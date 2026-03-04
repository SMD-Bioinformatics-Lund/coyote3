# Coyote3 FastAPI API Reference

## 1. Purpose and Audience
This document is the canonical API reference for internal consumers of the Coyote3 FastAPI backend. It is written for backend engineers, Flask UI engineers, integration developers, validation engineers, and operations teams who need deterministic API contracts for a regulated clinical genomics platform.

The API is not designed as a generic public interface with broad anonymous access. It is an internal policy-enforced service layer with explicit authorization semantics, stable payload conventions, and traceable behavior. Consumers should treat this reference as normative for contract behavior and implementation standards.

The examples in this document are representative and align with current route-family patterns in Coyote3. Endpoint naming and exact payload content can evolve over time, but changes must follow versioning and deprecation rules in this reference.

---

## 2. API Design Principles
Coyote3 API design follows principles intended for clinical safety, policy clarity, and operational reliability.

### 2.1 Contract determinism
Each endpoint must have a stable request and response structure. Dynamic fields should be explicit and schema-governed where possible.

### 2.2 Policy-first execution
Authorization checks are evaluated before domain mutation behavior. A route returning data or accepting mutation must not bypass policy dependencies.

### 2.3 Auditable side effects
Endpoints with side effects must execute through service flows that produce audit evidence.

### 2.4 Backward-compatible evolution
Additive changes are preferred within major API version. Breaking contract changes require a new major version path.

### 2.5 Clinical workflow alignment
Endpoint design reflects sample-centric workflows and report traceability requirements rather than generic CRUD abstractions only.

---

## 3. Base URL, Version Prefix, and Service Scope
### 3.1 Base path
Coyote3 API endpoints are rooted under major version path:

```text
/api/v1
```

### 3.2 Non-version aliases
Some compatibility aliases may exist temporarily (for example docs alias routes), but they should not be used as primary integration targets.

### 3.3 Service scope
Coyote3 API includes the following route families:
- system/auth
- internal
- home/sample context
- DNA workflows
- RNA workflows
- reporting workflows
- common/shared context
- public catalog endpoints
- admin/governance endpoints

---

## 4. Authentication Model
### 4.1 Session-based authenticated access
Most endpoints require authenticated user context resolved by backend dependencies. The common flow is:
1. client submits credentials to login endpoint
2. API validates credentials
3. API returns session payload and sets an HttpOnly API session cookie
4. Flask UI forwards session context on server-side API calls as:
   - `Authorization: Bearer <api_session_token>` (primary)
   - cookie header (compatibility/secondary)
5. API validates session + permissions on every request (`require_access(...)`)

### 4.2 Internal token model
Internal-only endpoints require an additional internal token (`X-Coyote-Internal-Token`) even when authenticated context exists. This is an extra control layer for service-to-service and privileged internal reads.

### 4.3 Role and permission enforcement
After authentication, route dependencies evaluate role level, permissions, and deny overlays. Endpoint consumers should expect explicit `403` responses when policy checks fail.

### 4.4 Authentication headers and cookies
Coyote3 integrations use a hybrid session transport model:
- Browser <-> Flask: HttpOnly cookie issued by API and stored in browser session context.
- Flask <-> API (server-side): Bearer token forwarding from the API session cookie, plus cookie forwarding for compatibility.

This model exists because UI routes are server-rendered; browser JavaScript does not directly call most protected API routes. The Flask layer is therefore the trusted transport proxy, while API remains the sole authorization authority.

### 4.6 Report preview and save contract boundary
Report preview and save flows are API-driven. The UI requests preview payloads from `/api/v1/.../report/preview`, renders the provided template/context, and submits rendered HTML to `/api/v1/.../report/save`. Report identifier generation, snapshot-row normalization, file-path resolution, and persistence validation are backend responsibilities in `api/routes/reports.py` + `api/core/reporting/*`.

### 4.5 Security behavior expectations
- authentication failure: `401`
- authorization failure: `403`
- internal token failure on protected internal routes: `403`

---

## 5. Request Format Standards
### 5.1 Content type
JSON endpoints expect:

```text
Content-Type: application/json
```

For `GET` requests, input is typically via path and query parameters.

### 5.2 Path parameter standards
- use explicit semantic names (`sample_id`, `variant_id`, `report_id`)
- identifiers are treated as strings unless explicitly documented otherwise
- avoid overloading one path parameter for multiple domain meanings

### 5.3 Query parameter standards
- query parameters are optional unless documented required
- boolean-like query values should be explicit (`true/false`) and normalized by backend
- list-style filters should be documented with expected format (comma-separated or repeated params)

### 5.4 Request body standards
- bodies must be JSON objects, not ambiguous primitive values
- mutation endpoints should reject malformed or missing required fields with `400`
- request body field names should remain stable across minor versions

### 5.5 Idempotency guidance
For critical mutation operations that can be retried by clients, consumers should ensure safe retry behavior by avoiding duplicate submission patterns unless endpoint is documented idempotent.

---

## 6. Response Format Standards
### 6.1 Success response envelope
Preferred success structure:

```json
{
  "status": "ok",
  "data": {...}
}
```

Some route families include additional top-level keys for historical compatibility. New endpoint designs should prefer explicit `data` envelopes unless route-family conventions require otherwise.

### 6.2 Error response envelope
Preferred error structure:

```json
{
  "status": 400,
  "error": "Validation failed",
  "details": "field X is required"
}
```

### 6.3 Response typing conventions
- identifiers are serialized as strings
- lists remain arrays even when single item returned logically possible
- optional fields should be omitted or set explicitly to `null` based on route-family convention

### 6.4 Deterministic keys
Consumers should not depend on key ordering but can depend on key naming and envelope shape per endpoint contract.

---

## 7. Error Model and Status Codes
### 7.1 Error model philosophy
Errors communicate contract or policy outcomes, not implementation internals. Messages should be useful for troubleshooting while avoiding sensitive data exposure.

### 7.2 Common status codes
- `200 OK`: successful read or mutation result
- `201 Created`: successful create semantics (use when route family applies)
- `400 Bad Request`: invalid input format or semantic validation failure
- `401 Unauthorized`: missing/invalid authentication context
- `403 Forbidden`: authenticated but insufficient permission/level
- `404 Not Found`: target entity absent or inaccessible as not-found pattern
- `409 Conflict`: state conflict (for example report artifact collision)
- `422 Unprocessable Entity`: framework-level validation failure where applicable
- `500 Internal Server Error`: unexpected failure after application handling

### 7.3 Error payload fields
- `status` numeric code
- `error` concise error label
- `details` optional contextual detail safe for client display/logging

### 7.4 Client handling recommendation
Internal consumers should branch on status code class first, then inspect `error` and `details` for user-friendly messages and diagnostics.

---

## 8. Pagination Standards
### 8.1 Pagination purpose
Pagination protects API and UI from unbounded result sets, improving latency predictability and memory safety.

### 8.2 Standard parameters
- `page`: 1-based page number
- `page_size`: bounded result count
- optional `sort`
- optional `direction` (`asc`, `desc`)

### 8.3 Standard pagination response block

```json
{
  "status": "ok",
  "data": [...],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 117,
    "pages": 3
  }
}
```

### 8.4 Validation behavior
Invalid pagination values should return `400` with details describing invalid parameter values.

---

## 9. Filtering Conventions
### 9.1 General filtering rules
- filters should be explicit and documented
- filter values should be type-safe and normalized server-side
- filter keys should avoid ambiguous naming

### 9.2 Endpoint-level filter documentation
Each endpoint with filtering should define:
- accepted filter keys
- expected type per key
- default behavior when key omitted
- interaction between multiple filters

### 9.3 Assay-aware filtering
Some filters are assay-specific. Consumers should not assume filter parity across DNA and RNA endpoints.

### 9.4 Error behavior for filters
Malformed or unsupported filter keys should return `400` with actionable detail.

---

## 10. Versioning Strategy
### 10.1 Major version in URI
Coyote3 uses URI major versioning (`/api/v1`).

### 10.2 Additive change policy
Within a major version:
- additive fields are allowed
- optional query parameters may be introduced
- behavior should remain backward-compatible

### 10.3 Breaking change policy
Breaking changes require a new major version path (for example `/api/v2`) and migration documentation.

### 10.4 Compatibility window
Deprecated endpoints should remain functional during a documented transition window.

---

## 11. Deprecation Policy
### 11.1 Deprecation lifecycle
1. Mark endpoint as deprecated in docs.
2. Provide replacement endpoint and migration guidance.
3. Communicate timeline in release notes.
4. Remove endpoint only after migration window closure and validation.

### 11.2 Consumer responsibilities
Internal consumers must track deprecation notices and schedule migration work before endpoint removal windows.

### 11.3 Operational safeguards
Deprecation removals should include pre-removal telemetry review to verify consumer migration completion.

---

## 12. Endpoint Documentation Template (Reusable)
Use this template for all new endpoint documentation.

```markdown
### <TITLE>
- Endpoint: `<PATH>`
- Method: `<HTTP_METHOD>`
- Purpose: <what this endpoint does>

#### Security
- Authentication: required/optional
- Permissions: <permission ids>
- Access level: <minimum level or N/A>
- Additional controls: <internal token or none>

#### Path Parameters
| Name | Type | Required | Description |
|---|---|---|---|
| ... | ... | ... | ... |

#### Query Parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| ... | ... | ... | ... | ... |

#### Request Body
```json
{...}
```

#### Response Body
```json
{...}
```

#### Example Request JSON
```json
{...}
```

#### Example Response JSON
```json
{...}
```

#### Status Codes
- 200 ...
- 400 ...
- 401 ...
- 403 ...
- 404 ...
- 409 ...
```

---

## 13. Sample Endpoint Documentation Examples
## 13.1 Get Sample Context
- Endpoint: `/api/v1/samples/{sample_id}`
- Method: `GET`
- Purpose: Retrieve primary sample context for authorized consumers.

### Security notes
- Authentication required.
- Permission typically includes `view_sample`.
- Minimum level gate may apply by deployment policy.

### Path parameters
| Name | Type | Required | Description |
|---|---|---|---|
| sample_id | string | yes | Canonical sample identifier |

### Query parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| include_reports | boolean | no | false | Include report references in sample context |

### Request body
Not applicable for `GET`.

### Response body
```json
{
  "status": "ok",
  "data": {
    "sample_id": "SAMPLE_001",
    "case_id": "CASE001",
    "assay": "WGS",
    "filters": {
      "min_depth": 100,
      "min_alt_reads": 5
    },
    "reports": [
      {"report_id": "CASE001_CC1.260303101112", "report_num": 1}
    ]
  }
}
```

### Example request JSON
Not applicable for `GET`.

### Example response JSON
```json
{
  "status": "ok",
  "data": {
    "sample_id": "SAMPLE_001",
    "case_id": "CASE001",
    "assay": "WGS"
  }
}
```

### Status codes
- `200` sample context returned
- `401` unauthenticated
- `403` missing permission
- `404` sample not found

## 13.2 Update Sample Filters
- Endpoint: `/api/v1/samples/{sample_id}/filters/update`
- Method: `POST`
- Purpose: Update filter state for sample-specific workflows.

### Security notes
- Authentication required.
- Permission typically includes `edit_sample` or equivalent.
- Mutation operation should emit audit event.

### Path parameters
| Name | Type | Required | Description |
|---|---|---|---|
| sample_id | string | yes | Target sample |

### Query parameters
None.

### Request body
```json
{
  "filters": {
    "min_depth": 80,
    "max_popfreq": 0.01
  }
}
```

### Response body
```json
{
  "status": "ok",
  "data": {
    "sample_id": "SAMPLE_001",
    "filters_updated": true
  }
}
```

### Example request JSON
```json
{
  "filters": {
    "min_depth": 80,
    "min_alt_reads": 4
  }
}
```

### Example response JSON
```json
{
  "status": "ok",
  "data": {
    "sample_id": "SAMPLE_001",
    "filters_updated": true
  }
}
```

### Status codes
- `200` update applied
- `400` invalid filter payload
- `401` unauthenticated
- `403` forbidden
- `404` sample not found

---

## 14. Variant Endpoint Documentation Examples
## 14.1 List DNA Variants
- Endpoint: `/api/v1/dna/samples/{sample_id}/variants`
- Method: `GET`
- Purpose: Return paginated variant list for DNA sample context.

### Security notes
- Authentication required.
- Permission typically includes `view_variant`.
- Filter parameters may be assay-aware and validated server-side.

### Path parameters
| Name | Type | Required | Description |
|---|---|---|---|
| sample_id | string | yes | Sample identifier |

### Query parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| page | integer | no | 1 | Page number |
| page_size | integer | no | 50 | Page size |
| tier | integer | no | none | Optional tier filter |
| gene | string | no | none | Optional gene symbol filter |

### Request body
Not applicable.

### Response body
```json
{
  "status": "ok",
  "data": [
    {
      "variant_id": "v1",
      "simple_id": "17_7579472_C_T",
      "gene": "TP53",
      "tier": 2
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 50,
    "total": 1,
    "pages": 1
  }
}
```

### Example request JSON
Not applicable.

### Example response JSON
```json
{
  "status": "ok",
  "data": [
    {
      "variant_id": "v1",
      "gene": "TP53",
      "tier": 2
    }
  ]
}
```

### Status codes
- `200` list returned
- `400` invalid query parameters
- `401` unauthenticated
- `403` forbidden
- `404` sample not found

## 14.2 Classify Variant
- Endpoint: `/api/v1/dna/samples/{sample_id}/variants/classify`
- Method: `POST`
- Purpose: Apply classification/tier mutation for one or more variants.

### Security notes
- Authentication required.
- Permission typically includes variant edit/classify permission.
- Must be audit-traceable mutation.

### Path parameters
| Name | Type | Required | Description |
|---|---|---|---|
| sample_id | string | yes | Target sample |

### Query parameters
None.

### Request body
```json
{
  "variant_ids": ["v1", "v2"],
  "tier": 2,
  "comment": "Clinically relevant based on review"
}
```

### Response body
```json
{
  "status": "ok",
  "data": {
    "updated_count": 2,
    "tier": 2
  }
}
```

### Example request JSON
```json
{
  "variant_ids": ["v1"],
  "tier": 3
}
```

### Example response JSON
```json
{
  "status": "ok",
  "data": {
    "updated_count": 1,
    "tier": 3
  }
}
```

### Status codes
- `200` classification applied
- `400` invalid body or tier
- `401` unauthenticated
- `403` forbidden
- `404` variant or sample not found

---

## 15. Assay Endpoint Documentation Examples
## 15.1 Public Assay Catalog Context
- Endpoint: `/api/v1/public/assay-catalog/context`
- Method: `GET`
- Purpose: Provide assay catalog context for approved public/internal views.

### Security notes
- Authentication policy depends on deployment route policy (public/internal read).
- Even for public routes, output must avoid sensitive patient data.

### Path parameters
None.

### Query parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| modality | string | no | none | Optional modality filter |

### Request body
Not applicable.

### Response body
```json
{
  "status": "ok",
  "data": {
    "modalities": ["DNA", "RNA"],
    "assays": [
      {"assay_id": "WGS", "label": "Whole Genome Sequencing"}
    ]
  }
}
```

### Example request JSON
Not applicable.

### Example response JSON
```json
{
  "status": "ok",
  "data": {
    "assays": [{"assay_id": "WGS", "label": "Whole Genome Sequencing"}]
  }
}
```

### Status codes
- `200` catalog returned
- `400` invalid filter
- `404` catalog not configured

## 15.2 Admin Assay Config Update
- Endpoint: `/api/v1/admin/aspc/{assay_id}/update`
- Method: `POST`
- Purpose: Update assay configuration document.

### Security notes
- Authentication required.
- Admin-level permission required.
- Mutation should emit audit event and version/changelog metadata.

### Path parameters
| Name | Type | Required | Description |
|---|---|---|---|
| assay_id | string | yes | Assay configuration id |

### Query parameters
None.

### Request body
```json
{
  "analysis_types": ["SNV", "CNV"],
  "filters": {"min_depth": 100},
  "change_reason": "Updated default thresholds"
}
```

### Response body
```json
{
  "status": "ok",
  "data": {
    "assay_id": "WGS",
    "updated": true,
    "version": 4
  }
}
```

### Example request JSON
```json
{
  "filters": {"min_depth": 120},
  "change_reason": "Policy revision"
}
```

### Example response JSON
```json
{
  "status": "ok",
  "data": {"assay_id": "WGS", "updated": true}
}
```

### Status codes
- `200` update succeeded
- `400` schema validation failed
- `401` unauthenticated
- `403` forbidden
- `404` assay config not found

---

## 16. User Endpoint Documentation Examples
## 16.1 Login
- Endpoint: `/api/v1/auth/login`
- Method: `POST`
- Purpose: Authenticate user and initialize API session context.

### Security notes
- Anonymous allowed only for login endpoint.
- Credentials must be transmitted over secure channel.
- Session token/cookie issued on success.

### Path parameters
None.

### Query parameters
None.

### Request body
```json
{
  "username": "analyst1",
  "password": "<secret>"
}
```

### Response body
```json
{
  "status": "ok",
  "user": {
    "username": "analyst1",
    "role": "analyst"
  },
  "session_token": "token_value"
}
```

### Example request JSON
```json
{
  "username": "analyst1",
  "password": "example_password"
}
```

### Example response JSON
```json
{
  "status": "ok",
  "user": {"username": "analyst1", "role": "analyst"}
}
```

### Status codes
- `200` authenticated
- `401` invalid credentials
- `400` malformed payload

## 16.2 Who Am I
- Endpoint: `/api/v1/auth/whoami`
- Method: `GET`
- Purpose: Return effective user policy context for current session.

### Security notes
- Authentication required.
- Useful for client-side permission-aware UI behavior.

### Path parameters
None.

### Query parameters
None.

### Request body
Not applicable.

### Response body
```json
{
  "username": "analyst1",
  "role": "analyst",
  "access_level": 100,
  "permissions": ["view_sample", "view_variant"],
  "denied_permissions": []
}
```

### Example request JSON
Not applicable.

### Example response JSON
```json
{
  "username": "analyst1",
  "role": "analyst"
}
```

### Status codes
- `200` context returned
- `401` unauthenticated

---

## 17. Permission Endpoint Documentation Examples
## 17.1 List Permissions
- Endpoint: `/api/v1/admin/permissions`
- Method: `GET`
- Purpose: Return permission registry for admin governance views.

### Security notes
- Authentication required.
- Admin permission required (`view_permission` or equivalent).

### Path parameters
None.

### Query parameters
| Name | Type | Required | Default | Description |
|---|---|---|---|---|
| category | string | no | none | Optional category filter |
| active_only | boolean | no | true | Return only active permissions |

### Request body
Not applicable.

### Response body
```json
{
  "status": "ok",
  "data": [
    {
      "permission_id": "view_sample",
      "label": "View sample",
      "category": "SAMPLE",
      "is_active": true
    }
  ]
}
```

### Example request JSON
Not applicable.

### Example response JSON
```json
{
  "status": "ok",
  "data": [{"permission_id": "view_sample", "category": "SAMPLE"}]
}
```

### Status codes
- `200` list returned
- `401` unauthenticated
- `403` forbidden

## 17.2 Create Permission
- Endpoint: `/api/v1/admin/permissions/create`
- Method: `POST`
- Purpose: Create a new permission policy entry.

### Security notes
- Authentication required.
- Strong admin permission required.
- Should emit audit event and be schema-validated.

### Path parameters
None.

### Query parameters
None.

### Request body
```json
{
  "permission_id": "export_qc_report",
  "label": "Export QC report",
  "category": "REPORTING",
  "description": "Allows QC report export"
}
```

### Response body
```json
{
  "status": "ok",
  "data": {
    "permission_id": "export_qc_report",
    "created": true
  }
}
```

### Example request JSON
```json
{
  "permission_id": "new_permission_x",
  "label": "New Permission X",
  "category": "ADMIN"
}
```

### Example response JSON
```json
{
  "status": "ok",
  "data": {"permission_id": "new_permission_x", "created": true}
}
```

### Status codes
- `200` created
- `400` invalid payload / duplicate id conflict pattern (or `409` by route policy)
- `401` unauthenticated
- `403` forbidden

---

## 18. Internal Endpoint Security Notes
Internal routes (`/api/v1/internal/...`) are not general client endpoints.

### Requirements
- valid authenticated/internal caller context as defined by deployment
- internal token header
- strict least-privilege handling

### Consumer guidance
Only trusted internal services should call these routes. UI and external clients should use non-internal route families unless explicitly designed otherwise.

---

## 19. API Consumer Best Practices
1. Always branch logic on HTTP status class first.
2. Treat `403` as policy result, not transient failure.
3. Use pagination and filters intentionally; avoid unbounded pulls.
4. Do not hardcode deprecated endpoint usage in new integrations.
5. Preserve response fields as typed values (especially identifiers as strings).
6. Log correlation identifiers for cross-layer debugging.

---

## 20. Assumptions
ASSUMPTION:
- Route names and family structure align with current Coyote3 API modules.
- Session authentication is the primary interaction model for internal consumers.
- Some response envelopes may preserve historical route-family conventions while new designs should prefer `status + data` structure.

---

## 21. Future Evolution Considerations
1. Add machine-generated endpoint contract examples from OpenAPI in CI.
2. Add endpoint-level policy metadata registry mapping permissions to routes.
3. Add formal idempotency-key support for critical mutation endpoints.
4. Add compatibility matrix tests across active and deprecated endpoint paths.
5. Introduce per-endpoint SLO/latency annotations for operational planning.
