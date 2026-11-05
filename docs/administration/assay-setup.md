# Assay Setup

An assay is a center-defined sequencing offering. Its name does not require a
dedicated code path: it selects compatible [application-supported analyses](supported-capabilities.md).
The setup workflow configures those analyses for the assay's diagnoses and environments.

Use the **Saved setups** sidebar to search by assay name, identifier or assigned
reviewer, and filter by Draft, Submitted for review or Published. Each row shows
its workflow state and revision. Selecting a row opens the existing six-step
editor on the right; filters do not change the open setup. Collapse the sidebar
when more editing space is needed. On narrow screens the list appears above the
editor. Selecting another setup or clearing the selection still checks for unsaved
form edits. Import controls, navigation and the editor share one workspace card.

Workflow badges retain text labels and use consistent colors across setup, rule,
catalog and configuration-governance pages: blue for Draft, amber for Submitted or
Pending review, mauve for Clinical review, green for Approved, teal for Published,
red for Rejected and neutral gray for Retired. These colors apply in both themes;
the label identifies the state without relying on color.

The assay editor derives modality from the selected sequencing family. Modality is
read-only; choose another family to change it. Accepted input
files determine the required-file choices and, together with sequencing family,
the available analyses. Changing a selection removes dependent choices that no
longer apply.

Gene eligibility always resolves from the sample's pinned assay configuration,
diagnosis and analysis-specific gene-list selections. Selected and ad-hoc genes
are bounded by assay eligibility for every sequencing family. An empty resolved
scope selects no findings; there is no unrestricted-scope switch or approval field.

ASPC settings-profile receipts, template releases and
promotion records are system-managed. Edit filter and reporting settings through
their structured controls and manage reusable resources through their dedicated
administration pages.

## Current versions and history

Every setup step explains read-only access. Published setups display the retained
publication snapshot; **Edit assay** opens the operational assay editor and
**Manage assay configurations** opens ASPCs, according to your permissions.
Submitted setups show the assigned reviewer and **Open review actions** for users
with assay editing permission. Return the setup to draft there, with a reason,
before editing. Drafts explain missing permissions or an unavailable editing session
beside the form.

When an assay setup is successfully published, its draft and submitted editing
snapshots are removed in the publication transaction. The final published snapshot,
revision number and audit events remain. Failed publication retains the editing
history. This applies to new publications; existing stored history is not purged
automatically. Published assay, ASPC and gene-list versions are retained as described below.

### Remove editing snapshots from previously published setups

For existing staging records, an operator can run the following in an authenticated
`mongosh` session. It targets only `coyote3_staging`, requires transactions, and
verifies that every published setup retains its final published snapshot before
removing older draft/submitted snapshots. Operational resources, published snapshots
and audit events are not deleted. Successful cleanup permanently removes the old
editing content; it does not reset revision numbers.

```javascript
function cleanupPublishedSetupDrafts(apply = false) {
  const session = db.getMongo().startSession();
  const staging = session.getDatabase("coyote3_staging");
  let snapshots = 0;
  let setups = 0;
  session.startTransaction();
  try {
    const published = staging.assay_setups.find(
      { status: "published" }, { _id: 1, revision: 1 }
    ).toArray();
    for (const setup of published) {
      const setupId = setup._id.toString();
      const retained = staging.assay_setup_revisions.findOne({
        setup_id: setupId, revision: setup.revision,
        "document.status": "published"
      });
      if (!retained) throw new Error("Missing published snapshot; cleanup aborted");
      const filter = {
        setup_id: setupId, revision: { $lt: setup.revision },
        "document.status": { $in: ["draft", "submitted"] }
      };
      const count = staging.assay_setup_revisions.countDocuments(filter);
      if (count) setups += 1;
      snapshots += apply
        ? staging.assay_setup_revisions.deleteMany(filter).deletedCount
        : count;
    }
    if (apply) session.commitTransaction();
    else session.abortTransaction();
    return { applied: apply, setups, snapshots };
  } catch (error) {
    session.abortTransaction();
    throw error;
  } finally {
    session.endSession();
  }
}
```

Preview counts without deleting, then review the result:

```javascript
cleanupPublishedSetupDrafts(false)
```

To perform the cleanup, rechecking the records in a new transaction:

```javascript
cleanupPublishedSetupDrafts(true)
```

### Published resource history

Runtime query/report evaluation resolves published rules. Configuration compilation
selects current published profiles; applied configurations retain their compiled
settings. Drafts and approved but unpublished versions are authoring work; they do
not replace the current publication. Editing a published rule creates a successor
draft, and the previous publication remains current until its successor is published.

Saving an assay, assay configuration or gene-list edit creates a new active
revision and retains its predecessor. Applied configuration revisions and their
captured assay/gene-list content remain pinned to existing samples. New assignments
resolve the current configuration; applying another configuration to an existing
sample is an explicit operation. Saved reports retain their captured content.

Assay, configuration and gene-list lists show active revisions. Select the row's
**Version history** action to load all retained revisions for that identifier.
The toolbar's **Version history** action also accepts an identifier whose revisions
are all retired. Each revision is read-only; opening it does not reactivate it.

Query rules, reporting rules and reusable profiles open on published versions.
Use their workflow selector to author drafts. **Browse retired versions** exposes
historical publications on demand; reporting rules load the selected rule set's
complete version history. Profiles use `is_current` to distinguish the current
publication from retained superseded publications. Reporting rules use `active`;
an inactive historical publication appears in retired history even when its stored
status still records that it was published. Retired catalog versions are
likewise hidden until **Browse retired versions** is selected.

Query policies and clinical reporting rules resolve from their current published
scopes. Their publication takes effect on subsequent matching requests without
creating or applying an ASPC revision. Saved reports retain their original rules.

You do not need to register a base query profile before creating an assay. The
software supplies [application base queries for each analysis](query-rules.md#application-base-queries-by-analysis).
That reference lists their evidence checks and explains how published UI rules
extend or override supported parts of the base behavior. Review these defaults
and any installed group policies when validating the assay's finding selection.

Configuration scope is fixed at creation: assay, diagnosis and environment cannot
be edited. Use **Copy as new** to create another scope. Resolution selects the named
diagnosis configuration first, then Base for the same assay and environment when
no named configuration exists. Base fallback records a warning on the sample.

On **Assay Configurations**, each saved configuration has a **Copy as new** action.
To reuse a staged configuration, select **Copy from setup draft**, choose the draft
and configuration, then **Copy staged configuration as new**. Both open the create
form for review without saving or changing the source. Select a new target scope;
the target assay must already be activated. Draft sources require assay list/view
permissions in addition to configuration create permission.
If the source draft changes while selecting a configuration, select it again
before copying; a saved selection cannot silently switch to another entry.

Analysis intents use checkboxes alongside enabled analyses. DNA supports somatic
and germline SNV review; RNA supports somatic analysis. Gene lists contain one
curated gene set. Their germline subset is resolved from its intersection with the
sample's pinned assay germline genes.

![Assay setup and resource dependencies](../assets/diagrams/assay-configuration-relationships.svg)

The diagram separates shared definitions, operational configuration, setup activation,
and catalog publication. Follow the steps below to create a new assay.

For the meaning, requirements and defaults of individual ASP, ASPC and ISGL fields,
use the [clinical resource field reference](clinical-resource-fields.md).

## Names And Identifiers

Administration uses **Assay group**, **Assay**, **Diagnosis**, **Assay configuration**,
**Gene list**, **Reporting rule set**, and **Assay catalog**. ASP, ASPC and ISGL
remain technical names in API fields and storage; changing a display label does
not change an endpoint, permission or database reference.

Assay groups describe biological or clinical context, such as hematology, solid
tumors and pharmacogenomics. DNA/RNA identifies modality; panel, WGS and WTS are
sequencing families. Fusion is an analysis type. Each assay has an explicit group,
modality and family. Parent groups provide annotation fallback evidence without
automatically sharing assay associations or configurations.

Use lowercase ASCII letters and digits for resource keys. Separate distinct terms
with hyphens (`demo-tumwgs-hema`, `mpn-variants`) and components within an assay name
with underscores (`demo-hematology_gmsv1`, `demo-solid_gmsv3`). Creation rejects spaces,
unsupported characters and leading, trailing or repeated separators with HTTP 422.
The collection contracts trim identifiers and normalize letter case to lowercase;
enter lowercase in the UI, whose creation controls validate that form directly.
Display names are independent and may use spaces and mixed case.

Configuration keys are generated as `assay::diagnosis::environment`, for example
`demo-hematology_gmsv1::mpn::testing`. MongoDB ObjectIds identify individual revisions;
samples pin the exact configuration revision. JSON field names retain underscores,
such as `asp_id` and `diagnosis_id`. Identifier punctuation is significant; lookups
do not translate hyphens into underscores or try alternate spellings.

Display names may contain spaces, punctuation and clinical capitalization, such
as **Breast Cancer** or **Hematology GMSv1**. Gene-list aliases provide alternative
readable names; references still use the stable gene-list identifier. Keep release
versions in version fields rather than changing the identifier on each publication.

Where a resource has both fields, **Name** is its short label for tables,
dropdowns, filters and compact badges (for example `HEM v1` or `FL`). **Display
name** is its full name for cards and detail headings (for example `GMS Hematology
Panel v1` or `Follicular lymphoma`). Gene lists store the full name as
`displayname`; assays use `display_name`. A missing short name falls back to the
full name, then the stable identifier. Renaming a label never changes associations
or stored reference IDs. Resources with only a display name, including diagnoses,
use it in both compact and full views. Role `name` is a stable role identifier;
its separate `label` is the readable role name.
An established assay name may contain a generation marker, such as `gmsv1`; that
is distinct from its configuration revision. `base` remains the implicit default
scope and must not be registered as a separate diagnosis.

## Starting A Setup

![Required setup order from accounts to sample review](../assets/diagrams/resource-setup-order.svg)

The numbered path shows the dependencies for a new installation or assay. Existing
accounts, groups, shared diagnoses, and eligible gene lists can be reused. Gene lists
are optional unless selected by a configuration. Publish compatible rules through
their separate review process before activating configurations that require them.

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

Open **Admin > Assay setup**, create a draft and choose **Save and continue** on
the **Assay** step to move to **Diagnoses** after validation succeeds. Supply a
stable identifier, display name, group, family, sequencing
settings, physical gene coverage and input-file policy. Define `expected_files`
for evidence the pipeline produces and `required_files` for inputs whose absence
must reject ingest. Select only implemented file/analysis combinations.

**Modality** (`asp_category`) is DNA or RNA and is derived from the sequencing
family. It is read-only; for example, `panel-dna` determines `dna`.
Saving diagnoses and environments advances to **Gene lists**. Use **Next** for
the remaining steps after saving any open gene-list or configuration editor.
Step changes, saved-setup changes, in-app links, browser Back/Forward and editor cancellation prompt before discarding
unsaved form edits. Browser reload/close prompts while an edited form is unsaved.
Imported setup JSON remains unsaved until **Save assay setup** succeeds. Import
review replaces the underlying form and uses the same navigation and reload
warnings, including before any JSON edits. **Cancel** closes the import review.
Confirming draft deletion discards its open form and clears the selection.
The setup refreshes after acquiring its edit session, then keeps the loaded form
when browser focus changes. A failed load has a **Retry loading setup** action.

This saved draft reserves the assay identity and makes it available to the rule
builder. It is not yet an operational ASP; creating it does not enable ingest.
Do not create a second ASP with the same identifier through another workflow.

### Gene-list creation order and associations

A gene list can be saved before its assay exists: leave **Assays** empty, and
leave **Assay groups** empty if the list should be unassigned. Use Base until
named diagnoses have been associated with the assay.

In the setup's **Gene lists** step, **Existing gene lists** searches the full
registry, including unassigned lists. Link suitable active, center-owned lists
or create new lists in the staged workspace. Existing-list selections are saved
in `existing_gene_list_ids`; they do not alter operational lists until
activation. Activation updates each selected list's `asp_ids` and
`asp_groups` in the same transaction as the new assay and configurations. The old
list revision remains in history; genes and original creation attribution are retained.
If a selected list changes after submission, return the setup to draft and recheck it.
Selected list identifiers have removal controls even when a list is absent from
the current search results or has become inactive. Removing a selection only
updates the setup draft; it does not delete or modify the operational list.
**Clear selected lists** removes all staged links, including when the editor lacks
permission to modify operational gene lists.

For an already registered assay, open **Admin > Assays > Edit > Existing gene lists**
to link or unlink a list. You can also edit **Assays** on the gene-list page.
Both editors use the gene list's `asp_ids` as the authoritative association, so
changes appear in both places. Unlinking an assay retains the list's other assay
links and group scope; group-scoped lists may still be offered to assays in that group.
The assay editor sends `expected_version` with the existing gene-list update
request; a stale selection is rejected rather than replacing newer associations.

Browsing requires `gene_list.insilico:list`; changing an existing list requires
`gene_list.insilico:edit`, including setup authors selecting lists and reviewers
activating those links. System-installed lists remain protected. Named list
diagnoses must be included in the setup's selected scopes.

Association does not automatically select a list for filtering or reporting.
Choose eligible lists in the assay configuration for the intended analysis type
and diagnosis. Ad-hoc lists remain excluded from standard configuration choices.

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
ad-hoc genes, applicable gene filtering uses the ASP's eligible genes. Empty
eligibility selects no findings. Confirm the intended scope before approving
the assay.

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

In **Configurations**, save the required **Base / production** configuration.
Other scope/environment pairs are marked **Optional** until configured.
The coverage table includes each saved configuration's name and Edit/View action;
empty combinations have an Add action that preselects that scope and environment.
The table shows 10 combinations per page. Saving an ASPC is available at both the
top and bottom of its editor. Displayed reporting defaults are included when saving,
including when only the report method is changed.
To load a configuration file into an existing setup, choose **Add** or **Edit**
for its scope/environment, then **Import configuration JSON**. The import loads
the form without saving or publishing. Its assay, group, modality, diagnosis and
environment must match the selected scope. Save the configuration after review;
ordinary schema validation, editing leases and revision checks still apply.
Import is unavailable for read-only forms or while the form has unsaved changes.
Use this staged editor for unpublished assays; standalone **Assay Configurations**
requires an operational assay record. Configuration files must contain editable
form fields. `profile_sources` and `profile_overrides` are server-computed fields,
not authored profile selections, and must not be included in a configuration import.
Creating a staged ASPC does not require a reusable configuration profile.
Review enabled analyses and intents, thresholds, consequence selections,
analysis-specific ISGL defaults, report sections, language and report settings.
Only analyses supported by the ASP's declared files and family are available.
Report sections must be a subset of enabled analyses and declared by the resolved
published reporting rule.

Selected ISGLs must be active, compatible with the analysis, and available through
the assay or its group. A typed identifier does not make an unavailable list valid.
The configuration cannot substitute for an absent file declaration or publish a rule.

### 7. Review, submit and activate

Open **Review**, resolve every readiness error, and select **Publish and activate**.
Review is optional for a draft: an authorized content editor may activate it directly.
Once submitted, only the assigned independent reviewer can approve and activate it.
To request that review, select
**Reviewer for optional review**, then **Submit for review**. The selector lists
active users whose active roles grant setup visibility and activation permissions,
including shared-list edit permission when needed; content editors are excluded.
Saving or submitting alone does not activate the assay. Submitted setups show
their assigned reviewer in **Saved setups**. A linked in-app review request is
delivered to that user through the committed audit/activity pipeline. Delivery can
be delayed when the maintenance queue is unavailable; it does not undo submission.

Activation rechecks dependency versions and atomically creates the ASP, named
diagnosis associations, staged ISGLs and ASPCs. If a dependency changed after
submission, return the setup to draft and recheck the new values before publishing
or submitting again. Rule publication remains a separate operation; setup activation
does not publish rules.
After publication, use **View activated assay** or **Manage assay configurations**
to continue maintenance and add optional configurations, subject to permissions.

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

## Gene Lists And Rules

Gene lists created here are staged until activation. Their assay and group
bindings come from the draft ASP. Diagnosis identifiers must belong to the
selected scopes. Existing active lists available to the assay group are also
offered by ASPC filter selectors; the workflow does not rewrite those shared lists.

**Open rule builder** opens clinical-rule administration in a new tab. Saved
setup assays are available in its assay selector even though they are not
operational ASPs. Rule authoring, testing, clinical review and publication retain
their existing lifecycle and permissions. After publishing rules, return to setup
and use **Refresh reporting rules**.

Clinical rules use their own approval/publication process. They may be published
before or after setup activation; missing rules produce a warning rather than
blocking activation. Setup activation does not publish or modify clinical-rule content.
An ASPC supplies the reporting language. Its exact diagnosis release is selected
automatically, with assay Base used only when no exact published release exists.
The analyte and declared analyses must match the configuration. Publishing a new
exact release does not require rebinding the ASPC.

Public catalog publication remains separate. Add the assay to the catalog after
activation; only the catalog workflow controls public presentation and publication.

## Review And Activation

1. Complete and save the selected configurations.
2. Open **Review** and resolve readiness errors.
3. Choose **Publish and activate** to activate directly, or **Submit for review**
   after selecting a reviewer for an optional colleague review. Submitted content becomes read-only.
4. The assigned colleague can open the saved setup, review it,
   and select **Approve and activate**, or **Return for changes** with a reason.
   Content editors cannot publish submitted setups. They can **Return to draft** with a reason.

Returning a setup restores draft editing and preserves the submitted revision.
Direct draft publication is recorded as **Published without review**. Submitted
publication requires the assigned reviewer to remain active, eligible and independent;
their approval is recorded in `reviewed_by` when they activate the setup.
Returning to draft clears the assignment; its previous value remains in revision history.
Published setup snapshots cannot be edited. Subsequent changes use the individual resource
administration pages.

Activation revalidates configurations and checks the versions of published rules,
shared diagnoses and available shared gene lists. For submitted setups it also
checks the dependency snapshot taken at submission. A dependency change requires
returning the setup to draft and rechecking before publication or resubmission.
Stale saves and concurrent publication attempts return a conflict.

The ASP, named diagnosis associations, newly staged gene lists, ASPCs, published
setup state and revision snapshot are written in one MongoDB transaction. A
failed write rolls back activation. A replica set is required, including a
single-member replica set for local development. Samples, annotations and
existing reports are not changed.

The transaction also writes an internal counter on the active parent group.
A concurrent deactivation therefore conflicts with publication and forces an
availability recheck before retrying. A group that becomes inactive before
publication commits cannot leave a partially activated setup.

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

Collection names are configured in `api/config/collections.toml`. Install
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

Mutations attach traceability audit metadata with the setup identifier, assay
identifier and revision. The workspace displays revision history; full historical
content is retained in the revision collection.

API endpoints are under `/api/v1/admin/assay-setups`: list/create at the collection
path, new context at `/context`, saved context at `/{identifier}/context`, updates
at `/{identifier}`, and actions at `/{identifier}/submit`, `/publish` and `/return`.
Updates and lifecycle actions require the expected `revision`.

## Verification

```bash
.venv/bin/pytest -q tests/unit/test_assay_setup.py --no-cov
npm --prefix frontend run test:e2e -- assay-setup.spec.ts
```

Real transaction tests require an explicitly selected disposable test replica set
through `ASSAY_SETUP_TEST_MONGO_URI`. They create a uniquely named synthetic
database and remove only that database afterward. Do not use a production account.

```bash
.venv/bin/pytest -q tests/integration/test_assay_setup_transactions.py --no-cov
```
