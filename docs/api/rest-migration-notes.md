# REST Migration Notes

This document records the current REST normalization work for the FastAPI backend.

## Canonical Direction

The authoritative API style is:

- resource-based paths
- HTTP methods aligned to intent
- explicit request and response contracts
- versioned routes under `/api/v1`
- consistent JSON error payloads

## Current Compatibility Policy

Canonical REST routes are the only supported API surface. Compatibility paths are removed once the Flask UI and tests are migrated.

## Recently Normalized Route Families

### Auth

- `POST /api/v1/auth/sessions`
- `DELETE /api/v1/auth/sessions/current`
- `GET /api/v1/auth/session`

### Admin Users

- `POST /api/v1/admin/users`
- `PUT /api/v1/admin/users/{user_id}`
- `DELETE /api/v1/admin/users/{user_id}`
- `PATCH /api/v1/admin/users/{user_id}/status`

### Admin Roles and Permissions

The same normalization pattern now applies to roles and permission policies.

### Admin Resource Modules

The same canonical CRUD and status pattern now also applies to:

- assay panels (`/api/v1/admin/asp`)
- genelists (`/api/v1/admin/genelists`)
- assay configs (`/api/v1/admin/aspc`)
- schemas (`/api/v1/admin/schemas`)
- admin sample update/delete flows

### Sample Mutations

- `POST /api/v1/samples/{sample_id}/comments`
- `PATCH /api/v1/samples/{sample_id}/comments/{comment_id}/hidden`
- `DELETE /api/v1/samples/{sample_id}/comments/{comment_id}/hidden`
- `PUT /api/v1/samples/{sample_id}/filters`
- `DELETE /api/v1/samples/{sample_id}/filters`

### Coverage Blacklist

- `POST /api/v1/coverage/blacklist/entries`
- `DELETE /api/v1/coverage/blacklist/entries/{obj_id}`

### DNA and RNA Workflow Mutations

Specialist workflow routes follow the same canonical pattern:

- flag resources
- comment visibility resources
- collection-based bulk operations

Examples:

- DNA variants:
  - `/variants/{id}/flags/false-positive`
  - `/variants/{id}/flags/interesting`
  - `/variants/{id}/flags/irrelevant`
  - `/variants/flags/false-positive`
  - `/variants/flags/irrelevant`
  - `/variants/tier`
  - `/variant-classifications`
  - `/variant-comments`
- DNA structural:
  - `/cnvs/{id}/flags/*`
  - `/translocations/{id}/flags/*`
  - `/comments/{comment_id}/hidden`
- RNA:
  - `/fusions/{id}/flags/false-positive`
  - `/fusions/{id}/selection/{callidx}/{num_calls}`
  - `/fusions/{id}/comments/{comment_id}/hidden`
  - `/fusions/flags/*`

### Reports

- `/api/v1/{dna|rna}/samples/{sample_id}/reports/preview`
- `/api/v1/{dna|rna}/samples/{sample_id}/reports`

## Error and Validation Model

API errors now follow a consistent structure:

```json
{
  "status": 422,
  "error": "Validation failed",
  "details": [
    {"field": "filters", "message": "Input should be a valid dictionary"}
  ]
}
```

The same envelope style applies to business errors and unexpected failures.

## Maintainer Guidance

- add new routes in canonical REST form first
- update the Flask UI and tests before removing or changing a contract
- remove obsolete routes promptly once no consumers remain
