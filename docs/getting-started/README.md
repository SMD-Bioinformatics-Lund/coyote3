# How to use this manual {#getting-started}

Start on the [documentation home page](../README.md#start-with-a-task) and choose
the task you need to complete. You do not need to read this manual from beginning
to end.

## Choose a reading path

A **guide** gives the numbered actions, prerequisites and checks for a task.
Follow those actions in order. A **reference** explains a field, term or setting;
open it only when you need that detail.

When a task spans multiple guides, **Continue this task** opens its next required
page. Optional examples, field catalogs and failure-recovery procedures are not
extra steps in that path. The last page says **End of this guide**.

If you open a reference from a guide, **Return to …** takes you back to the
paragraph you were reading. If you arrive from search, use **Start here** in the
sidebar to choose a task, or use the active sidebar section to find related material.

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

The sidebar has six areas: **Review samples**, **Configure assays**,
**Install and operate**, **Integrate pipelines**, **Develop and validate**, and
**Reference**. Each task area starts with direct action links. Expand its reference
group when you need supporting material. **On this page** opens the current guide's
sections, including its numbered steps.
Search using the visible application term, such as “assay group”, “query rules”,
“missing results” or “report preview”. For internal names such as ASP, ASPC and
ISGL, use [clinical concepts and resource identities](../reference/clinical-concepts.md).

## Installation and updates

Deployment procedures and their references appear under **Install and operate**
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
