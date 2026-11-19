# Sign in and use the application {#application-user-guide}

Use this guide for sign-in, navigation and account settings. For the review process,
follow [Review a sample and save its report](clinical-review-workflow.md).

## Sign in and public pages

Sign in with your username and an authentication method enabled by your center:
local account or LDAP. Sample and administration pages require authentication and
permission for the requested data or action. Public catalog, gene-list, About and
Contact pages may be available without signing in.

Select **Forgot password** to request recovery using your username:

- **Local account:** a reset link goes to the saved email address. Without a saved
  email, recovery requires administrator assistance.
- **LDAP account:** administrators handle the reset through the external directory
  service. Coyote records the request and its completion; it does not change the LDAP password.

Choose the account type if you have both local and LDAP accounts. Recovery uses a
neutral response so it does not reveal whether a username exists. Use **Logout**
in the account menu to end the current session.

## Main navigation

The top bar contains the application logo, available DNA/RNA assay menus, theme
control, notifications and account menu. The sidebar opens the workspaces available
to your account; it can be collapsed to leave more space for content.

| Workspace | Use it to |
| --- | --- |
| Dashboard | See workload, recent samples and configuration summaries. |
| Samples | Find a sample and open its analysis. |
| Tiered variant search | Find classifications and their recorded sample/report links. |
| Gene cohort | Review reported findings for one gene. |
| Reports | Open reports that have already been saved. |
| Catalog | Browse published assay and gene-coverage information. |
| Knowledgebases | Inspect installed reference sources and releases. |
| Admin | Manage the resources your account is allowed to edit. |

A hidden or unavailable action can reflect your permissions or a disabled application
module. It does not establish that the underlying data is absent.

### Theme

Use the top-bar icon or **Profile → User settings → Theme** to choose **Auto**,
**Light** or **Dark**. Auto uses light from 07:00 to 19:00 and dark overnight,
according to the browser's local clock. The icon cycles Auto → Light → Dark.
Signed-in changes are saved to your account; before sign-in they apply to that browser.
Report documents and supplied reference images retain their own presentation.

## Dashboard

Counts reflect your permitted sample scope and may come from cached metrics.
Use the page's refresh action when available. A zero count can mean no matching
records or no records visible to your account. See the [dashboard guide](dashboard.md)
for individual metrics.

## Find samples

Use the assay menus, profile scope, date range and search on **Samples**. Select a
sample name to open it. **Live samples** and **Reported samples** separate the two
worklists. [Sample management](sample-management.md) explains the controls and exports.

## Sample workspace

Check **Overview** for sample/control identifiers, the assay, applied configuration,
input files and readiness. Review any Base-configuration warning.
**Classic** groups enabled finding sections; **Modern** shows analyses in separate tabs.
The layout preference does not alter classifications, filters or report contents.

A missing analysis tab is different from an available analysis returning no rows.
Use [missing samples or results](sample-readiness-and-missing-results.md) to check
configuration, loaded evidence and filters in order.

## Work with clinical tables

Search, sorting, pagination and CSV export are available where supported by the table.
Server-backed finding tables apply these operations across the filtered result set.
Select rows before using bulk actions and review the confirmation before submitting.
Supported table state is retained in the URL when opening details and returning.

CSV exports preserve numeric zero. Text resembling a spreadsheet formula is escaped;
the protective apostrophe may be visible in a plain-text reader. A missing value is
not a measured zero. See [table columns and badges](pages-and-table-columns.md) for
field definitions and the meaning of individual status markers.

## DNA review

Open the enabled small-variant, CNV or translocation section and inspect a finding's
evidence before changing its classification or review state. Use [DNA review](dna-review.md)
for filters, transcripts and actions, and [coverage review](coverage-review.md) for
low-coverage measurements. Coverage is separate from the CNV profile.

## RNA review

Review fusion callers, breakpoints and support counts. Enabled WTS analyses can also
show expression, classification and QC. Use [RNA review](rna-review.md) for the
selected-call rules, fields and reporting behavior.

## Filters and gene lists

Filters are saved for each sample and analysis. Opening a filter panel does not apply
changes. Check thresholds and gene selections before saving. SNV, CNV, fusion and
translocation selections are independent; coverage has its own scope.
See [gene lists and assay context](gene-lists-and-assay-context.md#when-no-gene-list-is-selected)
for fallback and empty-selection behavior.

## Comments and annotations

Use a sample comment for report interpretation, a finding comment for one event,
and a global annotation for reusable text or classification. Check its scope before
saving. The latest visible sample comment supplies the report conclusion.

Comments support Markdown with Write and Preview modes. Hidden comments are inactive;
authorized users can reveal or restore them. See [actions and saved records](actions-and-record-changes.md)
for the effect of each mutation.

## Reports

Create a report from **Reports** inside the sample. The global **Reports** page lists
saved reports. Review HTML/PDF previews before saving; a preview or download alone
does not create a report. Follow [Preview and save reports](report-preview-and-save.md)
for the save confirmation and handling a changed preview.

## Search and cohort review

Tiered search shows classifications and recorded sample/report links. A latest-match
fallback for an unlinked legacy record does not prove which tier that sample used.
[Gene cohort](pages-and-table-columns.md#gene-cohort-explorer) summarizes reported
findings and the applicable profiled-sample population; its counts are not all ingested findings.

## Notifications and profile

The bell opens notifications addressed to you. Open **Profile** from the account
menu to change permitted account fields and your theme, analysis layout, sample-list
layout or default table page size. Administrative role and access changes use the
[account administration workflow](../administration/permissions-and-access.md).

## Administration

Use [assay setup](../administration/assay-setup.md) to prepare a new assay. Existing
assays, configurations and gene lists have separate administration pages. Their edits
create revisions; they do not silently update configurations already assigned to
samples or rewrite saved reports.

## Errors and missing data

| What you see | What to check |
| --- | --- |
| No results | Active filters and gene scope, then loaded evidence. |
| Missing analysis tab | Enabled analyses, sample modality and required resources. |
| Base configuration in use | Whether the fallback is appropriate for this sample. |
| Permission denied or module unavailable | Your account's access and the application's module settings. |
| Request failure or connection interruption | Whether a write completed before retrying. Retain the error's reference ID, time and request path for support. |

For sample problems, use [missing samples or results](sample-readiness-and-missing-results.md).
For a service failure, use [operations troubleshooting](../operations/troubleshooting.md).
