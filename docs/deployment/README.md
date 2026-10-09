# Deployment and configuration

Deployment covers service provisioning, database connections, center configuration,
bootstrap data, and installation acceptance. New installations require initial
account setup and resource validation. Legacy databases use separate
[v3](../migration_from_v3/migration-guide.md) or
[v2](../migration_from_v2/migration-guide.md) migration procedures.

## Guides

| Guide | Use it to |
| --- | --- |
| [Choose a deployment procedure](production-deployment.md) | Select first installation, an upgrade, or redeployment according to the installation's state. |
| [Minimum Production Baseline](production-requirements.md) | Review infrastructure, access, backup, and monitoring prerequisites. |
| [First installation](first-installation.md) | Follow one ordered procedure from environment files through network creation, storage, bootstrap, startup and first sign-in. |
| [Installation operations](installation-operations.md) | Select installer stages, opt in to knowledgebase operations, and run each operation independently. |
| [Initial deployment checklist](installation-checklist.md) | Record completion evidence for the first-installation procedure. |
| [Deployment acceptance checklist](acceptance-checklist.md) | Collect center-specific acceptance checks and evidence. |
| [Upgrade an existing installation](application-upgrades.md) | Preserve recovery artifacts, validate the release, pause writes, back up, apply required maintenance and verify or roll back. |
| [Restart or redeploy](application-redeployment.md) | Start or replace containers using the same release, configuration and persistent state. |
| [MongoDB deployment and recovery](mongodb-setup-and-recovery.md) | Initialize replica sets and verify database backup and recovery. |
| [Container deployment and reverse proxy](containers-and-reverse-proxy.md) | Configure service limits, images, routing, proxies, and release deployment. |
| [Installation bootstrap and data flow](bootstrap-data-flow.md) | Understand installed catalogs, seed ownership, and bootstrap order. |
| [Deployment Data Requirements](required-data.md) | Check which collections must exist before sample ingestion. |
| [New-center configuration review](center-configuration.md#new-center-configuration-review) | Review TOML, YAML, environment settings, and clinical resources before building images. |
| [Deployment configuration reference](configuration-reference.md) | Look up deployment environment variables and configuration ownership. |
| [Environments And Secrets](environments-and-secrets.md) | Separate environments, credentials, paths, and service endpoints. |
| [Center configuration files](center-configuration.md) | Look up supported center configuration files and keys. |

[Documentation home](../README.md)
