# Software development

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Use these guides to change, test and maintain the application.

## Make your first change

1. Set up the [local development environment](../getting-started/developer-environment.md).
2. Read the [developer guide](developer-guide.md) and
   [application architecture](../architecture/application-architecture.md) for the
   boundaries affected by the change.
3. Use the relevant guide below for contracts, UI components or report templates.
   Local application operations and remote clients have separate [package guides](../core/README.md).
4. Run the applicable [quality gates](../testing/test-strategy-and-quality-gates.md)
   and update [documentation](writing-documentation.md).
5. Follow the [contribution requirements](../project/contributing.md) when preparing a change for review.

For a failed development command, start with [development troubleshooting](troubleshooting.md).
For an incident in an installed service, use [operations troubleshooting](../operations/troubleshooting.md).

## Guides

| Guide | Use it to |
| --- | --- |
| [Developer manual](developer-guide.md) | Understand code structure, services, contracts, and development interfaces. |
| [Coyote Core](../core/application-core.md) | Invoke authenticated local use cases and compose storage-independent validation tools. |
| [Remote development deployment](remote-development.md) | Use compiled development images when accessing a remote stack. |
| [Engineering command reference](engineering-commands.md) | Run local checks, inspect logs, and prepare a pull request. |
| [Engineering and Refactoring Standards](refactoring-standards.md) | Change implementation structure while preserving application contracts. |
| [Collection contracts and resource versioning](schema-contracts.md) | Update stored document contracts, generated forms, and revision behavior. |
| [Frontend API contracts](frontend-api-contracts.md) | Generate and check TypeScript types against FastAPI source or a running server. |
| [Report templates](report-templates.md) | Edit packaged HTML/CSS layouts and verify HTML/PDF output. |
| [Add a New Domain or Collection](adding-domains-and-collections.md) | Add a domain or collection across backend and frontend boundaries. |
| [UI Action Modal](action-dialogs.md) | Use the shared action-dialog patterns and accessible interactions. |
| [Plotting And Chart Export](charts-and-exports.md) | Build plots and export charts using established components. |
| [Writing and organizing documentation](writing-documentation.md) | Choose documentation locations, filenames, links, and validation checks. |
| [Dependency Advisory Policy](dependency-security.md) | Review dependency advisories and runtime security requirements. |
| [Repository Script Reference](script-reference.md) | Find repository scripts and their execution responsibilities. |
| [Development troubleshooting](troubleshooting.md) | Diagnose local development, configuration, and integration problems. |

[Documentation home](../README.md)
