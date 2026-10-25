# Assay Diagnoses

Group choices come from `assay_groups`. Named diagnosis choices come from
`diagnoses` and their active assay associations, not a software-defined list.
ISGL diagnosis fields use those choices for the selected assays; the implicit
`base` scope is the default. New assignments reject unregistered or unassociated
diagnoses. Unchanged historical ISGL assignments are retained when editing metadata.

ASPC and clinical-rule creation offer Base plus the selected assay's active named
diagnoses. Both the shared definition and its assay association must be active.
Changing the ASP clears incompatible selections; ASPC diagnosis selection returns
to Base when its previous value is no longer available. ISGL diagnosis choices
combine the active diagnoses of its selected assays. Changing assay groups also
clears any assays and diagnoses that no longer match.

An ASP identifies an assay. A diagnosis has one shared identifier and display
definition, and can be associated with several assays. Each association can be
disabled independently. Sharing a diagnosis does not share ASPCs, genes or report rules.

## Field requirements and defaults

| Field / operation | Required | Omission behavior and meaning |
| --- | --- | --- |
| Create `diagnosis_id` | Yes, 1–100 characters | Stable normalized ID; do not create the implicit Base scope. |
| `display_name` | Yes, 1–200 characters | Trimmed visible label, not the identifier. |
| `description` | No, at most 4000 characters | Empty text. |
| `is_active` | Optional on definition; required for association status changes | New definition defaults to `true`. Association status requests must name the target state. |
| Shared create `asp_ids` | No, at most 1000 IDs | `[]`: creates no selected assay associations. |
| Shared update `add_asp_ids` | No, at most 1000 IDs | `[]`: adds no associations; does not remove existing links. |
| Update `expected_version` | Yes, integer at least 1 | Required revision precondition; a stale edit must be refreshed. |

Definition availability and association availability are independent. A named
scope must satisfy both for new assignments. History and actor fields are maintained
by the service; creation fields are not a complete database-export schema.

## Administration

Two administration pages separate shared definitions from assay availability.
Both require `assay.panel:list` and `assay.panel:view`; mutations also require
`assay.panel:edit`.

### Diagnosis Definitions

Open **Admin > Diagnosis definitions** (`/admin/diagnoses`). Each shared definition
appears once. **Create diagnosis** opens its name, identifier, description, global
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

`PUT /api/v1/resources/diagnoses/{diagnosis_id}` accepts `add_asp_ids` alongside
shared metadata and `expected_version`. An omitted or empty list preserves all
links; submitting an existing link leaves its status unchanged. The definitions
response includes `associated_asp_ids` for both active and inactive links.
The audit event records the requested additions and shared revision numbers.

### Assay Associations

Open **Admin > Assay diagnosis associations** (`/admin/assay-diagnoses`) and select
an ASP. Only diagnoses already associated with that assay are shown, including
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

The `base` scope is implicit when no diagnosis is specified. ASP creation does not insert a `base` document. ASPC and clinical-rule
selectors offer Base without requiring a registry record. Only named diagnoses
are registered; Base cannot be created, edited or retired. There is no
diagnosis deletion endpoint. Successful mutations use the administrative audit
middleware and record the scoped identity and revision numbers. Saves require the
version the operator edited; concurrent changes return a conflict instead of
silently overwriting another user's work.

## Configuration Order

![Shared diagnosis cardinality across independent assays](../assets/diagrams/assay-diagnosis-cardinality.svg)

In this example, assays A and B share the same named diagnosis S, but retain separate
associations and ASPCs. Adding a target environment adds another configuration tuple;
it does not duplicate the shared diagnosis definition. Disabling one association does
not disable the other. Base configurations belong to each assay and do not require
a shared diagnosis record.

For a new assay, use the [Assay setup workspace](assay-setup.md) to save the
following configuration as a draft and activate it after independent review.
The individual resource pages remain available for existing assays.

1. Save the draft assay definition with its identifier, registered active group,
   family and DNA/RNA category. The operational ASP is created only at activation.
2. Use the implicit Base scope, or associate additional named diagnoses as needed.
   A base-only assay needs no diagnosis registry entries. Named diagnoses do not
   require an ISGL to exist first.
3. Stage gene lists and prepare compatible published reporting rules for the intended scope.
4. Stage each required ASPC. Both its diagnosis selector and the clinical-rule creation selector
   offer Base by default and list active definitions belonging to the selected ASP.
5. Submit the setup for independent review and activation, then configure public
   catalog presentation through its separate publication workflow.

Registering a diagnosis does not create gene lists, clinical rules, an ASPC, or public
catalog content. ISGL `diagnosis` remains an existing gene-list association field;
changing it does not register or remove diagnoses. New clinical-rule scopes are
validated against the registry, including imported definitions. Catalog content
retains its existing authoring workflow and configuration references.

Retirement excludes a scope from new ASPC assignments. Existing ASPCs remain
editable with their original scope, and historical samples and reports are not
modified. Changing an ASPC's assay or diagnosis requires creating another ASPC.
This registry does not change ingest resolution or existing sample ASPC bindings.

## Persistence And API

Two application-database collections store the registry. Their names are configured
by `primary.diagnoses_collection` and `primary.diagnosis_associations_collection`
in `api/config/collections.toml`.

| Collection | Current identity | Purpose |
| --- | --- | --- |
| `diagnoses` | `diagnosis_id` | Shared name, description and global availability |
| `diagnosis_associations` | `asp_id`, `diagnosis_id` | Independent availability within an assay |

| Field | Meaning |
| --- | --- |
| `asp_id`, `diagnosis_id` | Stable scoped identity |
| `display_name`, `description` | Human-facing metadata in the shared definition only |
| `is_active` | Global availability on a definition; assay-specific availability on a link |
| `version` | Monotonically increasing metadata revision |
| `is_current` | Selects the current revision, including a retired definition |
| `updated_by`, `updated_on` | Operator and UTC time for this revision |

Unique indexes enforce one current document per identity and unique
`(asp_id, diagnosis_id, version)` revisions. Previous revisions retain their content;
only their `is_current` marker changes. Revision replacement is transactional and
requires MongoDB replica-set support, including a single-member development set.

| Method | API path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/resources/asp/{asp_id}/diagnoses` | List current definitions |
| POST | `/api/v1/resources/asp/{asp_id}/diagnoses` | Create a definition |
| PUT | `/api/v1/resources/asp/{asp_id}/diagnoses/{diagnosis_id}` | Replace metadata using `expected_version` |
| GET | `/api/v1/resources/diagnoses` | List shared definitions |
| POST | `/api/v1/resources/diagnoses` | Create a shared definition and selected `asp_ids` atomically |
| PUT | `/api/v1/resources/diagnoses/{diagnosis_id}` | Explicitly revise shared metadata using its own `expected_version` |
| PATCH | `/api/v1/resources/asp/{asp_id}/diagnoses/{diagnosis_id}/status` | Set `is_active` for one link using its `expected_version` |

## ISGL Identity And Names

`isgl_id` is the stable gene-list business key across revisions. MongoDB `_id`
identifies an individual revision. Keep identifiers lowercase with no spaces;
use hyphens between distinct terms, such as `mpn-variants`. Underscores are accepted
within names and remain distinct from hyphens. `displayname` is the
preferred readable name. `aliases` contains additional searchable names, with
spaces and mixed case allowed. Edit aliases in the gene-list administration form.
Aliases are not unique keys and never resolve configuration references.

`diagnosis` contains diagnosis association identifiers, not aliases for the list.
For example, `isgl_id: breast-panel`, `displayname: Breast cancer panel` and
`aliases: [BC panel]` can coexist with `diagnosis: [breast]`. An alias does not add
another diagnosis or change its clinical scope.

## Additional Analysis Types

Diagnosis definitions describe interpretation scopes. Analysis capabilities are
defined separately in the shared capability registry. Registering a clonality or methylation label does not add ingestion,
viewers, filters, or reporting support for those result types. Those capabilities
require explicit contracts and tested implementations before operational use.
