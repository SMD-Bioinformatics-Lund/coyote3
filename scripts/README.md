# Operational scripts

Run commands from the repository root with the application virtual environment.
The [script reference](../docs/development/script-reference.md) describes individual
commands, their callers, and operational prerequisites.

| Directory | Purpose |
| --- | --- |
| `bootstrap/` | Initial database installation, seed preparation, and assay validation |
| `deployment/` | Center installation orchestrator, version-aware Compose commands and deployment checks |
| `database/` | Backups, restores, indexes, capacity, report-artifact inspection, and audit-chain verification |
| `ingest/` | Manifest validation, submission, and API authentication |
| `identity/` | Identity database migration and permission/role maintenance |
| `knowledgebase/` | External reference imports, storage migrations, and repairs |
| `maintenance/` | Operational data maintenance |
| `docs/` | Reproducible schema/permission reference generators, Markdown lint and link validation |
| `quality/` | Repository checks, secret scanning, and test orchestration |
| `release/` | Version synchronization, SDK wheel builds, and release artifact verification |

Migration commands are operator tools, not application startup hooks. Read their
runbooks and inspect the plan before enabling writes. Keep credentials, database
exports, migration plans containing identifiers, and backups outside the repository.
Clinical-data conversion lives in `migrations_scripts/`. Follow the
[execution order and commands](../docs/operations/migrations/clinical-data.md).
Export and preparation do not write to the source databases.

Fresh deployment includes the connected DNA/RNA starter configuration and both samples
unless `--skip-demo` is selected. Later additions and repairs use
`python3 scripts/deployment/manage_data.py --api-url API_URL --modules demo`, with
`--force` for explicit repair. This command authenticates through the API and does not
deploy services. The [synthetic clinical workflow guide](../docs/testing/clinical-workflow-demo.md)
documents `bootstrap/install_demo_workflows.py` (plan/apply configuration in an explicit
local demo database) and `quality/export_demo_workflows.py` (offline ingest replay and
collection/report snapshot verification). Neither belongs in production startup.

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
