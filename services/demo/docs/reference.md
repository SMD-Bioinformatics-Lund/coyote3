# Interfaces

The base package exposes synthetic resources without importing the API or opening
database connections. Install the `api` extra for host installation and routes,
and the `worker` extra for the guarded Relay worker entry point.

| Interface | Purpose |
| --- | --- |
| `coyote_demo.resources.WORKFLOW_BUNDLE` | Installed directory containing manifests, setup documents and synthetic analysis inputs. |
| `coyote_demo.resources.DEMO_CENTER` | Compact synthetic assay configuration bundle. |
| `coyote_demo.installation.DemoInstallationService` | Plans and installs allowlisted configuration and starter samples through supplied repositories and ingestion services. |
| `coyote_demo.operations.DemoInstallation` | Enforces current session permissions before invoking the host installer. |
| `coyote-demo-install` | Plans by default; `--apply` installs resources and `--starter` includes sample ingestion. |
| `python -m coyote_demo.runtime ingest` | Validates isolated targets and credential scope before starting Relay's queue consumer. |
| `python -m coyote_demo.runtime maintenance` | Runs the normal maintenance queue for audit delivery, report completion and scheduled operations after the same preflight. |
| `python -m coyote_demo.runtime beat` | Runs the normal task schedule after preflight; scheduler state stays in demo storage. |

The `coyote.api.routers` entry point returns no routers while Demo is disabled.
When enabled, its routes retain the existing `demo:install` permission and the
host's session and CSRF checks. The `coyote.runtime.validators` entry point
declares the configuration keys needed to validate isolation before host
connections initialize.

See [usage](usage.md) for route paths and commands, [configuration](configuration.md)
for target restrictions, and [datasets](datasets.md) for the packaged inputs.
