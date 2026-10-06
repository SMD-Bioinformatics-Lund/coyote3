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
| Add the first or another clinical assay | [Assay setup](../administration/assay-setup.md) |
| Begin clinical review | [Application user guide](../user-guide/application-guide.md) |
| Prepare to develop application code | [Developer environment](developer-environment.md) |

## Installation and updates

All deployment guides appear under **Getting started → Installation and updates**
in the documentation site. Their source files remain together in `docs/deployment/`.
The [deployment overview](../deployment/README.md) lists infrastructure, acceptance
and recovery references alongside the three ordered procedures.

## Read a procedure and its references

A procedure gives the order, commands or screen actions, expected results and
conditions that stop progress. A reference explains a named resource or file,
its fields, valid values, defaults, validation and effect on application behavior.
Follow the linked reference when a term is unfamiliar; return to the same step afterward.

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
