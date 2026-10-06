# Assay Setup

![Assay setup and resource dependencies](../assets/diagrams/assay-configuration-relationships.svg)

The diagram separates shared definitions, operational configuration, setup approval,
and catalog publication. Follow the steps below to create a new assay.

For the meaning, requirements and defaults of individual ASP, ASPC and ISGL fields,
use the [clinical resource field reference](clinical-resource-fields.md).

## Names And Identifiers

Administration uses **Assay group**, **Assay**, **Subpanel**, **Assay configuration**,
**Gene list**, **Reporting rule set**, and **Assay catalog**. ASP, ASPC and ISGL
remain technical names in API fields and storage; changing a display label does
not change an endpoint, permission or database reference.

Assay groups are center-defined. WGS, WTS and Fusion may be both group names and
registered assays at a center; they are not forced into a clinical-specialty
classification. Group membership and assay family are separate configuration fields.

Use lowercase ASCII letters and digits with **underscores between words for new
database identifiers**: `solid_gmsv3`, `breast_cancer`, `mpn_diagnostic_genes`.
Use **hyphens for URL path segments**, such as `/assay-groups`. JSON/Python field
names use underscores (`asp_id`, `subpanel_id`). These are conventions for different
kinds of names, not instructions to translate a stored identifier in a URL.

New assay groups, assays, shared subpanels and gene lists must use lowercase
letters and digits separated by single underscores. Creation rejects hyphens,
spaces, and leading, trailing or repeated underscores with HTTP 422. The rule
also applies to assay setup registration and gene lists created through setup,
and to imported new definitions submitted through the same creation services.

Existing identifiers and references retain their original separators. Editing
metadata does not register a new identity. `breast-cancer` and `breast_cancer`
remain different keys, not aliases; lookups do not try alternative spellings.
Generated configuration and reporting keys continue to derive from their scope
identifiers, using their established underscore separators without renaming an
existing assay or subpanel reference. Do not create duplicate definitions solely
to change punctuation. Renaming stored identities requires a reference migration.

Display names may contain spaces, punctuation and clinical capitalization, such
as **Breast Cancer** or **Hematology GMSv1**. Gene-list aliases provide alternative
readable names; references still use the stable gene-list identifier. Keep release
versions in version fields rather than changing the identifier on each publication.
An established assay name may contain a generation marker, such as `gmsv1`; that
is distinct from its configuration revision. `base` remains the implicit default
scope and must not be registered as a separate subpanel.

## Starting A Setup

![Required setup order from accounts to sample review](../assets/diagrams/resource-setup-order.svg)

The numbered path shows the dependencies for a new installation or assay. Existing
accounts, groups, shared subpanels, and eligible gene lists can be reused. Gene lists
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
draft from **Saved setups** to continue its configuration.

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

Open **Admin > Assay setup**, create a draft and save the **Assay** step. Supply a
stable identifier, display name, group, family, DNA/RNA category, sequencing
settings, physical gene coverage and input-file policy. Define `expected_files`
for evidence the pipeline produces and `required_files` for inputs whose absence
must reject ingest. Select only implemented file/analysis combinations.

This saved draft reserves the assay identity and makes it available to the rule
builder. It is not yet an operational ASP; creating it does not enable ingest.
Do not create a second ASP with the same identifier through another workflow.

### 3. Select scopes and environments

**Base is always selected** and needs no subpanel registry document. For a
base-only assay, leave named subpanels unselected. Choose at least one target
environment; this is the clinical configuration environment, not a separate
application deployment.

For each required named scope, reuse an active shared subpanel or select
**Manage subpanel definitions** to register it. An unassigned definition can exist
before the assay. Return to setup and select **Refresh subpanel definitions**,
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
ad-hoc genes, applicable gene filtering falls back to the ASP's physical coverage;
empty physical coverage can leave a query without a gene restriction. Review the
intended scope explicitly before approving the assay.

### 5. Publish compatible reporting rules

After saving the assay draft, use **Open rule builder**. Select the draft assay,
DNA/RNA analyte, Base or registered named scope, and intended reporting language.
Author the clinical content, declare the analyses used by the report sections,
run its tests, and complete independent clinical review and publication.

Return to setup and choose **Refresh reporting rules**. Draft or merely reviewed
rules do not satisfy publication requirements. An exact named-scope release is
used when published; otherwise resolution can use a compatible assay Base release
for the same analyte and language. Do not assume a different language or another
assay's rule will be selected.

Rules and ISGLs can be prepared in either order after their assay/scope dependencies
exist. Neither publishes the other. Setup activation resolves a published rule
for every selected ASPC; even an ASPC with no report sections does not bypass this
setup-level check. The individual ASPC editor has a narrower rule check: it requires
a compatible published release when that ASPC is active and has report sections.

### 6. Complete one ASPC for each selected combination

In **Configurations**, save one configuration for each scope/environment pair.
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
subpanel associations, staged ISGLs and ASPCs. If a dependency changed after
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
| Assay group and ASP | Register/activate the group before saving the assay setup. | Shared subpanel definitions can be created without an assay association. |
| Assay identity and rules | Save the setup's ASP draft before authoring its rule scope. | An operational ASP is not required for rules authored against a saved setup draft. |
| Gene lists and rules | Both must be suitable before configurations that use them are approved. | ISGL authoring and rule authoring/publication have no required order relative to each other. |
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
An ASPC supplies the reporting language. Its exact subpanel release is selected
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
shared subpanels and available shared gene lists against the submitted review.
A dependency change requires returning the setup and submitting it again.
Stale saves and concurrent publication attempts return a conflict.

The ASP, named subpanel associations, newly staged gene lists, ASPCs, published
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
