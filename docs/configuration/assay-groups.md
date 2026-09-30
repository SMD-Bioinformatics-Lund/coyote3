# Assay Groups

Assay groups are stable scope identifiers shared by ASPs, ASPCs, gene lists,
annotations and user access assignments. The `assay_groups` collection belongs
to the application database; each environment manages its own registry.

## Administration

Open **Admin > Assay groups** (`/admin/assay-groups`). Search the registry or
select **Create group**, enter a display name and description, review the
suggested identifier, and save. Identifiers use lowercase letters,
numbers and single underscores between words. Hyphens, spaces and leading,
trailing or repeated underscores are rejected for new groups. Existing group
identifiers are not renamed. Spaces are allowed in display names, not keys.

| Operation | Permission |
| --- | --- |
| View the registry | `assay.panel:view` |
| Create a custom group | `assay.panel:edit` |
| Activate or deactivate a group | `assay.panel:edit` |

Creation records the authenticated creator and timestamp and produces a
managed-resource audit event. The API rejects client-supplied ownership and
creation metadata. System entries are labeled **System**; custom entries are
labeled **Center**.

Identifiers, display metadata and system ownership cannot be edited or deleted
through the application. Operational availability can be changed for both system
and center-owned groups. Duplicate identifiers return HTTP 409. Stable keys
preserve joins and access scopes on existing records.

## Operational availability

Select **Deactivate** to inspect affected assay identifiers, enter a reason and
confirm. **Activate** uses the same confirmation flow. Status updates require the
version inspected by the operator; a concurrent change returns HTTP 409 and
requires reloading. The audit event records the old and new status, revision and
reason; the registry records the latest actor and timestamp.

An inactive group blocks new assay creation/activation, ASPC creation and active
revisions, setup publication, clinical-rule publication, ingest and new access
assignments. Related assays are excluded from public catalog offerings and new
selection lists. Public catalog publication validates the currently available
assays. Ingest updates are also blocked; queued jobs check availability when they
run. This switch is not a cancellation mechanism for work already in progress.

Existing samples, annotations, reports and configuration history remain readable
under their existing access permissions. Clinical review and reporting of existing
samples are not disabled. Child records are never marked inactive by a group
status change. Reactivation makes only individually active children available.
Shared subpanels and gene lists retain availability through other active groups.

## Configuration order

1. Install the system groups and register any additional center groups.
2. Select a registered group when creating an ASP or assay setup draft.
3. Configure subpanels, gene lists, reporting rules and ASPCs for that assay.
4. Assign assay and group access explicitly through user administration.

ASP, ISGL and user-access forms read group choices from the registry. ASPC group
values follow the selected ASP. DNA/RNA and panel/WGS/WTS remain separate assay
properties. Registering a group does not create an assay, rewrite annotations,
grant access, add report wording or introduce group-specific clinical query rules.

## Installation

New database bootstrap includes
`api/config/bootstrap/reference/assay_groups.seed.ndjson`: `hematology`, `myeloid`,
`lymphoid`, `solid`, `pgx`, `tumwgs`, `wts`, `fusion` and `demo`, with
`system_managed: true`.

`demo` is reserved for demonstration and training assays; it does not grant
access or change the deployment environment. Environment choices remain
application-configured, not entries in this registry.

For an existing deployment, export the intended `COYOTE3_MONGO_URI` and
`COYOTE3_DB` in the shell, then run the installer before starting the updated API:

```bash
# Validate and count missing definitions without writing.
.venv/bin/python scripts/install_assay_groups.py --actor "$USER"

# Create the registry index and insert missing definitions transactionally.
.venv/bin/python scripts/install_assay_groups.py --actor "$USER" --apply
```

The script does not automatically load a local environment file. `--mongo-uri`
and `--db` override exported settings. Use a replica-set connection with permission
to create the registry index and insert application records.

Existing canonical groups found in ASP, ASPC and ISGL configuration are registered
as center-owned entries when they are not bundled system groups. The installer
does not scan or modify annotations, samples, identity accounts or reports.
Noncanonical scope identifiers require review; they are not silently renamed.
Existing registry documents are preserved on repeated runs.
The installer also initializes missing `is_active` and `version` fields to `true`
and `1`. It never overwrites an existing inactive status or revision. Run this
step before deploying availability-aware API code to an existing registry.

## Collection and API

| Field | Purpose |
| --- | --- |
| `group_id` | Unique stable scope key; referenced as `asp_group` or `asp_groups` elsewhere |
| `display_name` | Human-readable registry label |
| `description` | Optional explanation of the group's purpose |
| `system_managed` | Server-owned flag distinguishing bundled and custom definitions |
| `created_by`, `created_on` | Creation provenance |
| `is_active` | Root availability switch for new operational use |
| `version` | Optimistic concurrency revision, incremented on each status change |
| `publication_serial` | Internal transaction counter serializing assay setup publication with group availability changes; not editable |
| `updated_by`, `updated_on`, `status_reason` | Latest availability change provenance |

Setup publication increments `publication_serial` only while the group is active,
inside the activation transaction. Failed activation rolls back the increment.
Existing records without this counter start at zero; no backfill is required.
It does not increment the administrator-facing status `version`.

`GET /api/v1/resources/assay-groups` lists definitions.
`POST /api/v1/resources/assay-groups` accepts only `group_id`, `display_name` and
optional `description`. The unique `assay_group_id_unique` index prevents
duplicate keys even when administrators create groups concurrently.

`GET /api/v1/resources/assay-groups/{group_id}/impact` returns the current group
and affected assay identifiers without sample information.
`PATCH /api/v1/resources/assay-groups/{group_id}/status` accepts `is_active`,
`expected_version` and a nonblank `reason`.
