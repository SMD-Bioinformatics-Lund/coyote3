## Context

Coyote3 currently uses 64 flat snake_case permission strings stored in MongoDB
(`permissions` collection) and referenced free-text from templates via
`has_access('edit_sample', min_role='admin', min_level=99999)`. There are no
code constants, no server-side decorators, and no structural meaning in the
strings. See the inventory doc for the full list and observed problems.

This document evaluates naming schemes and recommends one. **It does not
change any code.** Migration is a separate task.

## Goals

1. **Parseability** — tooling can answer "what permissions touch samples?" by
   string match alone.
2. **Consistency** — one verb set, one scope mechanism, one pluralisation
   rule.
3. **Type safety** — typos surface as failures, not silently-hidden UI.
4. **Low migration cost** — every existing string maps unambiguously to the
   new form.
5. **Server-side enforceable** — the scheme must work for a future
   `@require_permission(...)` decorator, not just templates.

Naming is downstream of two bigger issues (disjunctive `has_access`,
no route-level enforcement). The chosen scheme should not block fixing those.

## Options considered

### Option 1 — Status quo: flat snake_case

`edit_sample`, `delete_sample_global`, `add_global_variant_comment`.

- **Pros:** zero migration; humans read it fine.
- **Cons:** every problem in the inventory; not parseable; scope is
  inconsistent; verbs drift.

### Option 2 — `resource:action` with `_global` suffix

`sample:edit`, `sample:delete_global`, `variant:comment_add_global`.

- **Pros:** resource is parseable; familiar (Laravel/Spatie style);
  Mongo-safe (colons are fine in string values).
- **Cons:** scope is still tacked on; `comment_add` re-introduces verb
  compounding; only half-structured.

### Option 3 — `resource:action:scope` (recommended)

`sample:edit:own`, `sample:edit:global`, `variant.comment:add:own`,
`variant.comment:add:global`, `tier:remove:global`, `report:preview`,
`role:create`, `audit_log:view`.

Rules:
- Three colon-separated segments: `resource:action[:scope]`.
- `resource` is singular, lowercase, dot-nested for sub-resources
  (`variant.comment`, `sample.comment`).
- `action` is one of a closed verb set: `view, create, edit, delete, list,
  download, preview, assign, remove, add, hide, unhide, apply, manage`.
- `scope` is omitted (= "any/N/A"), `own`, or `global`. No other values.
- All lowercase, no plurals.

- **Pros:**
  - Fully parseable — `perm.split(":")` gives `(resource, action, scope)`.
  - Scope is a first-class field, not a name fragment. Eliminates the
    `add_global_variant_comment` vs `add_variant_comment` ambiguity.
  - Maps 1:1 to a `@require_permission("sample:edit:global")` decorator.
  - Lets the `permissions` collection grow a real schema
    (`{resource, action, scope}`) in a future migration without renaming
    again.
  - Wildcards become trivial (`sample:*`, `*:view`, `sample:edit:*`).
- **Cons:**
  - 64 strings to rewrite (one-shot codemod + Mongo migration script).
  - Slightly longer to type than `edit_sample`.
  - Templates have to update every `has_access(...)` call site.

### Option 4 — Attribute-based access control (ABAC)

Drop named permissions; check `(user.role, action, resource_instance)` against
policies.

- **Pros:** maximally expressive; handles per-row scoping (e.g. "edit samples
  in your assay group only") natively.
- **Cons:** large rewrite; no off-the-shelf Flask library that fits the
  current handler pattern; postpones the problem we're trying to solve
  (consistent naming) by replacing it with a policy DSL. Defer.

### Option 5 — Cleaned snake_case (no separators)

Same as today but enforce one verb set, no plurals, scope-as-suffix only:
`sample_edit`, `sample_edit_global`, `variant_comment_add_global`.

- **Pros:** tiny migration; no template syntax change.
- **Cons:** still not parseable (where does the resource end and the action
  begin in `variant_comment_add_global`?); just delays Option 3.

## Recommendation

**Adopt Option 3 — `resource:action[:scope]`.**

Rationale:
- Scope is the single biggest source of inconsistency in the current set;
  promoting it to its own segment fixes that permanently.
- The closed verb set kills the `manage_*` / `modify_*` / `assign_*` drift.
- One-time migration cost is bounded (64 strings, ~80 template call sites)
  and codemoddable.
- It's the only option that lets us add a server-side
  `@require_permission(...)` decorator in F2 without renaming again later.
- It does not preclude moving to ABAC later — `resource:action:scope` is a
  natural input to a future policy engine.

## Migration plan (not part of F5 — sequencing only)

1. **Freeze new permissions** in the old format. New work uses Option 3
   strings from day one.
2. **Add a code-side registry** (`coyote/auth/permissions.py`) with one
   constant per permission. Templates start importing from the registry via
   a Jinja global. Typos become `AttributeError` at render time.
3. **Dual-write in `has_access`**: accept both old and new strings, log a
   deprecation warning when the old form is seen. Run for one release.
4. **Mongo migration script** rewrites `permissions._id` and every
   `roles.permissions[]` array entry. Backfill `resource/action/scope`
   columns.
5. **Codemod templates** (regex on `has_access\(['\"]([a-z_]+)['\"]`) using
   the old→new map.
6. **Drop the old-form fallback**, delete dead permissions identified in the
   inventory (18 of 64), and ship.
7. **Then** introduce the `@require_permission` route decorator (F2).

Steps 1–2 can land independently and unblock everything else. The full
migration is roughly one focused PR per step.

## Open questions

- Should `:own` be the implicit default (omit when "own"), or always
  explicit? Recommendation: **always explicit** when ownership matters,
  omit only when scope is genuinely N/A (`role:create`, `audit_log:view`).
  Implicit defaults are how we got `edit_sample` vs `edit_sample_global`
  in the first place.
- Wildcards in role definitions (`sample:*`) — supported from day one, or
  later? Recommendation: later. Start with explicit grants; wildcards can
  be added once the closed verb set is stable.
- Sub-resource dot-nesting (`variant.comment:add:global`) vs flat
  (`variant_comment:add:global`)? Recommendation: **dot-nested.** Keeps
  the resource segment tokenisable and matches how the data is actually
  shaped (a comment belongs to a variant).
