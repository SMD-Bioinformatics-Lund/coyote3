# Assay Setup

An assay is a center-defined sequencing offering. Its name does not require a
dedicated code path: it selects compatible [application-supported analyses](supported-capabilities.md).
The setup workflow configures those analyses for the assay's diagnoses and environments.

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

Analysis intents use checkboxes alongside enabled analyses. DNA supports somatic
and germline SNV review; RNA supports somatic analysis. Gene lists contain one
curated gene set. Their germline subset is resolved from its intersection with the
sample's pinned assay germline genes.

![Assay setup and resource dependencies](../assets/diagrams/assay-configuration-relationships.svg)

The diagram separates shared definitions, operational configuration, setup approval,
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
uppercase letters and leading, trailing or repeated separators with HTTP 422.
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

Have an authorized setup author and a different qualified reviewer available.
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
in `existing_gene_list_ids`; they do not alter operational lists until independent
approval and activation. Activation updates each selected list's `asp_ids` and
`asp_groups` in the same transaction as the new assay and configurations. The old
list revision remains in history; genes and original creation attribution are retained.
If a selected list changes after submission, the setup requires a new review.

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
base-only assay, leave named diagnoses unselected. Choose at least one target
environment; this is the clinical configuration environment, not a separate
application deployment.

For each required named scope, reuse an active shared diagnosis or select
**Manage diagnosis definitions** to register it. An unassigned definition can exist
before the assay. Return to setup and select **Refresh diagnosis definitions**,
then select the scope. Activation creates the draft assay's association; a shared
definition by itself does not configure every assay.

The selected scopes and environments determine the required ASPC combinations.
Base plus Myeloid in development and production requires four ASPCs. Base alone
in production requires one. Do not select speculative combinations: every selected
combination must be complete before the setup can be approved.

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

### 6. Complete one ASPC for each selected combination

In **Configurations**, save one configuration for each scope/environment pair.
The coverage table includes each saved configuration's name and Edit/View action;
missing combinations have an Add action that preselects that scope and environment.
The table shows 10 combinations per page. Saving an ASPC is available at both the
top and bottom of its editor. Displayed reporting defaults are included when saving,
including when only the report method is changed.
Review enabled analyses and intents, thresholds, consequence selections,
analysis-specific ISGL defaults, report sections, language and report settings.
Only analyses supported by the ASP's declared files and family are available.
Report sections must be a subset of enabled analyses and declared by the resolved
published reporting rule.

Selected ISGLs must be active, compatible with the analysis, and available through
the assay or its group. A typed identifier does not make an unavailable list valid.
The configuration cannot substitute for an absent file declaration or publish a rule.

### 7. Review, submit and activate

Open **Review**, resolve every readiness error, and select **Submit for review**.
A qualified reviewer who did not edit the setup reviews its content and chooses
**Approve and activate**, or **Return for changes** with a reason. Saving or
submitting the draft alone does not activate it.

Activation rechecks dependency versions and atomically creates the ASP, named
diagnosis associations, staged ISGLs and ASPCs. If a dependency changed after
submission, return the setup, review the new values and submit again. Rule
publication remains a separate operation; setup approval does not publish rules.

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
| Assay identity and rules | Save the setup's ASP draft before authoring its rule scope. | An operational ASP is not required for rules authored against a saved setup draft. |
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

Clinical rules are published through their own approval process before setup
activation. Setup approval does not publish or modify clinical-rule content.
An ASPC supplies the reporting language. Its exact diagnosis release is selected
automatically, with assay Base used only when no exact published release exists.
The analyte and declared analyses must match the configuration. Publishing a new
exact release does not require rebinding the ASPC.

Public catalog publication remains separate. Add the assay to the catalog after
activation; only the catalog workflow controls public presentation and publication.

## Review And Activation

1. Complete and save the selected configurations.
2. Open **Review** and resolve readiness errors.
3. Choose **Submit for review**. Submitted content becomes read-only.
4. A qualified user who has not edited the content opens the saved setup.
5. The reviewer selects **Approve and activate**, or enters review notes and
   selects **Return for changes**.

Returning a setup restores draft editing and preserves the submitted revision.
Content editors, including the creator, cannot approve that setup. Published
setup snapshots cannot be edited. Subsequent changes use the individual resource
administration pages.

Activation revalidates configurations and checks the versions of published rules,
shared diagnoses and available shared gene lists against the submitted review.
A dependency change requires returning the setup and submitting it again.
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
| Save, submit, approve and activate | All three creation permissions plus `assay.panel:edit` |
| Return for changes | `assay.panel:edit` and independence from content editors |

The UI requires assay list and view access. Editing requires the creation
permissions and assay edit permission. Clinical-rule actions retain their own
permissions.

An independent reviewer with `assay.panel:edit` can return a submitted setup
with a reason even without the creation permissions. Approval and activation
require all the creation permissions as well. Review notes are specific to the
selected setup and are cleared when switching workspaces.

## Storage And Operations

| Collection | Identity | Purpose |
| --- | --- | --- |
| `assay_setups` | Reserved `asp_id`; `_id` identifies the workspace | Current content and governance state |
| `assay_setup_revisions` | `setup_id`, `revision` | Immutable full snapshots of saved states and lifecycle actions |

Collection names are configured in `api/config/collections.toml`. Install
their indexes using the standard command, with the intended deployment
configuration and index-management account:

```bash
PYTHONPATH=. .venv/bin/python scripts/database/manage_mongo_indexes.py apply
```

Apply indexes before starting an API configured to verify index contracts. No
existing ASP backfill or clinical data migration is required.

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
