# Getting started

Choose the task that matches your role and the state of your installation.
Installing the application, changing its configuration and adding a clinical assay
are separate operations; the links below identify the appropriate procedure.

| Task | Start here |
| --- | --- |
| Evaluate the application with demonstration data | [Try Coyote3 locally](local-quickstart.md) |
| Install at a new center | [First installation](../deployment/first-installation.md) |
| Update a running installation | [Upgrade the application or configuration](../deployment/application-upgrades.md) |
| Restart or replace containers without changing the release | [Restart or redeploy](../deployment/application-redeployment.md) |
| Understand a file or setting mentioned in a procedure | [Configuration and file formats](../configuration/README.md) |
| Add the first or another clinical assay | [Assay setup procedure](../administration/assay-setup.md#step-by-step-add-a-new-assay) |
| Understand built-in finding selection and UI query rules | [Application base queries](../administration/query-rules.md#application-base-queries-by-analysis) and [policy inheritance](../administration/query-rules.md#scope-and-inheritance) |
| Begin clinical review | [Review one sample from start to report](../user-guide/clinical-review-workflow.md) |
| Prepare to develop application code | [Developer environment](developer-environment.md) |

## Choose a reading path

You can use an existing installation without learning deployment or development.
Start with the path for the work you need to do, then follow the linked references
only when you need field definitions or implementation details.

| Your work | Suggested reading order |
| --- | --- |
| Review and report clinical findings | [Sign in and navigate](../user-guide/application-guide.md#sign-in-and-public-pages) → [review a sample](../user-guide/clinical-review-workflow.md) → [preview and save a report](../user-guide/application-guide.md#reports). |
| Configure an assay | [Understand the resources](../administration/clinical-configuration-resources.md) → [follow assay setup](../administration/assay-setup.md) → [validate the workflow](../testing/clinical-workflow-demo.md). Synthetic exercises supplement the center's validation. |
| Install and operate the service | [Choose a deployment procedure](../deployment/production-deployment.md) → [acceptance checks](../deployment/acceptance-checklist.md) → [operations tasks](../operations/README.md). |
| Connect a pipeline or external application | [Authenticate](../api/authentication.md) → [choose API workflows](../api/routes-and-workflows.md) or the [Python HTTP client](../sdk/python-client.md) → [prepare and submit samples](../api/sample-ingestion.md). |
| Develop the application | [Prepare the environment](developer-environment.md) → [understand code boundaries](../development/developer-guide.md) → [run the required checks](../testing/test-strategy-and-quality-gates.md). |
| Migrate legacy clinical data | [Choose the source version](../operations/migrations/README.md) → read its prerequisites and source inventory → follow its migration procedure. |

## Find the right kind of rule or setting

| What you want to change or understand | Authoritative guide |
| --- | --- |
| Which findings the application retrieves by default | [Application base queries](../administration/query-rules.md#application-base-queries-by-analysis). These exist without a UI-created profile. |
| Additional finding-selection conditions created in the UI | [Query rules and inheritance](../administration/query-rules.md#scope-and-inheritance). Published policies compose with the application base. |
| Filter values such as depth, frequency and selected genes | [Review filter fields and defaults](../reference/filter-profile-fields.md), with [assay configuration and query filtering](../reference/assay-filtering.md) for how values resolve. |
| Clinical statements and sections generated in a report | [Reporting rules](../reference/clinical-reporting-rules.md). These are separate from finding-selection rules. |
| Report layout, logos, CSS or empty-section wording | [Report templates](../development/report-templates.md) and [report presentation settings](../configuration/report-presentation-file.md). |
| Hostnames, database connections, storage or center identity | [Configuration files](../configuration/README.md). These are separate from clinical resources managed in the UI. |

## Using the documentation navigation

Sidebar group headings expand their links; they do not open another contents page.
Choose a procedure link to begin. **On this page** opens that page's section list.
Task pages show their ordered path and a **Continue this task** link at the end.
The **Clinical
reference** shortcuts link directly to common review and assay topics.
Search using the visible application term, such as “assay group”, “query rules”,
“missing results” or “report preview”. For internal names such as ASP, ASPC and
ISGL, use [clinical concepts and resource identities](../reference/clinical-concepts.md).

## Installation and updates

All deployment guides appear under **Getting started → Installation and updates**
in the documentation site. Their source files remain together in `docs/deployment/`.
The [deployment overview](../deployment/README.md) lists infrastructure, acceptance
and recovery references alongside the three ordered procedures.

## Read a procedure and its references

A procedure gives the order, commands or screen actions, expected results and
conditions that stop progress. A reference explains a named resource or file,
its fields, valid values, defaults, validation and effect on application behavior.
Follow a linked reference when you need that detail. The site displays
**Return to …** above the reference, taking you back to the exact paragraph that
opened it. Browser Back also remains available. With browser storage disabled,
use Back; Markdown files viewed outside the site use their ordinary links.

For example, an installation step selects `production.env`. The
[environment-file reference](../configuration/environment-file.md) explains what
that file is and how to write it. The
[variable table](../deployment/configuration-reference.md#environment-variable-reference)
explains every supported setting and its omission behavior. A copied example is
not automatically the application's default or an approved center configuration.

Text such as `<RELEASE_TAG>` is a placeholder to replace with a real value, not
text to type literally. Names such as `COYOTE_ENV_FILE` used by shell examples
hold the operator's chosen filename; they are not additional application settings.
Run commands only after reviewing their prerequisites and target environment.

[Documentation home](../README.md)
