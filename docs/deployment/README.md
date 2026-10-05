# Deployment and configuration

Deployment covers service provisioning, database connections, center configuration,
bootstrap data, and installation acceptance. New installations require initial
account setup and resource validation. Existing Coyote v3 databases require the
[migration procedures](../operations/migrations/README.md) before deployment.

## Guides

| Guide | Use it to |
| --- | --- |
| [First installation](first-installation.md) | Provision an empty installation and create its initial accounts. |
| [Production deployment](production-deployment.md) | Deploy production services in the required order. |
| [Initial deployment checklist](installation-checklist.md) | Verify bootstrap, service startup, access, and deployment handoff. |
| [Deployment acceptance checklist](acceptance-checklist.md) | Collect center-specific acceptance checks and evidence. |
| [Minimum Production Baseline](production-requirements.md) | Review infrastructure, access, backup, and monitoring prerequisites. |
| [Deployment configuration reference](configuration-reference.md) | Look up deployment environment variables and configuration ownership. |
| [Environments And Secrets](environments-and-secrets.md) | Separate environments, credentials, paths, and service endpoints. |
| [Center configuration files](center-configuration.md) | Look up supported center configuration files and keys. |
| [MongoDB deployment and recovery](mongodb-setup-and-recovery.md) | Initialize replica sets and verify database backup and recovery. |
| [Container deployment and reverse proxy](containers-and-reverse-proxy.md) | Configure service limits, images, routing, proxies, and release deployment. |
| [Installation bootstrap and data flow](bootstrap-data-flow.md) | Understand installed catalogs, seed ownership, and bootstrap order. |
| [Deployment Data Requirements](required-data.md) | Check which collections must exist before sample ingestion. |

[Documentation home](../README.md)
