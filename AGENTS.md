# Repository Instructions for Coding Agents

## Project overview

Coyote3 is a clinical genomics application for ingesting, filtering, reviewing,
annotating, classifying, and reporting genomic findings. Changes can affect clinical
interpretation and traceability; preserve established behavior unless the task explicitly
changes it, and cover clinical logic with focused tests.

The system consists of:

- A Python 3.12 FastAPI API using Pydantic contracts and PyMongo repositories.
- A React 19 and TypeScript frontend built with Vite and Tailwind CSS.
- MongoDB with separate application, identity/security, knowledgebase, and BAM-service databases.
- Celery workers and beat scheduling, with Redis as broker, result backend, and cache.
- Nginx, API, frontend, documentation, worker, beat, and Redis services managed through
  Docker Compose. MongoDB is supplied separately through `MONGO_URI`.
- Static YAML clinical reporting rules and center-configurable TOML files.

## Repository structure

| Path | Purpose |
| --- | --- |
| `api/app/` | FastAPI composition, lifecycle, dependency wiring, and runtime setup. |
| `api/interfaces/http/` | Thin HTTP routers grouped by clinical or operational responsibility. |
| `api/application/` | Use-case and workflow services. |
| `api/domain/` | Domain models, rules, and repository protocols without framework dependencies. |
| `api/contracts/` | Pydantic request, response, and collection schemas. |
| `api/infra/` | MongoDB repositories, integrations, observability, and infrastructure adapters. |
| `api/config/` | Software defaults, bootstrap catalogs, and center configuration loading. |
| `api/tasks/` | Celery task entry points. |
| `frontend/src/` | React pages, reusable components, hooks, libraries, styles, and unit tests. |
| `frontend/tests/e2e/` | Playwright browser tests. |
| `clinical_reporting_rules/` | Versioned static report-rule YAML grouped by assay and subpanel. |
| `tests/` | Backend unit, API, integration, contract, and fixture coverage. |
| `deploy/` | Dockerfiles, Compose definitions, proxy configuration, and environment examples. |
| `scripts/` | Quality, bootstrap, deployment, maintenance, and contract-generation tools. |
| `docs/` | MkDocs user, developer, API, configuration, and operations documentation. |
| `demo_data/` | Synthetic demonstration and validation data only. |

Important entry points are `api/app/main.py`, `asgi.py`, `run_api.py`,
`api/celery_app.py`, and `frontend/src/main.tsx`.

## Development conventions

### Shared

- Follow `.editorconfig`: LF line endings, a final newline, trimmed trailing whitespace,
  two-space indentation by default, and four spaces for Python.
- Keep source lines within 100 characters where practical.
- Use descriptive domain names already established by the repository. Do not introduce
  aliases or compatibility shims for renamed concepts unless explicitly required.
- Never add secrets, credentials, tokens, patient information, real sample identifiers,
  or private operational data.

### Python

- Target Python 3.12 and use type annotations for public interfaces and nontrivial logic.
- Use Ruff for linting/import ordering and Ruff format with double-quoted strings. Black
  compatibility is configured at a 100-character line length.
- Use Google-style docstrings where a public or complex API needs explanation.
- Prefer Pydantic models at contracts and validation boundaries. Preserve meaningful
  `None` values when the contract distinguishes null from a missing field.
- Raise established application/domain errors and let the centralized HTTP exception
  handling produce API responses. Do not expose raw PyMongo result types above infra.
- Keep imports directed inward: domain and application code must not import FastAPI,
  Starlette, or `api.app`; infrastructure and lower layers must not depend on app wiring.

### TypeScript and React

- TypeScript is strict enough to reject unused locals and parameters. Avoid `any`; model
  API data and component props explicitly.
- Use the `@/` alias for imports from `frontend/src` and follow the existing import style.
- Prefer existing layout, UI, data-table, tooltip, badge, chart, comments, detail, and form
  components before creating another implementation.
- Use `PageFrame` as the owner of route width and gutters, and `PageShell` for standard page
  headings and actions.
- Use semantic theme tokens and typography roles. Do not add raw palette colors in pages,
  arbitrary text sizes, `transition-all`, `font-black`, or `font-extrabold`.
- Use the existing `.dark` theme mechanism, Lucide icons, focus states, reduced-motion
  behavior, and accessible labels. Do not communicate clinical meaning by color alone.

## Architecture rules

- HTTP routers declare paths, permissions, dependencies, and response contracts, then
  delegate behavior to `api/application` services.
- Business and clinical rules belong in application/domain modules, not route handlers,
  React pages, or MongoDB repositories.
- MongoDB access belongs in `api/infra/mongo/repositories`. Depend on repository protocols
  or explicit repositories; do not access raw collections from routes, domain, or
  application code.
- Keep Pydantic transport/collection contracts separate from persistence implementation
  and frontend display models.
- Frontend API access must remain behind the existing client/query abstractions. Keep the
  UI route registry synchronized when a page gains or changes an API dependency.
- Treat public API paths, Pydantic schemas, MongoDB collection contracts, configuration
  keys, permissions, report snapshots, and clinical rule syntax as deliberate contracts.
  Do not change them silently.
- Do not alter report wording, filtering behavior, transcript selection, tier matching, or
  finding identity logic as incidental refactoring. Compare established behavior and add
  regression tests when these areas change.
- Reuse configuration and constants from their authoritative modules. Center-specific
  values belong in supported configuration files; software invariants belong in code.
- Update source schemas or generators before regenerating derived documentation. Do not
  hand-edit generated contract or permission catalog pages.

Architecture boundary tests in `tests/integration/test_api_architecture_boundaries.py`
enforce several of these rules and must remain passing.

## Testing

- Backend tests use pytest with unit, API, integration, and contract markers. Overall branch
  coverage is collected from `api` and has a 75% minimum.
- Frontend unit/component tests use Vitest and Testing Library under `frontend/src`.
- Browser tests use Playwright under `frontend/tests/e2e`.
- Add positive, negative, authorization, validation, and regression cases appropriate to
  the behavior changed. Clinical and cross-layer changes require broader coverage than a
  visual-only change.
- Update test fixtures to the current schema instead of adding runtime compatibility for
  stale fixture shapes.
- Never place real clinical data in tests or snapshots.

## Build and development commands

Run commands from the repository root unless noted otherwise.

```bash
# Full repository quality gate
scripts/run_quality_suite.sh

# Backend tests, lint, formatting, and configured type-check boundary
PYTHONPATH=. .venv/bin/pytest -q tests/unit tests/api tests/integration
PYTHONPATH=. .venv/bin/ruff check api tests scripts
PYTHONPATH=. .venv/bin/ruff format --check api tests scripts
PYTHONPATH=. .venv/bin/mypy

# Frontend development and verification
npm --prefix frontend run dev
npm --prefix frontend run lint
npm --prefix frontend run test:coverage
npm --prefix frontend run build
npm --prefix frontend run test:e2e

# Documentation
npm run docs:lint
.venv/bin/python scripts/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict
```

Start the development stack with the version-aware Compose wrapper:

```bash
cp deploy/env/example.env .coyote3_dev_env
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

The environment file must contain the required deployment-specific values. Do not commit it.
The base Compose stack expects an external MongoDB URI and a pre-created application network.

## Agent working rules

- Inspect nearby code, tests, contracts, and documentation before editing.
- Make the smallest coherent change and leave unrelated code and user changes untouched.
- Reuse existing services, repositories, hooks, and components; add an abstraction only
  when it removes real duplication or follows an established pattern.
- Preserve supported behavior and backwards compatibility unless a breaking change is
  explicitly requested. Do not preserve obsolete behavior through hidden fallbacks or shims.
- Do not silently modify APIs, schemas, database structures, clinical rules, permissions,
  configuration contracts, or generated artifacts. Include migrations and documentation
  when a requested contract change requires them.
- Run the narrowest relevant checks while iterating, then the applicable broader checks.
  State clearly which checks could not be run.
- Use `apply_patch` for manual edits. Do not overwrite unrelated uncommitted work or use
  destructive Git commands.
- Set up the tracked pre-commit hook with `git config core.hooksPath .githooks`; do not run
  `pre-commit install` against this repository.
- Never invent dependencies, commands, paths, collection fields, or architectural details.

## Files and directories to avoid

Do not manually edit or commit:

- `.venv/`, `node_modules/`, `frontend/node_modules/`, Python caches, and tool caches.
- `frontend/dist/`, `site/`, coverage output, `htmlcov/`, `test-results/`, and
  `playwright-report/`.
- Local environment files, logs, reports, Redis state, database dumps, backups, ingest
  staging areas, or other runtime data.
- Nextflow `work/` directories or pipeline result trees if they are present locally.
- Private scratch directories such as `.design/`, `.internal/`, `.agents/`, `.codex/`, and
  `.claude/`.
- Generated documentation such as `docs/api/collection_contracts.md` and
  `docs/developer/permission_catalog.md`; change their source and run the repository
  generator instead.
- Dependency lockfiles unless the dependency graph intentionally changes.
