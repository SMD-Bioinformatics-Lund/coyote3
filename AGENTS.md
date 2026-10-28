# Repository Instructions for Coding Agents

## Project overview

Coyote3 is a clinical genomics application for ingesting, filtering, reviewing,
annotating, classifying, and reporting genomic findings. Changes can affect clinical
interpretation and traceability; preserve established behavior unless the task explicitly
changes it, and cover clinical logic with focused tests.

The system consists of:

- A Python 3.14.7 FastAPI API using Pydantic contracts and PyMongo repositories.
- A React 19 and TypeScript frontend built with Vite and Tailwind CSS.
- MongoDB with separate application, identity/security, knowledgebase, and BAM-service databases.
- Celery workers and beat scheduling, with Redis as broker, result backend, and cache.
- Nginx, API, frontend, documentation, worker, beat, and Redis services managed through
  Docker Compose. MongoDB services have independent URI/name pairs; optional
  `mongo` and `mongo-kb` profiles provide database containers.
- MongoDB-backed governed clinical reporting rules and center-configurable TOML files.

## Repository structure

| Path | Purpose |
| --- | --- |
| `api/app/` | FastAPI composition, lifecycle, dependency wiring, and runtime setup. |
| `src/coyote3/` | Core application library; never imports `api` or the external client. |
| `src/coyote3/templates/reporting/` | Packaged Jinja report layouts, components and embedded stylesheets. |
| `clients/python/` | Independently installable HTTP-only `coyote3-client` distribution and tests. |
| `api/interfaces/http/v1/` | Version-one HTTP routers grouped by clinical or operational responsibility. |
| `src/coyote3/application/` | Use-case and workflow services. |
| `src/coyote3/domain/` | Domain models, rules, and repository protocols without framework dependencies. |
| `src/coyote3/contracts/` | Pydantic request, response, and collection schemas. |
| `api/infra/` | MongoDB repositories, integrations, observability, and infrastructure adapters. |
| `src/coyote3/config/` | Typed policy inputs, software defaults and validation. |
| `api/bootstrap/` | Installation catalogs and host-owned catalog assembly. |
| `api/services/` | Host installation operations and public-page composition. |
| `api/presentation/` | Host selection of packaged report presentation. |
| `api/config/` | Host environment loading, API security, storage paths and database settings. |
| `config/examples/center/` | Center examples copied into an external reviewed deployment directory. |
| `docs/sdk/` | SDK installation, usage, host development, generated reference and release compatibility. |
| `api/tasks/` | Celery task entry points. |
| `frontend/src/` | React pages, reusable components, hooks, libraries, styles, and unit tests. |
| `frontend/tests/e2e/` | Playwright browser tests. |
| `src/coyote3/application/reporting/clinical_rules/` | Typed report-rule evaluation, validation, rendering, and lifecycle services. |
| `tests/` | Backend unit, API, integration, contract, and fixture coverage. |
| `tests/load/` | Optional Locust HTTP workloads, target checks and synthetic smoke server. |
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

- API images target Python 3.14.7; retain Python 3.12-compatible syntax for shared
  scripts and security tooling. Use type annotations for public interfaces and nontrivial logic.
- Use Ruff for linting/import ordering and Ruff format with double-quoted strings
  and a 100-character line length.
- Use Google-style docstrings for Python modules, classes, public functions and
  nontrivial private helpers. When changing a callable, review its docstring against
  the implementation; do not generate descriptions from its name alone.
- Start with a short sentence describing the behavior. Use `Args:` for parameters
  other than `self`/`cls`, `Returns:` for a returned value, or `Yields:` for a
  generator. Explain meaning, units, accepted values, defaults and null behavior
  where relevant; type annotations do not replace this information.
- Document expected failures under `Raises:`. Use `Notes:` only for details such
  as side effects, transaction boundaries, access checks, ordering, or external
  services. Include short synthetic `Examples:` when they clarify a non-obvious API.
- Do not add empty sections or filler such as "Normalized return value", "The
  function result", or parameter descriptions that repeat the parameter name.
  Simple properties and test functions may use a precise one-line docstring; a
  procedure returning only `None` does not need a meaningless `Returns:` section.
- For FastAPI handlers, put client-facing behavior and permission requirements
  first. A docstring form-feed (`\f`) may separate that text from internal Google
  sections so injected Python dependencies do not clutter Swagger/ReDoc.
- Ruff's Google-style configuration is a formatting check, not proof of complete
  or accurate documentation. `tests/integration/test_python_docstrings.py` checks
  docstring presence in production modules, classes and named callables, including
  private helpers. Reviewers must still check meaning, accuracy and section content.
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

### Protected visual theme

- Treat the current theme as the approved baseline. Preserve its colors, gradients,
  shadows, surface hierarchy, borders, corner radii, typography and control styling.
  Change these only when the user's request explicitly calls for the affected visual
  change. General feature work, refactoring and unrelated fixes must retain the theme.
- Reuse the authoritative tokens in `frontend/src/styles/tailwind-theme.css`, the
  component styles in `frontend/src/index.css`, and the surface treatments in
  `frontend/src/styles/page-materials.css`. Extend existing component styles rather
  than introducing competing page-specific themes or overriding shared tokens locally.
- Preserve the purple-to-orange brand gradient and the distinction between page
  backgrounds, grouping panels, raised content cards and inset controls. Retain the
  existing light/dark variants and semantic clinical/status colors.
- Preserve the existing panel, card and badge elevation, including `--panel-shadow`,
  `--inner-card-shadow`, `--material-card-shadow` and `--material-badge-shadow`.
  Do not flatten surfaces, remove shadows, or add stronger elevation incidentally.
  Keep existing forced-colors accessibility overrides.
- Keep the header and sidebar joined as a continuous L-shaped surface through
  `.app-chrome-surface`. Preserve their viewport-aligned gradient; do not reintroduce
  dividing borders, shadows or contrasting backgrounds at their junction.
- Use the established typography roles consistently for equivalent labels and values.
  Reuse existing button, badge and segmented-control variants, including their selected,
  hover, focus and disabled states. Preserve compact spacing and complete corner borders.
- Keep overview cards and configured-filter cards equal in height within each grid row;
  retain natural heights when stacked. Do not clip card outlines or shadows with outer
  rounded wrappers or overflow rules.
- Report paper has its own embedded styles in `src/coyote3/templates/reporting/assets/`.
  Preserve embedded Source Sans 3 typography, neutral tables, restrained purple/orange accents,
  the pale yellow conclusion and shared HTML/PDF geometry when changing report presentation.
- Fix confirmed visual regressions within this baseline without requesting additional
  approval. Verify affected light/dark and narrow/wide layouts; check collapsed/expanded
  navigation or HTML/PDF output when those surfaces change. Report intentional deviations.

## Architecture rules

- The installable library never imports `api`. Select center configuration explicitly
  before importing vocabulary-dependent contracts; one process uses one immutable profile.
- SDK release identity belongs to `pyproject.toml`; application identity and its exact
  SDK selection belong to `release.toml`. Keep HTTP and clinical configuration revisions separate.
- The Coyote3 wheel includes root-level API modules and server assets; `[api]`
  enables their dependencies. The core must import without those dependencies.
  Client code lives in its own distribution and imports neither core nor API.

- HTTP routers declare paths, permissions, dependencies, and response contracts, then
  delegate behavior to `src/coyote3/application` services.
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
- Locust runs in a separate environment using `requirements-load.txt`, not the API
  runtime. Load only an explicitly approved synthetic deployment through its proxy.
  Preserve target/database checks, TLS verification, CSRF handling and opt-in writes.
  Never aim load tests at production or external knowledgebase APIs. HTTP load tests
  do not replace browser acceptance, clinical validation or deployment capacity tests.
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
scripts/quality/run_quality_suite.sh

# Backend tests, lint, formatting, and configured type-check boundary
PYTHONPATH=. .venv/bin/pytest -q tests/unit tests/api tests/integration
PYTHONPATH=. .venv/bin/ruff check src api tests scripts
PYTHONPATH=. .venv/bin/ruff format --check src api tests scripts
PYTHONPATH=. .venv/bin/mypy

# Frontend development and verification
npm --prefix frontend run dev
npm --prefix frontend run lint
npm --prefix frontend run test:coverage
npm --prefix frontend run build
npm --prefix frontend run test:e2e

# Documentation
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict

# Standalone load-generator smoke test against a synthetic HTTP server
# Run with a separate interpreter where requirements-load.txt is installed.
.venv-load/bin/python tests/load/smoke_test.py
```

Start the development stack with the version-aware Compose wrapper:

```bash
cp deploy/env/example.env .coyote3_dev_env
./scripts/deployment/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

The environment file must contain the required deployment-specific values. Do not commit it.
The base Compose stack expects configured MongoDB endpoints and a pre-created application network.
Reuse `api/config/mongo.py` and `api/infra/mongo/connections.py`; never infer a host
from a database name or pass a session across different MongoClient instances.

## Agent working rules

### Scope and evidence

- Before editing, identify the requested outcome, the current behavior, its owning
  layer, and the smallest set of files needed. Inspect nearby code, callers,
  contracts, tests and documentation. Every changed file must have a task-related reason.
- Make the smallest coherent change that fully solves the task. Do not bundle
  unrelated cleanup, renaming, formatting, dependency upgrades or redesigns with a fix.
- Broad requests such as "audit", "improve", or "find bugs" require investigation;
  they do not automatically authorize rewriting working subsystems. Fix confirmed
  problems and distinguish evidence from suspected issues and optional improvements.
- Reproduce a reported bug where practical before changing production code. A long
  file, unfamiliar pattern, old timestamp, failing fixture or coverage gap alone
  does not establish that runtime behavior is wrong.
- Resolve routine implementation choices within the authorized task without repeated
  confirmation. Clarify only material ambiguity, especially intended clinical behavior,
  contract changes, or destructive operational actions.

### Additions and abstractions

- Search for an existing service, repository, hook, component, theme token or helper
  before adding one. Extend the authoritative implementation when that is sufficient.
- Add files and abstractions only for a concrete responsibility, real duplication,
  or an established architectural boundary. Do not split code merely to reduce line
  counts, increase component counts, or make a change look more substantial.
- Keep React pages responsible for route composition and feature coordination.
  Extract cohesive UI or asynchronous behavior into focused components or hooks;
  do not introduce forwarding components, convenience layers or unnecessary props.
- Do not add speculative features, configuration switches, compatibility paths,
  dependencies or operational scripts. A new dependency must be necessary for the
  requested behavior and justified against the tools already present.
- Never invent dependencies, commands, paths, collection fields or architectural
  details. Check the repository before documenting or using them.

### Refactoring and protected behavior

- Keep structural refactoring separate from intentional behavior changes. Preserve
  API calls, query keys, permissions, editing leases, revision checks, cache
  invalidation, cancellation, loading/error states and accessible interactions.
- A visual or component change must not alter report wording, finding eligibility,
  transcript selection, tier matching, annotation identity, saved filters or report
  snapshots. Use established clinical regression tests to verify these boundaries.
- Preserve supported behavior and backwards compatibility unless a breaking change
  is explicitly requested. Do not retain obsolete behavior through hidden fallbacks,
  duplicate implementations or aliases that hide incomplete migrations.
- Do not silently modify APIs, schemas, database structures, permissions, configuration
  defaults or generated artifacts. Trace affected consumers and include migrations,
  regeneration and documentation when the requested contract change requires them.
- For styling, use existing components and semantic tokens. Check the impact of a
  shared style change; do not apply broad global overrides to solve one page's issue.

### Deletions and retirement

- Delete code or assets only after establishing that they are obsolete, redundant,
  or outside the supported implementation. Search imports, dynamic registries,
  routes, package resources, scripts, tests, documentation and generators first.
  Absence from a simple text search is not sufficient proof that something is unused.
- Before removing a document or implementation, preserve any unique supported
  behavior or instructions in its maintained owner. Update callers, navigation,
  section anchors and asset references in the same change.
- Do not remove supported migration procedures, historical report artifacts,
  clinical provenance or architecture decisions merely because they are old.
  Removing repository code does not authorize deleting operational or clinical data.
- Remove obsolete source files when a replacement is complete; do not leave a second
  implementation or placeholder forwarding layer. Change generators rather than
  deleting generated output that the next build will recreate.

### Verification and completion

- Run the narrowest relevant checks while iterating, then the applicable broader
  checks after the final change. Scale verification to the affected behavior;
  clinical, security, persistence and concurrency changes need focused regressions.
- Test observable behavior and failure boundaries. Reuse existing regression tests
  for code moves; do not add tests that only repeat component structure or implementation.
- Do not lower coverage gates, disable checks, skip failing tests, weaken assertions
  or update snapshots solely to obtain a passing result. Update stale fixtures only
  after checking the authoritative contract. Investigate timeouts and test contention
  before increasing limits.
- For UI changes, verify relevant light/dark and narrow/wide layouts, keyboard use,
  loading, empty and error states. For documentation-site changes, validate source
  links, the strict build and built-site anchors/assets. Instruction-only edits need
  Markdown lint and diff review, not application tests. Check executable permissions
  for documented shell entry points.
- Review the complete task diff for accidental deletions, generated-file drift,
  unrelated churn and new dependencies. Report what changed, why, what actually ran,
  and remaining risks or skipped checks. Do not claim the application is bug-free
  or a workflow is validated beyond the evidence obtained.

### Workspace and Git discipline

- Inspect Git status and relevant diffs before editing. Treat existing uncommitted
  changes as user work unless their ownership is established. Do not overwrite,
  revert, stash or delete them to simplify the task.
- Never use destructive Git commands or rewrite shared history without explicit
  authorization for that action and its affected work.
- Use `apply_patch` for manual text edits. Avoid repository-wide replacements,
  automatic reformatting and file moves unless necessary for the requested scope;
  inspect every affected file when a mechanical change is needed.
- Do not stage, commit, push, merge, deploy or publish without session authorization.
  Never stage unrelated work. If an authorized workflow requires an index-only or
  executable-mode change, preserve existing staged content and disclose that change.
- Set up the tracked pre-commit hook with `git config core.hooksPath .githooks`; do not
  run `pre-commit install`. Do not otherwise change Git settings to hide or simplify a diff.
- Do not change agent instructions, architecture baselines, lint rules or quality
  policies to make an implementation easier. Policy changes must be part of the
  requested task.

### Documentation and temporary tooling

- Write documentation as a current reference for users and developers. Name the
  actual operation, resource, condition and result. Avoid promotional claims,
  generic introductions, unsupported guarantees, and accounts of how an agent
  changed the implementation. Keep upgrade instructions only where operators need
  them to deploy safely. Do not remove precise technical terms merely because they
  also occur in generated prose.
- Keep `scripts/` limited to documented, reproducible operational or repository
  workflows and their shared helpers. Put one-off fixes, artwork generators and
  coding-session experiments in ignored `.design/`; tracked code, tests, CI and
  documentation must not depend on scratch tooling. Commit reviewed SVG artwork,
  not disposable scripts used to create it.

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
- Generated documentation such as `docs/sdk/reference.md`, `docs/reference/mongodb-collections.md` and
  `docs/administration/permission-catalog.md`; change their source and run the repository
  generator instead.
- Generated HTTP types under `frontend/src/lib/generated/` and
  `deploy/compose/mongo-init/identity-role-policy.json`; change the authoritative
  API or permission policy and run the documented generator instead.
- Dependency lockfiles unless the dependency graph intentionally changes.
