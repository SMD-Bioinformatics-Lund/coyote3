# Admin Config, Permissions, and Schema Playbooks (Developer)

This chapter covers sensitive governance mechanics that should be handled by developer/admin engineering owners.

Scope:

- permission policy lifecycle
- schema lifecycle and structural validation
- RBAC composition (roles + user overrides)
- ASP/ASPC/ISGL create/edit behavior from an implementation perspective
- safe rollout and rollback patterns

Standard terms:

- ASP: Assay Specific Panel
- ASPC: Assay Specific Panel Config
- ISGL: In Silico Gene List

## 1. Security boundary: user docs vs developer docs

User handbook should explain operational steps only.

Developer handbook must own:

- permission model design
- schema category/type strategy
- version-history and rewind behavior
- route-protection contract (`@require(...)` and sample-scope controls)

## 2. Route map for sensitive admin entities

Permissions:

- list: `/admin/permissions`
- create: `/admin/permissions/new`
- edit: `/admin/permissions/<perm_id>/edit`
- view: `/admin/permissions/<perm_id>/view`
- toggle active: `/admin/permissions/<perm_id>/toggle`
- delete: `/admin/permissions/<perm_id>/delete`

Schemas:

- list: `/admin/schemas`
- create: `/admin/schemas/new`
- edit: `/admin/schemas/<schema_id>/edit`
- toggle active: `/admin/schemas/<schema_id>/toggle`
- delete: `/admin/schemas/<schema_id>/delete`

RBAC entities and assay config (for dependency context):

- users: `/admin/users`, `/admin/users/new`, `/admin/users/<id>/edit`
- roles: `/admin/roles`, `/admin/roles/new`, `/admin/roles/<id>/edit`
- ASP: `/admin/asp/new`, `/admin/asp/<id>/edit`
- ASPC: `/admin/aspc/dna/new`, `/admin/aspc/rna/new`, `/admin/aspc/<id>/edit`
- ISGL: `/admin/genelists/new`, `/admin/genelists/<id>/edit`

## 3. Permission policy lifecycle (developer playbook)

### 3.1 Create policy

1. Create in `/admin/permissions/new`.
2. Use active schema category/type:
- `schema_type="acl_config"`
- `schema_category="RBAC"`
3. Set stable `_id` from `permission_name`.
4. Store `schema_name` and `schema_version`.
5. Inject initial version-history record.

### 3.2 Update policy

1. Edit in `/admin/permissions/<perm_id>/edit`.
2. Preserve immutable identity `_id`.
3. Increment `version`.
4. Update `updated_by` / `updated_on`.
5. Inject version delta (`util.admin.inject_version_history`).

### 3.3 Rewind/view historical versions

Read/view/edit handlers support `?version=<n>` for rewound display behavior by applying stored deltas.

Use this for:

- audit investigations
- change impact debugging
- rollback planning before forward-fix

### 3.4 Activation strategy

- prefer create as inactive, validate with test role/user, then toggle active
- remove or deactivate stale policies that are no longer assigned

## 4. Schema lifecycle (developer playbook)

### 4.1 Create schema

1. Create in `/admin/schemas/new`.
2. Provide JSON object with valid structure.
3. `_id` is derived from `schema_name`.
4. Validate with `util.admin.validate_schema_structure(...)`.
5. Save with metadata (`created_by/on`, `updated_by/on`).

### 4.2 Edit schema

1. Edit in `/admin/schemas/<schema_id>/edit`.
2. Validate structure before write.
3. Preserve original `_id`.
4. Increment version on save.

### 4.3 Toggle/delete schema

- toggle is the preferred operational method for retiring a schema
- delete only when safe and no active dependency remains

### 4.4 Schema governance rules

- do not change schema semantics silently between versions
- add fields in backward-compatible way where possible
- test affected create/edit pages before activating the new schema

## 5. RBAC composition contract

Effective access derives from:

1. role baseline permissions (`roles.permissions` / `roles.deny_permissions`)
2. user-level overrides (`users.permissions` / `users.deny_permissions`)
3. route decorators and runtime checks

Implementation detail from handlers:

- user create/edit removes duplicate permissions already present in assigned role
- this keeps user docs focused on overrides only, reducing ambiguity in effective policy

## 6. ASP, ASPC, ISGL creation internals (developer notes)

All three follow similar schema-driven patterns:

1. resolve active schema set by `schema_type` + `schema_category`
2. inject runtime options (assay groups, assay ids, consequences, etc.)
3. process form through `util.admin.process_form_to_config`
4. set identity (`_id`) and schema metadata
5. inject version history
6. persist via handler

Entity-specific notes:

- ASP parses covered and germline genes from file/paste input.
- ASPC enforces assay/environment compatibility and category split (DNA/RNA).
- ISGL supports assay-group/assay mapping and genes list payload.

## 7. Safe rollout order for config changes

For new assay behavior, deploy in this order:

1. schema changes (if required), inactive first
2. permission policies
3. roles
4. users (or user overrides)
5. ASP
6. ASPC
7. ISGL
8. smoke test with representative sample(s)

Rationale:

- prevents users from reaching routes/features that reference missing config
- isolates failures to one domain per step

## 8. Minimal smoke-test matrix after admin config changes

1. Admin user can access intended admin pages.
2. Non-admin analyst is blocked from restricted pages.
3. Target assay sample loads with expected filters/sections.
4. ISGL/ad hoc gene application changes effective genes as expected.
5. Report preview still renders for target assay.
6. Audit log receives corresponding actions.

## 9. Failure patterns and quick diagnosis

1. Form page opens but create fails:
- usually schema mismatch or invalid field structure

2. Config saves but behavior does not change:
- wrong assay/env linkage or inactive config

3. User can log in but route denied:
- role/permission mismatch or deny override present

4. Edit page fails on historical version:
- malformed version history delta chain

## 10. Documentation ownership rule

When changing permissions/schemas/admin config semantics:

1. update this chapter
2. update affected user playbook sections if operator behavior changed
3. include rollout and rollback notes in change log / release notes
