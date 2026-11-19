# Assay Setup

An assay is a center-defined sequencing offering. Its name does not require a
dedicated code path: it selects compatible [application-supported analyses](supported-capabilities.md).
The setup workflow configures those analyses for the assay's diagnoses and environments.

Follow the numbered setup procedure first. The workspace, naming and version
references below provide detail when you need it.

## Starting A Setup

Register an [assay group](assay-groups.md) before starting a new assay setup.
The assay form uses the database registry, including center-owned groups.
An inactive group blocks new setup saves, submission and activation. Existing
clinical records remain accessible; disabling a group does not rewrite child statuses.

Open **Admin > Assay setup** (`/admin/assay-setups`) to prepare a new assay.
The **Create** action on the ASP list opens this workspace. Existing ASPs continue
to use their individual administration pages.

Setup drafts are separate from active assay data. Saving a step does not make
the assay available to ingest, sample analysis, or the public catalog. Reopen a
draft from **Saved setups** to continue its configuration. The selector shows the
assay's short name (or full display name), assay ID, workflow status and revision.

## Step-by-step: add a new assay

Use this procedure both for a center's first assay and for additional assays in
an existing installation. Adding an assay does not require deployment, database
bootstrap, new system permissions or a new MongoDB database. Existing active
shared resources may be reused when their scope and clinical content are suitable.

### 1. Confirm authors, reviewers and the active group

Have an authorized setup author available. If requesting optional review, choose
a different qualified colleague who has not edited the setup.
Use the permissions table below; a clinical-rule reviewer/publisher also needs the
permissions for that separate workflow. Assign role permissions and assay/group/
environment access separately. A role name alone does not grant clinical scope.

Create or select the active assay group before saving the assay draft. Reuse a
suitable group rather than creating one for every assay. An inactive group blocks
new setup saves, submission and activation.

### 2. Save the assay definition in the setup workspace

On the **Assay** step, supply a stable identifier, display name, group, sequencing
family, covered genes and input-file policy. Modality (DNA or RNA) is derived from
the sequencing family and is read-only.

Declare the files the pipeline produces in `expected_files`. Use `required_files`
for inputs whose absence must reject ingest. Select only supported file and
analysis combinations, then choose **Save and continue**.

The saved draft reserves the assay identity and makes it available to the rule
builder. It does not enable ingest. Do not create a second ASP with the same identifier.
Use **Saved setups** to reopen it later; unsaved changes require saving or discarding
before leaving the form.

### 3. Select scopes and environments

**Base is always selected** and needs no diagnosis registry document. For a
base-only assay, leave named diagnoses unselected. **Production is always selected**;
other environments are optional. These are clinical configuration environments,
not separate application deployments.

For each required named scope, reuse an active shared diagnosis or select
**Manage diagnosis definitions** to register it. An unassigned definition can exist
before the assay. Return to setup and select **Refresh diagnosis definitions**,
then select the scope. Activation creates the draft assay's association; a shared
definition by itself does not configure every assay.

Only **Base / production** requires an ASPC before activation. Selecting additional
diagnoses or environments does not require every combination to be configured.
You can add these configurations later from **Assay Configurations**. Any optional
configurations included in the setup must still pass validation before activation.

### 4. Prepare the gene lists that filters will select

In **Gene lists**, stage new analysis-specific ISGLs or reuse active eligible lists
from the assay/group. Review genes, list type, display name and diagnosis/scope
bindings. Diagnosis identifiers on staged lists must belong to the selected setup
scopes. A list for SNV does not automatically become a CNV or fusion list.

This step may be left empty when the intended filters do not select an ISGL.
Do not create an empty placeholder merely to proceed. Without selected lists or
ad-hoc genes, findings use the assay's covered genes. For CNVs, no selection and no
panel genes means no gene restriction; SNVs, fusions and translocations return no
findings when their eligible gene scope is empty. Coverage has its own scope.
Check the [gene-scope rules](../user-guide/gene-lists-and-assay-context.md#when-no-gene-list-is-selected)
before approving the assay.

### 5. Optionally publish reporting rules

After saving the assay draft, use **Open rule builder**. Select the draft assay,
DNA/RNA analyte, Base or registered named scope, and intended reporting language.
Author the clinical content, declare the analyses used by the report sections,
run its tests, and complete independent clinical review and publication.

Return to setup and choose **Refresh reporting rules**. Draft or merely reviewed
rules are not used for report generation. An exact named-scope release is
used when published; otherwise resolution can use a compatible assay Base release
for the same analyte and language. Do not assume a different language or another
assay's rule will be selected.

Rules and ISGLs can be prepared in either order after their assay/scope dependencies
exist. Neither publishes the other. Reporting rules are optional: setup can be
reviewed and activated without a compatible publication. The UI warns that reports
will be available without an automatically generated summary. Existing published
rules must pass integrity and compatibility checks. Individual ASPC creation and
editing do not require a rule publication.

### 6. Complete the Base / production ASPC

In **Configurations**, select **Add** for **Base / production** and save its settings.
Other scope/environment combinations are optional. Use **Edit** to update a saved
configuration in this setup.

Review enabled analyses and intents, thresholds, consequences, analysis-specific
gene lists, report sections and language. Analyses must be supported by the assay's
files and sequencing family. Report sections must be enabled analyses; when a
published reporting rule resolves, its declared analyses must also cover those sections.
Selected gene lists must be active and compatible with the analysis and assay scope.

To load a file, use **Import configuration JSON** in this editor. Import fills the
form without saving or publishing. The assay, group, modality, diagnosis and
environment must match the selected scope. Review the values and save. Omit
`profile_sources` and `profile_overrides`: these fields are computed by the server.

Use this setup editor for an unpublished assay. The standalone **Assay Configurations**
page requires an activated assay. A reusable configuration profile is not required.

### 7. Review, submit and activate

Open **Review** and resolve readiness errors. Choose one of these paths:

- **Publish and activate:** an authorized editor can activate a draft without
  colleague review. The publication records that no review took place.
- **Submit for review:** select **Reviewer for optional review** and submit. The
  assigned independent reviewer can **Approve and activate** or **Return for changes**
  with a reason. Submitted content is read-only; editors can **Return to draft**
  with a reason to revise it.

Saving or submitting does not activate the assay. Activation rechecks dependencies
and creates the assay, diagnosis associations, gene lists and configurations in
one transaction. If a dependency changed after submission, return to draft and
review it again. Reporting-rule publication remains separate.

After activation, use **View activated assay** or **Manage assay configurations**
for subsequent changes. See [review and activation](#review-and-activation) for
reviewer eligibility and failure handling.

### 8. Verify with a representative validation sample

Confirm the activated ASP and intended ASPCs are available. Assign users the
necessary assay/group/environment access, then ingest an approved validation
sample with matching assay, scope, environment and declared file types.

Check the resolved ASPC and any Base-fallback warning, expected-data availability,
analysis tabs, filter defaults, selected gene lists, report preview, saved report
and audit records. Missing optional evidence does not prove that an analysis
returned zero findings. Do not accept the assay for clinical use until its intended
review and reporting workflow passes the center's validation.

### 9. Publish the public catalog only if required

An operational assay need not appear in the public catalog. If public presentation
is required, create its catalog content after activation and complete the catalog's
separate review/publication workflow. Catalog publication does not activate an ASP,
create an ASPC or make sample data public.

Synthetic [workflow exercises](../testing/clinical-workflow-demo.md) can supplement
the center validation required in step 8.

## Gene-list creation order and associations

A gene list can exist before its assay. Leave **Assays** empty and use Base until
named diagnoses are associated. In setup, **Existing gene lists** searches the
registry, including unassigned lists. Link active center-owned lists or stage new ones.

Links take effect at activation. The operation creates new list revisions with the
assay/group associations while preserving genes and original creation attribution.
If a list changes after submission, return to draft and check it again. Removing a
selection or using **Clear selected lists** changes only the draft, not the stored list.

For an active assay, use **Admin > Assays > Edit > Existing gene lists**, or edit
**Assays** on the gene-list page. Both update the same association. Unlinking an
assay preserves other assay links and group scope, so a group-scoped list may remain
available. Concurrent changes require reloading before saving.

Browsing requires `gene_list.insilico:list`; linking or changing existing lists
requires `gene_list.insilico:edit`, including at activation. System lists remain
protected. Named diagnoses must be among the setup's selected scopes.

Linking makes a list available; choose it in the configuration to apply it to an
analysis. Ad-hoc lists are excluded from standard configuration choices.

## Workspace controls

Use **Saved setups** to search by assay or reviewer and filter by workflow state.
Select a setup to resume it. Save or discard unsaved changes before switching.

Sequencing family determines modality. Accepted files determine required-file
choices and available analyses; changing them removes incompatible selections.
Edit filters and report settings through their controls. Configuration receipts,
release identities and promotion records are managed by the application.

## Names and identifiers

| Field | Use |
| --- | --- |
| Identifier | Stable key for associations and lookups. Use lowercase ASCII letters/digits with single hyphens or underscores; no spaces or leading/trailing separators. |
| Name | Short label for tables and selectors where the resource supports it. |
| Display name | Full readable label, allowing spaces and capitalization. |
| Revision | Version of the resource; keep this separate from its stable identifier. |

Configuration keys are generated as `assay::diagnosis::environment`, for example
`demo-hematology_gmsv1::mpn::testing`. Hyphens and underscores are not interchangeable.
Samples pin the exact configuration revision. Renaming a display label does not
change stored associations.

Assay groups describe biological context; DNA/RNA is the modality, and panel/WGS/WTS
is the sequencing family. Each assay declares these separately. `base` is implicit;
do not register it as a diagnosis. Use the [field reference](clinical-resource-fields.md)
for exact keys and validation.

## Current versions and history

Publishing a setup keeps the final snapshot, revision number and audit events,
and removes its draft/submitted editing snapshots in the same transaction. Failed
publication retains that history. Previously stored editing history is not purged
automatically; operators can use the [snapshot cleanup procedure](../operations/maintenance-and-verification.md#remove-editing-snapshots-from-previously-published-setups).

### Published resource history

Editing an assay, configuration or gene list creates a new active revision and
retains its predecessor. Existing samples keep their assigned configuration and
captured resource versions until an explicit configuration update. Saved reports
retain their original content.

Use **Version history** to inspect retained resource revisions. The toolbar action
also accepts an identifier whose revisions are all retired. Viewing a revision
does not reactivate it.

Query rules, reporting rules and reusable profiles open on published versions.
Use the workflow selector for drafts and **Browse retired versions** for previous
publications. Drafts do not replace published behavior. New query/report-rule
publications affect subsequent matching requests without requiring a new ASPC;
existing saved reports remain unchanged.

### Copy a configuration to another scope

Assay, diagnosis and environment are fixed at creation. Use **Copy as new**, or
**Copy from setup draft** followed by **Copy staged configuration as new**. Select
a new scope under an activated assay, review the form and save. Copying does not
modify the source. If the draft changed while selecting it, select it again.

Configuration resolution uses the named diagnosis first, then Base for the same
assay and environment when no named configuration exists. Base fallback records
a warning on the sample. Review the installed [base query behavior](query-rules.md#application-base-queries-by-analysis)
when validating the assay; a separate base query profile is not required.

## When order matters

| Dependency | Required order | What can be prepared independently |
| --- | --- | --- |
| Assay group and ASP | Register/activate the group before saving the assay setup. | Shared diagnosis definitions can be created without an assay association. |
| Assay identity and rules | Author against a saved setup when available, or create an unlinked rule draft and link it later. | An operational ASP is not required to create or import a draft. A compatible available assay/diagnosis is required before submission. |
| Gene lists and rules | Referenced gene lists must be valid; reporting rules can be added later. | ISGL authoring and rule authoring/publication have no required order relative to each other. Missing reporting rules produce a warning and no automatic summary. |
| Named scopes and configurations | Register and select the named scope before configuring it. | Base has no definition or association to create. |
| ASPC and selected ISGL | The referenced list must exist in the draft workspace or be an eligible existing active list. | Unselected lists are optional and do not block setup. |
| Setup and catalog | Activate operational resources before catalog publication. | Public wording can be prepared separately; it does not control ingest. |

For the behavior of each missing prerequisite, see the
[resource and availability reference](clinical-configuration-resources.md#missing-prerequisites-and-their-effects).

## Review and activation

A reviewer must be active, have the required access and permissions, and have no
content edits on the setup. The selector excludes ineligible users. Eligibility
is checked again at publication. Returning to draft clears the assignment but
retains it in revision history. Published setup snapshots are read-only.

Submission sends the reviewer a linked notification through background delivery.
A delayed maintenance queue can delay that notification without undoing submission.

Activation checks dependency versions and, for submitted setups, the snapshot
taken at submission. A changed dependency or concurrent edit produces a conflict.
Return to draft and review the latest values before publishing again.

The assay, diagnosis associations, gene-list changes, configurations and published
setup snapshot are committed in one MongoDB transaction. Failed writes roll back;
a replica set is required, including for local development. Concurrent group
deactivation forces an availability recheck. Activation does not change samples,
annotations or existing reports.

## Permissions

| Operation | Required permissions |
| --- | --- |
| List summaries | `assay.panel:list` |
| Inspect a setup | `assay.panel:view` |
| Open a new form | `assay.panel:create` |
| Create a draft | `assay.panel:create`, `assay.config:create`, `gene_list.insilico:create` |
| Save, submit, publish and activate | All three creation permissions plus `assay.panel:edit` |
| Return to draft / return for changes | `assay.panel:edit` |

The UI requires assay list and view access. Editing requires the creation
permissions and assay edit permission. Clinical-rule actions retain their own
permissions.
Activating a setup that links existing shared gene lists additionally requires
`gene_list.insilico:edit`; saving a draft that retains those links requires it too.
The UI explains this and keeps those edits and activation disabled without it.

A user with `assay.panel:edit` can return a submitted setup
with a reason even without the creation permissions. Publication and activation
require all the creation permissions as well. Review notes are specific to the
selected setup and are cleared when switching workspaces.

## Storage And Operations

| Collection | Identity | Purpose |
| --- | --- | --- |
| `assay_setups` | Reserved `asp_id`; `_id` identifies the workspace | Current content and governance state |
| `assay_setup_revisions` | `setup_id`, `revision` | Editing snapshots until publication; thereafter the final published snapshot |

Collection names are configured in `adapters/mongo/src/coyote_mongo/config/collections.toml`. Install
their indexes using the standard command, with the intended deployment
configuration and index-management account:

```bash
PYTHONPATH=. .venv/bin/python scripts/database/manage_mongo_indexes.py apply
```

Apply indexes before starting an API configured to verify index contracts. No
existing ASP backfill or clinical data migration is required.
The optional-review request now requires `assignee` on submission. Existing submitted
setups without an assignment can still be published directly, or returned to draft
to select a reviewer. Optional `reviewer` and `reviewed_by` fields need no backfill.

Mutations record the setup identifier, assay identifier and revision in audit events.
The revision collection retains editing snapshots until publication, then the final
published snapshot. Audit events remain; see [version history](#current-versions-and-history).

API endpoints are under `/api/v1/admin/assay-setups`: list/create at the collection
path, new context at `/context`, saved context at `/{identifier}/context`, updates
at `/{identifier}`, and actions at `/{identifier}/submit`, `/publish` and `/return`.
Updates and lifecycle actions require the expected `revision`.
