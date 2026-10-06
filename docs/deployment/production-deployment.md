# Deployment procedures

Choose the procedure that matches the state of the installation. Each procedure
contains its own ordered commands; configuration and architecture pages describe
settings rather than provide alternative installation sequences.

| Situation | Procedure | Database behavior |
| --- | --- | --- |
| New application and identity databases | [First installation](first-installation.md) | Explicitly installs the baseline and initial accounts once. |
| An existing installation needs a new application release or reviewed configuration change | [Upgrade an existing installation](application-upgrades.md) | Preserves data; only release-required maintenance is applied after backup. |
| The same release and configuration must be started again or its containers replaced | [Restart or redeploy](application-redeployment.md) | Reuses the existing databases, storage, secrets and Redis volume. No bootstrap or migration. |
| Legacy Coyote v3 data must be converted | [Migration from v3](../migration_from_v3/migration-guide.md) | Uses the separate reviewed end-to-end conversion procedure. |
| Legacy Coyote v2 data must be converted | [Migration from v2](../migration_from_v2/migration-guide.md) | Uses the separate reviewed end-to-end conversion procedure. |

A host replacement or disaster recovery is not an ordinary redeployment. It
requires restored persistent storage, verified database endpoints, preserved
configuration and the original deployment identity. Follow the
[backup and recovery procedure](../operations/backup-and-recovery.md) before
resuming application services.

## Ownership and persistence

| Resource | Owner | Deployment behavior |
| --- | --- | --- |
| Application containers | Application release | API, frontend, worker, beat, monitor, proxy and documentation can be replaced. |
| Redis data volume | Existing Compose project | Retained across application replacement; contains queue and operational state. |
| MongoDB | Independently operated database service | Application deployment does not provision, replace or remove it. |
| Center files and secrets | Deploying center | Retained across releases; changed only through reviewed configuration updates. |
| Reports, ingest files and logs | Persistent host storage | Mounted into replacement containers; never reset by deployment. |
| ASP, ASPC, ISGL and reporting rules | Center-managed database resources | Preserved across application releases. Application bootstrap is not a configuration reset. |

Use the same Compose project name and private environment file for every operation
on one installation. Changing the project name can create a second application
stack and a different Redis volume, even if MongoDB settings are unchanged.

The application definition is `deploy/compose/docker-compose.yml`. Use
`scripts/deployment/compose-with-version.sh` for deployment commands. No MongoDB
profile or development overlay is part of the production application procedure.
The wrapper prepares application storage before startup and refuses `down -v`.

## Reference and acceptance documents

| Document | Purpose |
| --- | --- |
| [Configuration reference](configuration-reference.md) | Environment settings and their meaning. |
| [Center configuration](center-configuration.md) | Editable TOML/YAML contracts and persistent configuration releases. |
| [Container and reverse-proxy reference](containers-and-reverse-proxy.md) | Service wiring, URL prefixes and ingress behavior. |
| [Initial deployment checklist](installation-checklist.md) | Evidence to record after following first installation. |
| [Deployment acceptance](acceptance-checklist.md) | Clinical and operational release acceptance. |
| [Production requirements](production-requirements.md) | Capacity, security and operational prerequisites. |
