# Collection Key Migration Matrix (Mongo Active, DB-Agnostic Target)

## 1. Why this matrix exists
This matrix is the implementation tracker for the identity strategy in the database-agnostic backend plan.

Policy objective:
- keep Mongo `_id` as technical identity for backward compatibility
- add explicit unique business keys per collection for domain contracts and future engine portability

Without this matrix, key migration work tends to drift into ad hoc fixes and undocumented assumptions.

## 2. Status model
- `todo`: key strategy not implemented yet
- `in_progress`: key field/index/contract migration started
- `done`: key field/index/contract/tests completed for that collection

## 3. Current state snapshot (2026-03-11)
High-level:
- architectural boundary metrics are complete (`store_usage_total=0`, `mongo_leak_usage_total=0`)
- business-key rollout is still mostly pending and is the major remaining persistence-neutrality task

## 4. Collection matrix
| Area | Collection / Handler | Current `_id` pattern | Business Key target | Current usage in contracts | Unique index status | Migration status |
|---|---|---|---|---|---|---|
| Auth/Admin | users | string user identifier (mixed username/email semantics) | `user_id` | `user_id` canonical, `_id` compatibility fallback | done | done |
| Auth/Admin | roles | string role id | `role_id` | `role_id` canonical, `_id` compatibility fallback | done | done |
| Admin | permissions | string permission id | `permission_id` | mostly `_id` | pending | todo |
| Admin | schemas | string schema id | `schema_id` | mostly `_id` | pending | todo |
| Assay config | assay_specific_panels (asp) | string assay panel id | `asp_id` | mostly `_id` | pending | todo |
| Assay config | asp_configs (aspc) | composite string key | `aspc_id` | mixed | pending | todo |
| Gene lists | insilico_genelists (isgl) | string id with mixed semantics | `isgl_id` | mixed | pending | todo |
| Sample workflow | samples | ObjectId dominant | `sample_id` | mixed (`_id`, sample name) | pending | todo |
| DNA | variants | ObjectId dominant | `variant_id` | mostly `_id` refs | pending | todo |
| DNA | cnvs | ObjectId dominant | `cnv_id` | mostly `_id` refs | pending | todo |
| DNA | translocations | ObjectId dominant | `transloc_id` | mostly `_id` refs | pending | todo |
| RNA | fusions | ObjectId dominant | `fusion_id` | mostly `_id` refs | pending | todo |
| Interpretation | annotation | ObjectId dominant | `annotation_id` | mostly `_id` refs | pending | todo |
| Reporting | reported_variants | mixed ObjectId references | `reported_variant_id` | mixed | pending | todo |
| Coverage | group_coverage | ObjectId dominant | `group_region_id` | mostly `_id` refs | pending | todo |
| Coverage | blacklist | ObjectId dominant | `blacklist_entry_id` | mostly `_id` refs | pending | todo |
| Biomarkers | biomarkers | ObjectId dominant | `biomarker_id` | mostly `_id` refs | pending | todo |
| RNA QC | rna_expression | mixed/sample keyed | `rna_expression_id` | mixed | pending | todo |
| RNA QC | rna_classification | mixed/sample keyed | `rna_classification_id` | mixed | pending | todo |
| RNA QC | rna_qc | mixed/sample keyed | `rna_qc_id` | mixed | pending | todo |

## 5. Rollout playbook (per collection)
1. Add business key field definition and generation rule.
2. Backfill business key for existing documents.
3. Add unique index on business key.
4. Add repository read/write methods using business key.
5. Move service contract to business key as canonical identifier.
6. Keep `_id` mapping only inside infra adapter compatibility layer.
7. Add tests:
   - uniqueness violation behavior
   - lookup parity (`_id` path vs business key path during transition)
   - write/read roundtrip by business key

## 6. Implementation order (recommended)
1. `users`, `roles`, `permissions`:
   - highest auth/rbac impact
2. `samples`, `asp`, `aspc`, `isgl`:
   - highest route/workflow fanout
3. `variants`, `cnvs`, `translocations`, `fusions`:
   - high clinical workflow impact
4. `annotation`, `reported_variants`:
   - interpretation/reporting continuity
5. remaining support collections

## 7. Acceptance criteria for this matrix to be \"done\"
- every listed collection has explicit business key field documented
- unique index exists and is validated
- service contracts no longer require `_id` semantics
- adapter layer performs any remaining `_id` bridging
- regression tests cover uniqueness and lookup behavior

## 8. Completed rollout: users collection
Delivered for `users`:
1. Business key:
   - canonical field: `user_id`
   - compatibility fields: `_id`, `email`, `username` (read fallback only)
2. Unique index:
   - `user_id_1` (`unique=true`, `partialFilterExpression={"user_id": {"$exists": true, "$type": "string"}}`)
3. Repository/handler behavior:
   - identity lookup and updates now prefer `user_id`, then fallback to `_id`
   - local auth lookup supports email/username/user_id while preserving existing users
   - `toggle_user_active` now updates `is_active` (not generic `active`)
4. Session/auth identity:
   - auth session token and last-login updates now resolve canonical identity via `user_id` first
5. Backfill tooling:
   - script: `scripts/backfill_users_user_id.py`
   - dry-run example:
     - `python scripts/backfill_users_user_id.py --mongo-uri mongodb://localhost:37017 --db coyote_dev_3 --dry-run`
   - apply example:
     - `python scripts/backfill_users_user_id.py --mongo-uri mongodb://localhost:37017 --db coyote_dev_3`
6. Tests:
   - `tests/api/test_auth_service.py`
   - `tests/api/routes/test_system_routes.py` (business-key session path)

## 9. Completed rollout: roles collection
Delivered for `roles`:
1. Business key:
   - canonical field: `role_id`
   - compatibility field: `_id` (read/update fallback)
2. Unique index:
   - `role_id_1` (`unique=true`, `partialFilterExpression={"role_id": {"$exists": true, "$type": "string"}}`)
3. Repository/handler behavior:
   - lookups, updates, deletes, and toggle-active flows accept either `role_id` or `_id`
   - role identity normalization is lowercase to preserve existing role semantics
   - active flag mutation corrected to `is_active` (not generic `active`)
4. Backfill tooling:
   - script: `scripts/backfill_roles_role_id.py`
   - example:
     - `python scripts/backfill_roles_role_id.py --mongo-uri mongodb://localhost:37017 --db coyote_dev_3`
