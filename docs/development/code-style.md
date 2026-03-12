# Coyote3 Code Style and Engineering Conventions

## 1. Purpose
This document defines coding and review conventions for Coyote3. The goal is to keep the codebase understandable, stable, and safe to change in a regulated clinical environment.

These standards are mandatory for new code unless an exception is documented in the pull request and approved during review.

---

## 2. Naming Conventions

## 2.1 General naming rules
- Use descriptive names tied to domain intent.
- Prefer explicit names over abbreviations.
- Avoid generic names like `data`, `obj`, `temp`, `handler2`.

### Good examples
- `build_report_file_location`
- `normalize_rna_filter_keys`
- `home_samples_read`

### Anti-patterns
- `process_data`
- `do_stuff`
- `x`, `tmp1`, `abc`

## 2.2 Python functions and variables
- `snake_case` for functions, variables, modules.
- Function names should include domain + action where possible.

### Good
`save_sample_filters`, `get_role_levels_internal`

### Bad
`save`, `getInfo`, `runTask`

## 2.3 Classes
- `PascalCase`.
- Include domain meaning in name.

### Good
`DNAWorkflowService`, `ApiRequestError`

### Bad
`Manager`, `Utility2`, `DataClass`

---

## 3. Folder Structure Rules

## 3.1 Backend (`api/`)
- `routers/`: endpoint adapters only
- `services/`: business/workflow logic
- `db/`: data access handlers
- `domain/`: domain models and shared semantics
- `errors/`: typed error model
- `utils/`: technical helpers, not policy orchestration

## 3.2 Web (`coyote/`)
- `blueprints/`: UI route composition
- `templates/`: rendering only
- `integrations/api/`: API transport wrappers
- UI layer must not own backend business logic

## 3.3 Tests (`tests/`)
- `tests/api`: backend behavior and guardrails
- `tests/ui`: boundary and web integration tests
- test module names should match feature families

### Anti-patterns
- placing business logic in `routers/` and skipping `services/`
- placing policy logic in Flask blueprint helpers
- one-file-per-function fragmentation without domain grouping

---

## 4. Blueprint Naming Rules
- Use domain-specific blueprint package names: `dna`, `rna`, `admin`, `home`, `public`.
- View module names should reflect responsibility: `views_reports.py`, `views_small_variants.py`.
- Group Flask blueprint code by feature area, not by one tiny action at a time.
- Prefer modules like `views_small_variants.py`, `views_small_variant_actions.py`, `views_users.py`, `views_assay_configs.py`, or `views_genes.py`.
- Avoid shards like `views_users_list.py`, `views_users_detail.py`, `views_users_actions.py` unless a cohesive feature module has grown too large to review.
- Blueprint variables should end with `_bp`.

### Good
- `coyote/blueprints/dna/views_reports.py`
- `dna_bp = Blueprint(...)`

### Bad
- `coyote/blueprints/misc/everything.py`
- `bp1 = Blueprint(...)`

---

## 5. Router Naming Rules
- Route module files should match feature families (`api/routers/small_variants.py`, `api/routers/fusions.py`, `api/routers/reports.py`).
- Route function names should indicate domain and operation.
- Path prefixes must remain versioned (`/api/v1/...`).

### Good route names
- `auth_login`
- `common_gene_info_read`
- `preview_dna_report`

### Anti-patterns
- unversioned routes
- route functions named `index`, `handler`, `main`
- route files mixing unrelated domains

---

## 6. Permission Naming Rules
- Permission IDs must be `snake_case` action-oriented names.
- Format recommendation: `<action>_<resource>`.
- Keep names stable; avoid semantic drift.

### Good
- `view_sample`
- `create_role`
- `preview_report`
- `export_qc_report`

### Bad
- `sampleAccess`
- `admin_all`
- `misc_permission`

### Anti-patterns
- adding permission documents without endpoint enforcement
- changing permission meaning without migration/docs update

---

## 7. Schema Naming Rules
- Schema IDs should be explicit and versioned.
- Format recommendation: `<domain>_schema_v<major>`.

### Good
- `rbac_role_schema_v1`
- `aspc_schema_v3`
- `rna_filter_schema_v2`

### Bad
- `schema1`
- `new_schema`
- `my_config`

### Requirements
- include `schema_type`
- include `version`
- include field definitions/defaults
- include changelog metadata for updates

---

## 8. Logging Naming Rules

## 8.1 Event/message names
- Use structured event names with domain semantics.
- Recommended pattern: `<domain>_<action>_<outcome>` for operational logs.
- Audit event types: `<domain>.<action>`.

### Good
- operational: `report_save_completed`
- operational: `variant_list_request`
- audit: `report.save`, `variant.classify`

### Bad
- `log1`
- `error happened`
- `something failed`

## 8.2 Required logging fields
- `trace_id` or correlation id
- route/module context
- actor/user context when relevant
- result/outcome

## 8.3 Anti-patterns
- logging secrets/tokens
- dumping raw sensitive payloads
- inconsistent event type naming across modules

---

## 9. Commit Message Conventions
Use conventional, scoped commit messages.

Format:

```text
<type>(<scope>): <short imperative summary>
```

### Common types
- `feat`
- `fix`
- `refactor`
- `test`
- `docs`
- `chore`

### Good examples
- `feat(api-reports): add RNA report save conflict handling`
- `test(api-auth): add deny-override permission matrix cases`
- `docs(security): clarify route-level enforcement model`

### Bad examples
- `updates`
- `fixed stuff`
- `final commit`

### Multi-line body guidance
Include:
- what changed
- why it changed
- risk or migration notes if relevant

---

## 10. PR Review Expectations

## 10.1 Required PR content
- problem statement
- implementation summary
- test evidence
- docs impact
- risk/rollback notes for high-impact changes

## 10.2 Reviewer checklist
1. Are boundaries respected (UI vs API vs DB handler)?
2. Are route contracts explicit and stable?
3. Are permissions enforced and tested?
4. Are audit events emitted for privileged mutations?
5. Are migrations/backward compatibility concerns addressed?
6. Are logs/errors deterministic and safe?

## 10.3 Minimum merge conditions
- CI passes (tests + compile + guardrails)
- policy-sensitive changes include permission tests
- contract changes include docs updates

## 10.4 Anti-patterns in PRs
- large mixed-scope PRs (feature + refactor + policy rewrite) without separation
- no tests for changed behavior
- changing contracts without docs
- skipping reviewer questions on security/policy implications

---

## 11. Examples: Good vs Bad Patterns

## 11.1 Good: route-service separation
```python
@app.get('/api/v1/samples')
def list_samples_read(user=Depends(require_access(min_level=1))):
    return SampleCatalogService.read_samples(user)
```

## 11.2 Bad: route owns all logic
```python
@app.get('/api/v1/samples')
def list_samples_read():
    # direct query + policy + transformation + response in one function
    ...
```

## 11.3 Good: explicit permission check
```python
@app.post('/api/v1/roles')
def create_role(payload: dict, user=Depends(require_access(min_level=900, permissions=['create_role']))):
    ...
```

## 11.4 Bad: hidden implicit access
```python
@app.post('/api/v1/roles')
def create_role(payload: dict):
    ...  # no explicit policy dependency
```

---

## 12. Enforcement and Exceptions
These standards are expected by default.

If deviation is necessary:
1. document reason in PR
2. describe risk and mitigation
3. get reviewer approval
4. add follow-up task if temporary exception

Unapproved convention drift is treated as quality debt and should be corrected before release.

---

## 13. Future Evolution Considerations
1. Add automated lint rules for permission/schema naming.
2. Add static checks for route naming and version prefix compliance.
3. Add PR template fields for policy and audit-impact classification.
4. Add commit message validation hook in CI.
