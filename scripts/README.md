# Operational scripts

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Run commands from the repository root with the application virtual environment.
The [script reference](../docs/development/script-reference.md) describes individual
commands, their callers, and operational prerequisites.

| Directory | Purpose |
| --- | --- |
| `bootstrap/` | Initial database installation, seed preparation, and assay validation |
| `deployment/` | Center installation orchestrator, version-aware Compose commands and deployment checks |
| `database/` | Backups, restores, indexes, capacity, report-artifact inspection, and audit-chain verification |
| `identity/` | Identity database migration and permission/role maintenance |
| `knowledgebase/` | HGNC and external reference imports, storage migrations, and repairs |
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

The identity and knowledgebase database migrations share JSON output and exit-code
handling in `database/migration_report.py`. Each command retains its own validation,
dry-run and write controls. Submission, manifest validation and pipeline login are
provided by [Coyote Relay](../services/relay/docs/usage.md), not a scripts directory.

Normal deployment does not install demonstration code or samples. The optional
`coyote-demo` package supplies `coyote-demo-install` and its authenticated API
routes for an [explicitly isolated demo environment](../docs/deployment/demo-installation.md).
`manage_data.py` manages identity, application and knowledgebase catalogs only.
The [synthetic clinical workflow guide](../docs/testing/clinical-workflow-demo.md)
documents the packaged installer and `quality/export_demo_workflows.py` for offline
ingest replay and collection/report verification. Neither belongs in production startup.

`quality/run_package_tests.sh` runs `core`, `api`, `mongo`, `client`, `relay`,
`atlas`, `demo`, or `all`
from each package directory. The default is its full suite; `--smoke` selects fast
checks and `--coverage` enforces that package's branch-coverage floor and writes
its local reports. It uses `PYTHON_BIN`, the active virtual environment, or root
`.venv/bin/python`. It starts no application services and configures no CI jobs.

`docs/export_collection_dependencies.py` regenerates the collection reference
diagrams and tables from the reviewed catalog. Its SVG styling helper is
`docs/collection_diagram_style.py`; neither belongs to an application package.
See [diagram maintenance](../docs/project/maintainer-guide.md#documentation-diagrams).

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
