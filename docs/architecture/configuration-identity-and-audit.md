# Configuration Identity And Audit

Coyote4 uses stable clinical identifiers, one active configuration record per
clinical scope, and an operational audit trail. Sample review and report records
retain the configuration identity and filter state used at the time.

This page describes the production architecture. It is intended for clinical
administrators, developers, and operators who maintain ASP, ASPC, and ISGL
configuration.

> **Info**
>
> Application timestamps are stored in UTC. The user interface renders them
> in the deployment's configured local time zone.
>

## Identity Model

Clinical identifiers are machine join keys, not display labels. They are used
by configuration records, samples, filters, static report-rule directories,
and access scopes. The same canonical value must therefore be used wherever a
clinical scope is referenced.

| Identifier | Represents | Primary use |
|---|---|---|
| `asp_id` | Physical assay definition | Connects an assay to its platforms, coverage, and assay family |
| `diagnosis_id` | In-silico diagnosis within an ASP | Selects scoped filters, gene lists, and report rules; `base` means no diagnosis-specific configuration |
| `aspc_id` | Active assay configuration | Identifies the resolved ASP, diagnosis, and environment configuration |
| `isgl_id` | In-silico gene list | Identifies a reusable curated gene scope |
| `sample.name` | Clinical sample identifier | Human-facing sample identity and URL segment |

### Identifier grammar

| Rule | Requirement | Example |
|---|---|---|
| Case | Input is converted to lowercase before storage | `Hem-Snabb` becomes `hem-snabb` |
| Allowed characters | Lowercase letters, digits, underscore, and hyphen | `demo-solid_gmsv3`, `hem-snabb` |
| Separator semantics | Hyphens and underscores are both valid and remain distinct | `hem-snabb` is not the same key as `hem_snabb` |
| Disallowed characters | Whitespace, dots, slashes, and other punctuation are rejected | `Hem Snabb` and `gms.v1` are invalid |
| Display text | Human-readable labels are kept separately from identifiers | `Hem-Snabb` can be displayed while `hem-snabb` is stored |

This policy prevents silent key rewrites. A configuration that is not valid at
creation time cannot later become unreachable because a space, period, or
changed separator was normalized differently by another service.

## Active Clinical Configuration

![Managed configuration update flow](../assets/diagrams/configuration-resource-update.svg)

ASP, ASPC and ISGL each have a stable identifier. Each identifier can have one
active revision and retained historical revisions. Each sample uses its recorded ASPC.

| Resource | Stable key | Revision key | Owns |
|---|---|---|---|
| ASP | `asp_id` | `(asp_id, version)` | Physical assay and platform definition, assay family, coverage, and supported scope |
| ASPC | `aspc_id` | `(aspc_id, version)` | Environment-specific enabled analyses, filter profiles, reporting configuration, and rule resolution scope |
| ISGL | `isgl_id` | `(isgl_id, version)` | Typed curated genes and permitted assay/diagnosis associations |

When intake or a sample update requests a named diagnosis, its shared definition
and assay association must both be active. If its environment has no matching
ASPC, the active `base` configuration can supply the defaults. The sample keeps
the requested diagnosis and the UI identifies the fallback.

### Revision protocol

1. Creating a resource activates version 1. Editing it creates the next active version and records the previous ObjectId in `supersedes_id`.
2. An ASP or shared ISGL edit advances the affected active configurations in the same transaction. Samples keep their previous ASPC until explicitly updated.
3. Version history and the audit trail retain the superseded revisions and the actor responsible.

Active reads remain unambiguous because a partial unique index permits only one
active document per business identifier. Compound unique indexes prevent two
documents from using the same business identifier and version. Activation and
its audit record require a MongoDB replica set.

## Audit Events

Audit events describe significant operational actions. They are separate from
the resource document and do not store a second complete copy of configuration
or secret material.

### Events recorded for managed clinical resources

The ASP, ASPC, and ISGL administration routes record successful create, update,
status, and retirement actions as permanent traceability events. Failed HTTP
requests remain visible as operational request or mutation failures and follow
the operational retention policy. Events contain the following context.

| Field | Meaning |
|---|---|
| Event type | Domain action such as `configuration.created` or `configuration.revision_rotated` |
| Resource type | Component collection or assay identity |
| Resource identifier | Business key and display identity needed to find the affected resource |
| Actor | Authenticated user responsible for the action |
| Timestamp | UTC time at which the request completed |
| Outcome | Success or failure |
| Request context | HTTP method, route, request ID, and permitted operational metadata |
| Error context | Sanitized failure reason when an action cannot complete |
| Revision context | Previous and successor version and document identifiers for a successful rotation |

Audit events are also produced for clinically important actions such as sample
ingest success or failure, sample deletion, report creation, and variant
curation. This provides an operational timeline without making audit records a
replacement for clinical report snapshots.

> [!CAUTION]
>
> Audit metadata must not include passwords, session tokens, API tokens, or
> unrestricted source-file content. Error details are sanitized before they
> are persisted or presented to users.
>

ASP, ASPC, and ISGL mutations are stored as `traceability` audit events. These
events have `immutable: true`, do not receive `expires_at`, and are excluded
from both MongoDB TTL expiry and application retention cleanup. Routine request
and runtime events use the expiring `operational` class. Database access and
backups remain part of the control boundary: a privileged MongoDB operator can
still alter data outside the application.

## Report Reproducibility

Current configuration and report reproducibility serve different purposes.

1. A sample resolves an active ASPC by its canonical assay, diagnosis, and
   environment scope.
2. The reviewer changes filters or selected gene lists as needed during review.
3. Report preparation builds the exact finding and text context from that
   state.
4. Saving the report stores the resolved ASPC identity, applied filter snapshot,
   selected gene-list context, reportable finding snapshots, rendered output,
   and static-rule identity/content hash.

New samples use the active configuration for their scope. An existing sample changes its ASPC
when an authorized user reviews and applies the update with a reason. A saved
report retains the configuration and rule evidence captured when it was created.

## Operational Migration Policy

For a first installation, upload the editable definitions on their individual Admin pages.
Successful imports receive local revision IDs, timestamps and actors. Reporting rules go through
their publication workflow. See [Install assay resources](../administration/install-assay-resources.md).

## Configuration Relationships

![Clinical resources and saved evidence](../assets/diagrams/collection-relationships.svg)

For the complete clinical data path, see
[Clinical Data Preparation And Reporting Flow](clinical-data-and-reporting.md).
