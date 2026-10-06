# Operational scripts

Run commands from the repository root with the application virtual environment.
The [script reference](../docs/development/script-reference.md) describes individual
commands, their callers, and operational prerequisites.

| Directory | Purpose |
| --- | --- |
| [upgrade_from_v3](upgrade_from_v3/README.md) | Clinical application data upgrades from Coyote v3; excludes identity and external knowledgebases |
| [migrate_from_v2](migrate_from_v2/README.md) | Offline v2 clinical migration using `variants_idref` and `cnvs_wgs` |
| `migration_common/` | Shared offline indexing, conversion, metadata reconciliation, and isolated target bundle application |
| `bootstrap/` | Initial database installation, seed preparation, and assay validation |
| `deployment/` | Version-aware Compose commands and installation checks |
| `database/` | Backups, restores, indexes, capacity, and report-artifact inspection |
| `ingest/` | Manifest validation, submission, and API authentication |
| `identity/` | Identity database migration and permission/role maintenance |
| `knowledgebase/` | External reference imports, storage migrations, and repairs |
| `maintenance/` | Operational data maintenance |
| `docs/` | Reproducible schema/permission reference generators and link validation |
| `quality/` | Repository checks, secret scanning, and test orchestration |
| `release/` | Package-version synchronization |

Migration commands are operator tools, not application startup hooks. Read their
runbooks and inspect the plan before enabling writes. Keep credentials, database
exports, migration plans containing identifiers, and backups outside the repository.

## Retention criteria

Keep scripts that support a documented, reproducible workflow for an operator,
another center, or repository automation. Each retained command needs defined inputs,
outputs, prerequisites, and failure behavior. Shared helpers belong here only when
retained commands use them. Version-specific migrations remain with their runbooks
while that upgrade path is supported.

One-off data fixes for unreleased development state, inspection snippets, artwork
renderers, and coding-session experiments belong in the ignored `.design/` directory.
Do not commit them or reference them from CI, tests, or operational documentation.
The staged-file guard rejects `.design/` content even when it is force-added to Git.
For documentation artwork, maintain the reviewed SVG assets themselves. Schema and
permission generators remain tracked because they reproduce references from the
application's authoritative contracts.
