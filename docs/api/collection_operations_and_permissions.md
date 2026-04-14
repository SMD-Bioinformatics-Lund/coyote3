# Collection Operations And Permissions

This page defines the internal ingest commands and permission requirements for supported collections.

Role gate for all internal ingest routes: `developer` or `superuser`.

`superuser` is always allowed. Other roles must satisfy the mapped permission or route requirement directly.
Permission IDs in this page are the same IDs shipped in the out-of-the-box seed file:
`tests/data/seed_data/permissions.seed.ndjson.gz`.

## Command Templates

## Business ID conventions

For admin-managed collections, use stable business IDs as primary document keys:

- `users.username`
- `roles.role_id`
- `permissions.permission_id`
- `assay_specific_panels.asp_id`
- `asp_configs.aspc_id` (`<assay>:<environment>`)
- `insilico_genelists.isgl_id`

Expected behavior:

- Admin create APIs return `409 Conflict` when one of these IDs already exists.
- Internal ingest routes can be configured to skip duplicates using `ignore_duplicate` / `ignore_duplicates`.

Insert one document:
```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection" \
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
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection/bulk" \
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
curl -sS -X PUT "${API_BASE_URL}/api/v1/internal/ingest/collection" \
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
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection/upload" \
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

| Collection | Create/Bulk Permission | Update/Upsert Permission |
| --- | --- | --- |
| `annotation` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `asp_configs` | `create_aspc` | `edit_aspc` |
| `asp_to_groups` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `assay_specific_panels` | `create_asp` | `edit_asp` |
| `biomarkers` | `edit_sample` | `edit_sample` |
| `blacklist` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `brcaexchange` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `civic_genes` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `civic_variants` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `cnvs` | `edit_sample` | `edit_sample` |
| `cosmic` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `dashboard_metrics` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `fusions` | `edit_sample` | `edit_sample` |
| `group_coverage` | `edit_sample` | `edit_sample` |
| `hgnc_genes` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `hpaexpr` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `iarc_tp53` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `insilico_genelists` | `create_isgl` | `edit_isgl` |
| `mane_select` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `oncokb_actionable` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `oncokb_genes` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `panel_coverage` | `edit_sample` | `edit_sample` |
| `permissions` | `create_permission_policy` | `edit_permission_policy` |
| `refseq_canonical` | `developer/admin role-level gate` | `developer/admin role-level gate` |
| `reported_variants` | `edit_sample` | `edit_sample` |
| `rna_classification` | `edit_sample` | `edit_sample` |
| `rna_expression` | `edit_sample` | `edit_sample` |
| `rna_qc` | `edit_sample` | `edit_sample` |
| `roles` | `create_role` | `edit_role` |
| `samples` | `edit_sample` | `edit_sample` |
| `translocations` | `edit_sample` | `edit_sample` |
| `users` | `create_user` | `edit_user` |
| `variants` | `edit_sample` | `edit_sample` |
| `vep_metadata` | `developer/admin role-level gate` | `developer/admin role-level gate` |

## Ready-To-Run Examples By Collection Group

Users:
```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "users",
  "document": {
    "email": "analyst@your-center.org",
    "username": "analyst1",
    "fullname": "Analyst One",
    "role": "viewer",
    "access_level": 10,
    "permissions": [],
    "denied_permissions": [],
    "is_active": true
  },
  "ignore_duplicate": true
}
JSON
```

Roles:
```bash
curl -sS -X PUT "${API_BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "roles",
  "match": {"role_id": "viewer"},
  "document": {
    "role_id": "viewer",
    "role_name": "Viewer",
    "level": 10,
    "permissions": ["view_sample_global"],
    "denied_permissions": []
  },
  "upsert": true
}
JSON
```

Permissions:
```bash
curl -sS -X PUT "${API_BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "permissions",
  "match": {"permission_id": "edit_sample"},
  "document": {
    "permission_id": "edit_sample",
    "name": "Edit sample",
    "description": "Allows editing sample-level data",
    "is_active": true
  },
  "upsert": true
}
JSON
```

ASP:
```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection" \
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
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer ${API_BEARER_TOKEN}" \
  --data @- <<'JSON'
{
  "collection": "asp_configs",
  "document": {
    "aspc_id": "assay_1:prod",
    "assay_name": "assay_1",
    "environment": "prod",
    "asp_group": "hematology",
    "is_active": true
  }
}
JSON
```

ISGL:
```bash
curl -sS -X POST "${API_BASE_URL}/api/v1/internal/ingest/collection" \
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
