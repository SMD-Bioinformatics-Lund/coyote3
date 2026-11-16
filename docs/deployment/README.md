# Install or update Coyote4

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Choose one procedure. These are alternatives, not a sequence of manuals to read.

| Installation state | Procedure |
| --- | --- |
| New application database and initial account | [First installation](first-installation.md) |
| Existing installation, new application release | [Upgrade](application-upgrades.md) |
| Existing installation, same release | [Restart or redeploy](application-redeployment.md) |
| Local evaluation with synthetic samples | [Isolated demo installation](demo-installation.md) |
| Ordinary development containers | [Local development stack](../getting-started/local-quickstart.md) |
| Data from Coyote version 2 or 3 | [Clinical data conversion](../operations/migrations/clinical-data.md#select-the-source-version) |

Before a center deployment, review the [production requirements](production-requirements.md).
The installation procedure includes the commands and checks in order.

## References for installation choices

- **MongoDB:** [first-time provisioning](mongodb-first-setup.md) and [topology](../architecture/mongodb-topology.md).
- **Settings:** [environment variables](configuration-reference.md) and [center files](center-configuration.md).
- **Containers:** [Compose and reverse proxy](containers-and-reverse-proxy.md), including support for the older deployment host.
- **Installed data:** [baseline data flow](bootstrap-data-flow.md), [required data](required-data.md) and [individual installer operations](installation-operations.md).

## After installation

Complete the [acceptance checklist](acceptance-checklist.md), then
[configure and validate the assays](../administration/assay-setup.md).
Use [operations](../operations/README.md) for routine checks and incident recovery.
