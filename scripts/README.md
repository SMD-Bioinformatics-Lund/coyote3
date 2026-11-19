# Operational scripts

<!-- badges:start -->
![Coyote4: 4.0.0](https://img.shields.io/badge/Coyote4-4.0.0-4F46A5?style=flat) ![License: GPL-3.0-only](https://img.shields.io/badge/License-GPL--3.0--only-2E7D32?style=flat)
<!-- badges:end -->

Use `bash install.sh --help` for installation and deployment operations. Internal
installer modules live in `deploy/installer/`. Run the operational scripts below
from the repository root with the application virtual environment.
The [script reference](../docs/development/script-reference.md) describes individual
commands, their callers, and operational prerequisites.

| Directory | Purpose |
| --- | --- |
| `bootstrap/` | Initial database installation, seed preparation, and assay validation |
| `branding/` | One blueprint for the approved application and package logos |
| `database/` | Backups, restores, indexes, capacity, report-artifact inspection, and audit-chain verification |
| `identity/` | Identity database migration and permission/role maintenance |
| `knowledgebase/` | HGNC and external reference imports, reference publication and supported database relocation |
| `docs/` | Reproducible schema/permission reference generators, Markdown lint and link validation |
| `quality/` | Repository checks, secret scanning, and test orchestration |
| `release/` | Version synchronization, Coyote Core wheel builds, and release artifact verification |

Migration commands are operator tools, not application startup hooks. Read their
runbooks and inspect the plan before enabling writes. Keep credentials, database
exports, migration plans containing identifiers, and backups outside the repository.
Clinical-data conversion lives in `migrations_scripts/`. Follow the
[execution order and commands](../docs/operations/migrations/clinical-data.md).
Export and preparation do not write to the source databases.

The identity and knowledgebase database migrations share JSON output and exit-code
handling in `database/migration_report.py`. Each command retains its own validation,
dry-run and write controls. Submission, manifest validation and pipeline login are
provided by [Coyote Relay](../services/relay/docs/README.md), not a scripts directory.

Normal deployment does not install demonstration code or samples. The optional
`coyote-demo` package supplies `coyote-demo-install` and its authenticated API
routes for an [explicitly isolated demo environment](../docs/deployment/demo-installation.md).
`install.sh data` manages identity, application and knowledgebase catalogs only.
The [synthetic clinical workflow guide](../docs/testing/clinical-workflow-demo.md)
documents the packaged installer. Offline ingest and reporting fixtures belong in
`tests/fixtures/clinical_workflows/`; they are not production startup tools.

`quality/run_package_tests.sh` runs `core`, `api`, `mongo`, `relay`, `demo`, or `all`
from each package directory. The default is its full suite; `--smoke` selects fast
checks and `--coverage` enforces that package's branch-coverage floor and writes
its local reports. It uses `PYTHON_BIN`, the active virtual environment, or root
`.venv/bin/python`. It starts no application services. GitHub CI uses smoke mode;
full suites and coverage remain available for local release validation.
Atlas and pyClient suites run in their own repositories; see the
[test ownership guide](../docs/testing/test-strategy-and-quality-gates.md#independent-package-coverage).

`branding/generate_logos.py` is the sole logo blueprint. It derives package logos
from the approved application SVG. Use `--version 4` (the default), `--name hop`,
or any new package name. `--mono` creates a separate print edition.
New lettering uses bundled Lato outlines through fontTools; existing labels retain
their approved outlines. Export for review with `--output-dir`; `--all` selects the
registered asset set and `--write` replaces registered files after review.
Tool dependencies are in `branding/requirements.txt`; optional `--raster` output
requires CairoSVG and Pillow. See
[brand asset maintenance](../docs/project/maintainer-guide.md#documentation-diagrams).

## Retention criteria

Keep scripts that support a documented, reproducible workflow for an operator,
another center, or repository automation. Each retained command needs defined inputs,
outputs, prerequisites, and failure behavior. Shared helpers belong here only when
retained commands use them. Version-specific migrations remain with their runbooks
while that upgrade path is supported.

Keep one-off inspection, migration experiments and artwork tools outside the repository.
Do not commit them or reference them from CI, tests, or operational documentation.
The staged-file guard rejects `.design/` content even when it is force-added to Git.
For documentation artwork, maintain the reviewed SVG assets themselves. Schema and
permission generators remain tracked because they reproduce references from the
application's authoritative contracts.
