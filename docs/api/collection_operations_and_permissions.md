# Collection Operations And Permissions

This page defines the internal ingest commands and permission requirements for supported collections.

All authenticated internal ingest routes require explicit RBAC permissions.
Collection/sample ingest mutations require `internal.ingest:manage`; task-status
inspection requires `internal.task:view`. `superuser` still bypasses RBAC checks.

`superuser` is always allowed. Other roles must satisfy the mapped permission or route requirement directly.
Permission IDs in this page are the same IDs shipped in the out-of-the-box seed file:
`api/config/bootstrap/rbac/permissions.seed.ndjson`.

## Command Templates

## Business ID conventions

For admin-managed collections, use stable business IDs as primary document keys:

- `users.username`
- `roles.role_id`
- `permissions.permission_id`
- `assay_specific_panels.asp_id`
- `asp_configs.aspc_id` (stable identifier for one
  `asp_id + subpanel_id + environment` configuration)
- `insilico_genelists.isgl_id`

Expected behavior:

- Admin create APIs return `409 Conflict` when one of these IDs already exists.
- Internal ingest routes can be configured to skip duplicates using `ignore_duplicate` / `ignore_duplicates`.

Insert one document:
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "COLLECTION",
  "document": {
    "key": "value"
  },
  "ignore_duplicate": true
}
JSON
```

Bulk insert:
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection/bulk" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "COLLECTION",
  "documents": [
    {"key": "value_1"},
    {"key": "value_2"}
  ],
  "ignore_duplicates": true
}
JSON
```

Update/upsert one document:
```bash
curl -sS -X PUT "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "COLLECTION",
  "match": {
    "_id": "DOCUMENT_ID"
  },
  "document": {
    "key": "new_value"
  },
  "upsert": true
}
JSON
```

Upload JSON file (multipart; insert/bulk/upsert):
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection/upload" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  -F "collection=COLLECTION" \
  -F "mode=insert" \
  -F "documents_file=@/path/to/document.json;type=application/json"
```

Multipart mode rules:

- `mode=insert` expects uploaded JSON object.
- `mode=bulk` expects uploaded JSON array.
- `mode=upsert` expects uploaded JSON object and `match_json` form field.
- Payload validation and normalization use the same Pydantic collection contracts as JSON ingest endpoints.

## Supported Collections

All generic collection-ingest operations require `internal.ingest:manage`.
Some collection groups additionally require the resource-specific permission
shown below. This prevents an ingest operator from using the low-level endpoint
to bypass normal user, policy, assay-configuration, or sample controls.

| Collection group | Additional create/bulk permission | Additional update/upsert permission |
| --- | --- | --- |
| `users` | `user:create` | `user:edit` |
| `roles` | `role:create` | `role:edit` |
| `permissions` | `permission.policy:create` | `permission.policy:edit` |
| `assay_specific_panels` | `assay.panel:create` | `assay.panel:edit` |
| `asp_configs` | `assay.config:create` | `assay.config:edit` |
| `insilico_genelists` | `gene_list.insilico:create` | `gene_list.insilico:edit` |
| Sample-linked collections | `sample:edit:own` | `sample:edit:own` |
| Other supported collections | None beyond `internal.ingest:manage` | None beyond `internal.ingest:manage` |

## Ready-To-Run Examples By Collection Group

Users:
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "users",
  "document": {
    "email": "analyst@your-center.org",
    "username": "analyst1",
    "fullname": "Analyst One",
    "roles": ["viewer"],
    "auth_type": ["ldap"],
    "is_active": true
  },
  "ignore_duplicate": true
}
JSON
```

Roles:
```bash
curl -sS -X PUT "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "roles",
  "match": {"role_id": "viewer"},
  "document": {
    "role_id": "viewer",
    "name": "viewer",
    "label": "Viewer",
    "level": 1,
    "permissions": ["sample:list:global"]
  },
  "upsert": true
}
JSON
```

Permissions:
```bash
curl -sS -X PUT "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "permissions",
  "match": {"permission_id": "sample:edit:global"},
  "document": {
    "permission_id": "sample:edit:global",
    "label": "Edit all samples",
    "description": "Allows global administrative sample edits",
    "is_active": true
  },
  "upsert": true
}
JSON
```

ASP:
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "assay_specific_panels",
  "document": {
    "asp_id": "ASP_DEMO_DNA",
    "name": "Demo DNA Panel",
    "assay": "assay_1",
    "assay_group": "hematology",
    "is_active": true
  }
}
JSON
```

ASPC:
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "document": {
    "aspc_id": "assay_1_base_production",
    "asp_id": "assay_1",
    "subpanel_id": "base",
    "environment": "production",
    "asp_group": "hematology",
    "asp_category": "dna",
    "is_active": true
  }
}
JSON
```

ISGL:
```bash
curl -sS -X POST "${BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "insilico_genelists",
  "document": {
    "isgl_id": "ISGL_DEMO",
    "display_name": "Demo In Silico List",
    "assays": ["assay_1"],
    "assay_groups": ["hematology"],
    "genes": ["EGFR", "TP53"],
    "is_active": true
  }
}
JSON
```
