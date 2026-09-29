# Assay Subpanels

Group choices come from `assay_groups`. Named subpanel choices come from
`subpanels` and their active assay associations, not a software-defined list.
ISGL diagnosis fields use those choices for the selected assays; the implicit
`base` scope is the default. New assignments reject unregistered or unassociated
subpanels. Unchanged historical ISGL assignments are retained when editing metadata.

ASPC and clinical-rule creation offer Base plus the selected assay's active named
subpanels. Both the shared definition and its assay association must be active.
Changing the ASP clears incompatible selections; ASPC subpanel selection returns
to Base when its previous value is no longer available. ISGL diagnosis choices
combine the active subpanels of its selected assays. Changing assay groups also
clears any assays and diagnoses that no longer match.

An ASP identifies an assay. A subpanel has one shared identifier and display
definition, and can be associated with several assays. Each association can be
disabled independently. Sharing a subpanel does not share ASPCs, genes or report rules.

## Administration

Two administration pages separate shared definitions from assay availability.
Both require `assay.panel:list` and `assay.panel:view`; mutations also require
`assay.panel:edit`.

### Subpanel Definitions

Open **Admin > Subpanel definitions** (`/admin/subpanels`). Each shared definition
appears once. **Create subpanel** opens its name, identifier, description, global
status and checkboxes for available active ASPs. Assay search filters the list
without discarding selections. Saving creates one definition and all selected
associations in one transaction. An unassigned definition is also allowed.

The identifier is generated from the display name and can be edited before
creation. Existing definitions keep their identifier. Editing changes shared
metadata and global availability and can add assay associations. Existing links
are checked and locked, including inactive links; saving never removes or
reactivates them. Use **Assay associations** to deactivate or reactivate a link.
Metadata and new links are saved in one transaction with a shared revision check.

Removing a link could leave ASPCs and report-rule scopes without a registered
association. Links are therefore additive: deactivation excludes a scope from new
selections while preserving its identity and history. Existing samples, annotations
and saved reports are not rewritten. New configurations and setup validation
still require active associations. Adding an assay does not create its ASPCs,
ISGLs or report rules automatically; configure those separately.

`PUT /api/v1/resources/subpanels/{subpanel_id}` accepts `add_asp_ids` alongside
shared metadata and `expected_version`. An omitted or empty list preserves all
links; submitting an existing link leaves its status unchanged. The definitions
response includes `associated_asp_ids` for both active and inactive links.
The audit event records the requested additions and shared revision numbers.

### Assay Associations

Open **Admin > Assay subpanel associations** (`/admin/assay-subpanels`) and select
an ASP. Only subpanels already associated with that assay are shown, including
inactive links. Use **Activate** or **Deactivate** to change that assay's
availability without affecting other assays. There are no association creation or
definition-edit controls on this page. The same association controls appear in the
ASP editor.

A globally retired definition cannot be enabled for an assay. Its existing links
can still be disabled. Reactivating a shared definition does not reactivate disabled
links. Global status and assay-link status are displayed separately.

| Operation | Permission | Effect |
| --- | --- | --- |
| View | `assay.panel:view` | Inspect current definitions and assay associations, including retired scopes |
| Create shared definition | `assay.panel:edit` | Register one shared scope, optionally associating active ASPs |
| Edit shared definition | `assay.panel:edit` | Save a new shared metadata revision; applies to every associated assay |
| Activate/deactivate association | `assay.panel:edit` | Change availability for one assay without changing the shared definition |

The UI also requires `assay.panel:list` to select assays. Status actions appear
in the **Actions** column. The **Created by / Installed by** column uses recorded
creation metadata, not `updated_by`. Records without creation attribution show
**Unknown**; revision history and audit events retain the operators who edited them.

The `base` scope is implicit when no subpanel is specified. Neither ASP creation
nor the registry backfill inserts a `base` document. ASPC and clinical-rule
selectors offer Base without requiring a registry record. Only named subpanels
are registered; Base cannot be created, edited or retired. There is no
subpanel deletion endpoint. Successful mutations use the administrative audit
middleware and record the scoped identity and revision numbers. Saves require the
version the operator edited; concurrent changes return a conflict instead of
silently overwriting another user's work.

## Configuration Order

For a new assay, use the [Assay setup workspace](assay-setup.md) to save the
following configuration as a draft and activate it after independent review.
The individual resource pages remain available for existing assays.

1. Save the draft assay definition with its identifier, registered active group,
   family and DNA/RNA category. The operational ASP is created only at activation.
2. Use the implicit Base scope, or associate additional named subpanels as needed.
   A base-only assay needs no subpanel registry entries. Named subpanels do not
   require an ISGL to exist first.
3. Stage gene lists and prepare compatible published reporting rules for the intended scope.
4. Stage each required ASPC. Both its subpanel selector and the clinical-rule creation selector
   offer Base by default and list active definitions belonging to the selected ASP.
5. Submit the setup for independent review and activation, then configure public
   catalog presentation through its separate publication workflow.

Registering a subpanel does not create gene lists, clinical rules, an ASPC, or public
catalog content. ISGL `diagnosis` remains an existing gene-list association field;
changing it does not register or remove subpanels. New clinical-rule scopes are
validated against the registry, including imported definitions. Catalog content
retains its existing authoring workflow and configuration references.

Retirement excludes a scope from new ASPC assignments. Existing ASPCs remain
editable with their original scope, and historical samples and reports are not
modified. Changing an ASPC's assay or subpanel requires creating another ASPC.
This registry does not change ingest resolution or existing sample ASPC bindings.

## Persistence And API

Two application-database collections store the registry. Their names are configured
by `primary.subpanels_collection` and `primary.subpanel_associations_collection`
in `api/config/center/collections.toml`.

| Collection | Current identity | Purpose |
| --- | --- | --- |
| `subpanels` | `subpanel_id` | Shared name, description and global availability |
| `subpanel_associations` | `asp_id`, `subpanel_id` | Independent availability within an assay |

| Field | Meaning |
| --- | --- |
| `asp_id`, `subpanel_id` | Stable scoped identity |
| `display_name`, `description` | Human-facing metadata in the shared definition only |
| `is_active` | Global availability on a definition; assay-specific availability on a link |
| `version` | Monotonically increasing metadata revision |
| `is_current` | Selects the current revision, including a retired definition |
| `updated_by`, `updated_on` | Operator and UTC time for this revision |

Unique indexes enforce one current document per identity and unique
`(asp_id, subpanel_id, version)` revisions. Previous revisions retain their content;
only their `is_current` marker changes. Revision replacement is transactional and
requires MongoDB replica-set support, including a single-member development set.

| Method | API path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/resources/asp/{asp_id}/subpanels` | List current definitions |
| POST | `/api/v1/resources/asp/{asp_id}/subpanels` | Create a definition |
| PUT | `/api/v1/resources/asp/{asp_id}/subpanels/{subpanel_id}` | Replace metadata using `expected_version` |
| GET | `/api/v1/resources/subpanels` | List shared definitions |
| POST | `/api/v1/resources/subpanels` | Create a shared definition and selected `asp_ids` atomically |
| PUT | `/api/v1/resources/subpanels/{subpanel_id}` | Explicitly revise shared metadata using its own `expected_version` |
| PATCH | `/api/v1/resources/asp/{asp_id}/subpanels/{subpanel_id}/status` | Set `is_active` for one link using its `expected_version` |

## Existing Installations

Before enabling administrative writes with this release, back up configuration
collections and register existing scopes. The migration reads ASPs, ASPCs, clinical
rule scopes and active ISGL diagnosis associations. Existing ASPs, ASPCs and ISGLs
remain valid; the registry adds definitions for their existing identifiers rather
than replacing those records. It does not read or modify samples. Unknown parent
references and identifiers that would require renaming stop planning before writes.

The migration also reads current entries from the previous `assay_subpanels`
collection. Equal identifiers consolidate into one definition only when display
names and descriptions agree. Conflicts stop planning. Each previous assay-specific
active state becomes its link's active state. Shared definitions start active;
disabled links remain disabled. New association history starts at revision 1;
the old collection is not used for runtime lookup. Base entries are not copied.
After verifying the shared registry, use the
[reference database migration](../operations/reference_database_migration.md)
to archive and remove the old collection. Its previous revisions remain in the
restricted BSON backup, not in the runtime collection contract.

The migration also checks distinct `annotation.assay` / `annotation.subpanel` pairs.
`annotation.assay` identifies an **assay group**, not an ASP; `annotation.subpanel`
uses exact matching with `subpanel_id` within that group. Historical ASP
group memberships and retired registry definitions are included in this check.
Only these scope fields are aggregated; annotation content is neither returned nor
modified. Missing, null or empty subpanels represent the implicit base scope for
registry planning; this migration does not rewrite historical annotation fields
or change their lookup behavior. Explicit `base` references need no registry match.

An annotation-only scope with no matching configuration or registry definition
is reported as a warning, not registered automatically. Historical and cross-assay
annotations need not belong to a current ASP. Review ownership before registering
an applicable definition in **Admin > Subpanel definitions** and associating its
intended ASPs. A shared group does not
justify automatically assigning a scope to every assay in that group. Noncanonical
annotation identifiers still stop planning; this command does not rename them.
Changing a display name does not change annotation matching; stable identifiers do.

With `COYOTE3_MONGO_URI` and `COYOTE3_DB` exported for the intended environment:

```bash
# Read-only plan; does not create indexes.
.venv/bin/python scripts/migrate_assay_subpanels.py --actor operator

# Insert missing registry definitions and ensure their indexes.
.venv/bin/python scripts/migrate_assay_subpanels.py --actor operator --apply
```

Use `--db` and `--mongo-uri` only when explicit overrides are required. Avoid putting
credentials in shell history. Run with configuration writes paused. Existing
registry definitions, including retired ones, are preserved on subsequent runs.
Each definition is committed separately; an interrupted migration can be rerun.
Generated display names preserve existing identifiers and should be reviewed in
the admin UI. New demo bootstraps derive registry records from their seed scopes.

## ISGL Identity And Names

`isgl_id` is the stable gene-list business key across revisions. MongoDB `_id`
identifies an individual revision. Keep identifiers lowercase with no spaces;
hyphens and underscores are accepted and remain distinct. `displayname` is the
preferred readable name. `aliases` contains additional searchable names, with
spaces and mixed case allowed. Edit aliases in the gene-list administration form.
Aliases are not unique keys and never resolve configuration references.

`diagnosis` contains subpanel association identifiers, not aliases for the list.
For example, `isgl_id: breast-panel`, `displayname: Breast cancer panel` and
`aliases: [BC panel]` can coexist with `diagnosis: [breast]`. An alias does not add
another subpanel or change its clinical scope.

For existing ISGL diagnosis spelling, the migration supports an explicit mode:

```bash
# Review first: lowercase diagnosis values and replace whitespace with hyphens.
.venv/bin/python scripts/migrate_assay_subpanels.py --actor operator --normalize-isgl-diagnosis

# Back up configuration data and pause writers before applying.
.venv/bin/python scripts/migrate_assay_subpanels.py --actor operator --normalize-isgl-diagnosis --apply
```

This mode normalizes ISGL diagnosis arrays, including inactive revisions, and
inserts missing registry definitions in one transaction. It preserves gene-list
IDs, names, aliases, genes and revision numbers. Changed records receive the
operator and update time. Distinct spellings collapsing to the same identifier
stop planning. `BC` becomes `bc`; `breast cancer` becomes `breast-cancer`. These
remain separate scopes, not inferred synonyms.

This is not a blanket database rename: noncanonical ASPC, rule or annotation
scopes still block application. Clinical records, published rules, report snapshots
and audit history are not rewritten by this command. Such references require a
separately reviewed migration to preserve clinical matching and provenance.

## Additional Analysis Types

Existing `asp_group`, `asp_family`, `asp_category`, `analysis_types`, and identifier
keys retain their meanings. This registry adds interpretation scopes, not processing
capabilities. Registering a clonality or methylation label does not add ingestion,
viewers, filters, or reporting support for those result types. Those capabilities
require explicit contracts and tested implementations before operational use.
