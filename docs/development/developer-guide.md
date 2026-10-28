# Developer manual

This manual describes Coyote3's application structure, runtime dependencies,
data contracts and development interfaces. It covers the FastAPI backend,
React frontend, background workers and their shared persistence services.

Installation and deployment procedures are maintained in
[First installation](../deployment/first-installation.md) and
[Center deployment](../deployment/bootstrap-data-flow.md). Clinical rule
authoring is documented in [Clinical reporting rules](../reference/clinical-reporting-rules.md).

## Development environment

Backend dependencies and Python tooling are declared in `pyproject.toml`.
Frontend dependencies, the Node.js requirement and npm scripts are declared in
`frontend/package.json`; `frontend/package-lock.json` records resolved versions.
Use the Python version of the target API image when reproducing runtime behavior.
Shared scripts and security tooling retain Python 3.12-compatible syntax.

The application requires configured MongoDB endpoints and Redis. MongoDB workflows
that use transactions require a replica set, including for local development.
A single-member replica set can host the logical databases on one local instance.

### Local stack

The development stack uses the base Compose definition with the development overlay:

```bash
./scripts/deployment/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

Before running this command, populate the environment file from
`deploy/env/example.env`, provision the configured databases and host storage,
and create the application network. The base stack connects to configured MongoDB
endpoints; it does not require a local MongoDB container. Container provisioning,
optional database profiles and storage permissions are covered in
[MongoDB deployment and recovery](../deployment/mongodb-setup-and-recovery.md).
Docker Compose 1.29.2 uses the separate definitions under `deploy/legacy`.

Local environment files contain deployment settings and secrets and are not
version-controlled. Development and test databases must be separate from production.
Use synthetic samples for local verification and browser fixtures.

## Application structure

| Location | Responsibility |
| --- | --- |
| `api/app/` | FastAPI composition, lifecycle, middleware and dependency wiring. |
| `api/interfaces/http/` | HTTP routes, transport contracts and access dependencies. |
| `src/coyote3/application/` | Clinical and administrative workflows coordinating domain rules, repositories and integrations. |
| `src/coyote3/domain/` | Domain rules, identity logic, query policies and repository protocols. |
| `src/coyote3/contracts/` | Request, response, collection and managed-resource contracts. |
| `api/infra/` | MongoDB persistence, cache, integrations, notifications and observability. |
| `api/security/` | Authentication, authorization and password workflows. |
| `src/coyote3/config/` | Typed center inputs, software constants and policy validation. |
| `api/bootstrap/` | Host installation catalogs and catalog assembly. |
| `api/services/` | Authorized demo/deployment installation and public-page composition. |
| `api/contracts/` | Host-only HTTP, session, diagnostic and installation contracts. |
| `api/presentation/` | Host selection of packaged report presentation. |
| `src/coyote3/templates/reporting/` | Legacy/modern Jinja layouts, components and embedded CSS. |
| `clients/python/` | Independent typed sync/async HTTP client distribution and tests. |
| `api/config/` | Host startup, environment settings, API security, storage and MongoDB configuration. |
| `config/examples/center/` | Examples for an external reviewed center directory. |
| `docs/sdk/` | SDK installation, usage, development, generated reference and version compatibility. |
| `api/tasks/` | Celery task entry points. |
| `frontend/src/pages/` | Route-level React views. |
| `frontend/src/components/` | Shared layouts, forms, tables and clinical display components. |
| `frontend/src/hooks/` | Shared state and query hooks. |
| `frontend/src/lib/` | HTTP client, route registry and display utilities. |
| `tests/` | Backend unit, API and integration coverage. |
| `frontend/tests/e2e/` | Playwright browser coverage. |
| `scripts/` | Bootstrap, maintenance, contract generation and verification commands. |
| `deploy/` | Container builds, Compose definitions, proxy configuration and environment templates. |

The API entry points are `api/app/main.py`, `asgi.py` and `run_api.py`.
Celery is configured through `api/celery_app.py`. The frontend starts at
`frontend/src/main.tsx`.

### Dependency boundaries

HTTP routes declare transport models, dependencies and permissions, then delegate
to application services. Application services coordinate the operation; domain
modules supply clinical and identity rules. Repositories own MongoDB queries,
indexes and driver interactions.

Domain and application modules do not import FastAPI, Starlette or application
assembly from `api.app`. The frontend consumes HTTP contracts, not Python modules
or database documents directly. These boundaries are checked by
`tests/integration/test_api_architecture_boundaries.py`.

## Runtime services

![Runtime topology](../assets/diagrams/runtime-topology.svg)

| Service | Responsibility |
| --- | --- |
| Frontend | Navigation, forms, clinical display and browser query state. |
| API | Authentication, authorization, validation and application workflows. |
| Celery worker | Queued ingest and maintenance operations. |
| Celery beat | Periodic task scheduling. |
| MongoDB | Persistent application, identity, knowledgebase and BAM-service records. |
| Redis | Celery broker, results and configured caches. |
| Nginx | Browser-facing service routing and response headers. |

An HTTP request passes through middleware and access dependencies before the
application service runs. API access remains authoritative even when a frontend
control is hidden or disabled. Background tasks initialize their runtime and
invoke application services without an HTTP request context.

## Configuration ownership

| Configuration | Runtime source |
| --- | --- |
| Database endpoints, credentials, service URLs and host mounts | Deployment environment. |
| Contacts and clinical presentation policy | External center profile initialized from `config/examples/center/`. Query rules remain governed database resources. |
| Assay groups, diagnosis definitions and assay associations | MongoDB registries. |
| Assays, assay configurations and gene lists | Versioned ASP, ASPC and ISGL documents. |
| Clinical reporting rules | Governed rule-set documents in the application database. |
| Public catalog structure and narrative | Governed catalog documents in the application database. |
| Runtime module and maintenance controls | `app_controls`. |
| Roles, permissions and user assignments | Identity database records. |
| Durable user display preferences | `users.ui_settings`. |
| UI colors, typography and surfaces | Frontend theme tokens and shared components. |

Bootstrap catalogs supply installation data; they do not replace the runtime
registry. The configuration keys, defaults and deployment requirements are listed
in the [configuration reference](../deployment/configuration-reference.md). Center file
schemas are documented in [Center configuration files](../deployment/center-configuration.md).

## Database access

### Logical databases

Each MongoDB service has an independently configured URI and database name:

| Service | URI setting | Database setting |
| --- | --- | --- |
| Application | `COYOTE3_MONGO_URI` | `COYOTE3_DB` |
| Identity | `IDENTITY_MONGO_URI` | `IDENTITY_DB` |
| Knowledgebase | `KNOWLEDGEBASE_MONGO_URI` | `KNOWLEDGEBASE_DB` |
| BAM service | `BAM_MONGO_URI` | `BAM_DB` |

`api/config/mongo.py` resolves endpoint configuration.
`api/infra/mongo/connections.py` owns connection pools for the runtime process.
Services with identical URIs share a `MongoClient`; different endpoints can use
different hosts and replica-set names. Database names do not determine hosts or
filesystem paths.

### Contracts and transactions

Collection models are registered in `src/coyote3/contracts/schemas/registry.py`.
The [collection reference](../reference/mongodb-collections.md) describes their fields.
Request validation, application normalization and collection validation serve
different boundaries; a valid HTTP request does not by itself establish that a
document is ready to persist.

Related writes use the transaction boundary of their owning workflow. A MongoDB
session belongs to its originating client and cannot be passed to another
`MongoClient`. Filesystem operations, mail delivery and writes on separate MongoDB
deployments are not covered by a single database transaction. Their recovery and
delivery behavior is specified in
[Transactions and ingest recovery](../architecture/transactions-and-ingest-recovery.md).

Missing fields and explicit `null` values are distinct where the collection model
defines them that way. Serialization must preserve that distinction.

### Identity and revisions

Business identifiers such as `asp_id`, `aspc_id` and `isgl_id` identify resources.
MongoDB `_id` values identify individual persisted documents. Versioned resources
retain prior revisions so existing references can be resolved independently of
the currently active revision.

Sample configuration resolution is implemented in
`src/coyote3/application/common/assay_config.py`. When `current_aspc_id` is present,
normal resolution uses that exact revision. Active configuration lookup applies
to ingestion, unassigned samples and explicit configuration updates. Saved report
snapshots are not reconstructed from the current active configuration.

### Index administration

Repositories declare their index contracts. API startup inspects those contracts
and logs missing or conflicting indexes without creating, replacing or dropping them.
Index changes are explicit maintenance operations:

```bash
PYTHONPATH=. .venv/bin/python scripts/database/manage_mongo_indexes.py status
PYTHONPATH=. .venv/bin/python scripts/database/manage_mongo_indexes.py plan
```

With the target database configured and the plan reviewed, `apply` creates missing
compatible indexes. It does not drop conflicting indexes:

```bash
PYTHONPATH=. .venv/bin/python scripts/database/manage_mongo_indexes.py apply
```

## Clinical configuration

| Resource | Purpose |
| --- | --- |
| Assay group | Clinical grouping and availability of associated assays. |
| Assay (ASP) | Assay identity, sequencing attributes, physical gene coverage and input-file policy. |
| Diagnosis | Shared interpretation scope associated with one or more assays. Availability can be controlled per association. |
| Assay configuration (ASPC) | Assay, diagnosis and environment-specific analyses, filter profiles and reporting settings. |
| Gene list (ISGL) | Named gene selection offered to the analysis types declared by `list_type`. |

`base` is the default interpretation scope when no named diagnosis is selected.
Named diagnosis choices come from the selected assay's associations.

Filter profiles separate analysis intent and finding type. An SNV gene-list
selection does not implicitly restrict CNVs or fusions. Selected lists and
ad-hoc genes are intersected with the assay's eligible genes; without a selection,
assay eligibility applies. Empty eligibility or a selection with no overlap
selects no findings, including for WGS and WTS.

The backend applies clinical predicates before sorting and pagination. UI tables
display the resulting records and do not independently decide clinical inclusion.
See [Query and filter strategy](../reference/assay-filtering.md) for filter
composition, supported operators and scope examples.

## Ingestion

![Sample ingest workflow](../assets/diagrams/celery-ingest-flow.svg)

Ingest reads a sample manifest, resolves its assay configuration, validates the
declared files and parses analysis data into collection-ready documents. A declared
file must be readable and valid even when that file type is optional for the assay.

| Stage | Result |
| --- | --- |
| Manifest validation | Supported pipeline keys and sample metadata. |
| Configuration resolution | Applicable assay and environment-specific configuration. |
| File validation and parsing | Validated analysis records and sample counts. |
| Persistence | Sample, declared evidence and applicable async completion receipt committed together. |
| Completion | Staging cleanup, watcher acknowledgement and audit delivery. |

Parsing and filesystem work occur outside the clinical database transaction.
A parsing failure prevents clinical writes. A failure after a confirmed commit
does not make the committed sample disappear. The
[ingestion API](../api/sample-ingestion.md) defines submission, failure and recovery
behavior. Parser input formats are specified in
[Sample input files](../reference/ingest-files/README.md#file-contracts) and [Sample YAML](../reference/sample-manifest.md).

## Reporting

The **Try new report** feature renders the established clinical inputs through
the alternate Jinja layout in `src/coyote3/templates/reporting/modern/`. The authorized
`Reports.try_new` operation returns matching HTML/PDF content in memory without
report numbering or persistence. See the [user workflow](../user-guide/try-new-report.md)
and [package boundaries](../sdk/package-boundaries.md).

![Reporting workflow](../assets/diagrams/report-generation-flow.svg)

Clinical rule sets are stored in MongoDB and follow the authoring, review and
publication workflow. Publishing approved rule content does not require a new
application build.

`src/coyote3/application/reporting/clinical_rules/resolution.py` selects an active published
release using the assay, sample diagnosis, analyte and reporting language. An exact
diagnosis release takes precedence; assay Base is used only when no exact release
exists. Selection does not cross assays, analytes or languages. Ambiguous releases,
invalid content and checksum mismatches produce an error rather than a silent
switch to another rule set.

| Stage | Responsibility |
| --- | --- |
| Fact preparation | Build typed facts from the sample, configuration, findings, gene lists and comments. |
| Evaluation | Apply typed conditions and output nodes, producing report text and an evaluation trace. |
| Preview | Render HTML/PDF without saving a report. |
| Save | Persist report metadata, artifacts, resolved rule provenance and applicable finding snapshots. |

Rule conditions and outputs are data, not executable Python or arbitrary templates.
Report descriptions and formatted comments are sanitized; biological values are
escaped. Browser report previews are sandboxed. Stored reports retain the provenance
of their generation rather than selecting a newly published release when viewed.

The [reporting workflow](../reference/report-snapshots.md)
defines snapshot behavior. The [clinical rule reference](../reference/clinical-reporting-rules.md)
defines matching, ordering, governance and authoring constraints.

## Security and observability

### Authentication and authorization

Deployments can enable local authentication, LDAP or both. Browser sessions use
the configured session cookie; state-changing cookie-authenticated requests require
the session CSRF token. Supported bearer authentication is handled at the API boundary.

Public-page identity checks also use the shared frontend API client so an
authenticated `GET /auth/whoami` captures the CSRF token before settings are saved.
These optional checks set `redirectOnUnauthorized: false` and handle anonymous
responses inline. Protected requests retain the default login redirect; the option
does not bypass API authentication or CSRF validation.

Roles bundle permissions. API access checks combine the required permission with
applicable assay and environment scope. Frontend visibility is not an authorization
decision. Bootstrap permissions and roles are installed from
`api/bootstrap/catalogs/rbac/`; MongoDB holds runtime assignments.

System-managed identity definitions are protected by their resource policies.
Password changes, session state and user preferences use their dedicated operations.
Detailed account, session and authorization behavior is specified in the
[security model](../architecture/security-model.md).

### Errors, logs and audit

Application services raise established application or domain errors. Centralized
HTTP handling produces client responses; unexpected exception details belong in
server logs, not user-facing messages. The frontend API client handles transport
failures, session expiry and validation responses consistently.

Diagnostic logs record execution failures and request context. Audit records capture
accountable actions such as access administration, clinical configuration changes,
curation, ingestion and report creation. Logs and audit records serve different
purposes and are not interchangeable. Retention and delivery behavior is documented
in [Audit and logging](../operations/audit-and-logging.md).

## Frontend interfaces

Native text inputs, selects, textareas, combobox triggers and rich-text editors share
the outlined field surface in `frontend/src/styles/form-controls.css`. The global
stylesheet imports it once, so lazy-loaded pages and native controls receive the
same light/dark surface, inset shadow, focus ring and validation state. Disabled
and read-only controls use the muted surface. Checkbox, radio, range, color, upload
and hidden controls retain their specialized presentation. Do not add page-specific
background or shadow overrides for ordinary fields. Rich-text editors use one outer
outline around their toolbar and content.

Admin routes in `frontend/src/App.tsx` name their resource pages explicitly.
Each resource has a feature directory under `frontend/src/pages/admin/` containing
its list page, editor page, and `resource.ts` configuration. The list page composes
its table columns, toolbar, row actions, and additional panels. The editor page
owns the form layout and resource-specific behavior. Assay creation uses
`AssaySetupPage.tsx` rather than the ordinary resource editor.

| Directory | List page | Editor page |
| --- | --- | --- |
| `assays/` | `AssaysPage` | `AssayEditorPage` |
| `assay-configurations/` | `AssayConfigurationsPage` | `AssayConfigurationEditorPage` |
| `gene-lists/` | `GeneListsPage` | `GeneListEditorPage` |
| `users/` | `UsersPage` | `UserEditorPage` |
| `roles/` | `RolesPage` | `RoleEditorPage` |
| `permissions/` | `PermissionsPage` | `PermissionEditorPage` |
| `samples/` | `AdminSamplesPage` | `AdminSampleEditorPage` |

To change assay columns or filters, edit `assays/resource.ts`; to change an assay
cell, action, or table layout, edit `assays/AssaysPage.tsx`. Assay diagnosis
associations belong to `AssayEditorPage.tsx`. DNA/RNA schema selection belongs to
the configuration editor, and account-assignment restrictions belong to the user
editor. Sample administration uses the JSON document editor.

`useAdminList` and `useAdminEditor` share request, mutation, and form-state
mechanics. Their callers supply resource endpoints, permissions, document keys,
request envelopes, and additional cache invalidations. Shared toolbar, action,
confirmation, and loading controls do not select behavior by resource name.
`resource-specs.ts` collects resource metadata for navigation; it does not own
table layouts or resource-specific forms.

`AdminControlsPage.tsx`, `AdminAuditPage.tsx`, and `AdminIngestPage.tsx` each own a
separate operational workflow. Keep route metadata in `ui-route-registry.ts`
synchronized with page ownership and API dependencies.

Public routes also have dedicated modules: `PublicCatalogPage.tsx`,
`PublicCatalogMatrixPage.tsx`, `GeneInfoPage.tsx`, `PublicGenelistPage.tsx`,
`PublicAspGenesPage.tsx`, and `CoverageBlacklistPage.tsx`. About, contact,
not-found, password-request, and password-reset routes each have their own page.
Route modules are loaded independently through `App.tsx`.

Pages coordinate route parameters and top-level composition. Feature hooks own
request, mutation and asynchronous state when that behavior needs a separate boundary.
Keep cohesive editors, viewers, and presentation helpers beside their owning
feature instead of adding unrelated routes to one module:

| Feature | Supporting modules |
| --- | --- |
| Clinical rules | `RuleConditionBuilder`, `RuleOutputEditor`, `RuleEditor`, and condition/authoring helpers. |
| Admin resource forms | `AdminManagedForm`, `FormControl`, `CheckboxGroup`, and `ObjectFieldEditor`. |
| Sample overview | `PanelSummary`, `AnalysisStatusStrip`, and overview data helpers. |
| Coverage | `CoverageGeneView` and coverage presentation helpers. |
| Small-variant detail | `VariantEvidencePanel` owns knowledgebase presentation and on-demand public lookups. |
| Sample and gene-cohort tables | `useSampleColumns`, `useSampleExportColumns`, and `useCohortColumns`. |
| Public matrix | `AssayMatrixTable` and matrix layout helpers. |
| Report review | `useReportPreview` owns preview/PDF requests, saving and feedback; `ReportDocumentPreview` and `ReportReviewSummary` render the document and immutable finding snapshot. |
| Dashboard charts | Individual modules under `components/dashboard/` own composition, tiers, gene coverage, capabilities and tiered-gene plots. |
| Knowledgebase charts | `CancerGeneCensusChart` and `KnowledgebaseStatisticsCharts` live with knowledgebase components and load independently of dashboard charts. |
| Rule workspace layout | `useRuleWorkspaceLayout` owns pane widths and collapse state; the shared `components/admin/RuleWorkspaceDivider` handles pointer and keyboard resizing. |

Share form controls and presentation components without duplicating resource
workflows. Keep pure helpers separate from React components so they can be tested
without rendering a page. Page tests cover query state, permissions, navigation,
and mutations; component tests cover local editing and display behavior.

`frontend/src/App.tsx` declares React routes. The registry under
`frontend/src/lib/routes/` records route, module and API dependencies for the admin
route audit and contract tests. API access uses the shared client; React Query owns
server-state caching and mutation invalidation.

| Interface | Responsibility |
| --- | --- |
| `PageFrame` and `PageShell` | Route width, gutters, headings and page actions. |
| Shared form components | Typed input, validation feedback and resource selection. |
| `DataTable` and TanStack Table | Column definitions, selection and table presentation. |
| `useClinicalTableState` | URL-backed server pagination, search and sorting. |
| Theme tokens | Consistent colors, typography, surfaces and interaction states. |
| `users.ui_settings` | Persisted user-owned display preferences. |

Sequencing badges use `sequencingValueClasses` in `lib/badge-colors.ts` and the
theme's `--color-dna`, `--color-rna`, `--color-panel-dna`, `--color-panel-rna`,
`--color-wgs` and `--color-wts` tokens. Reuse these classes for modality and technical
family badges. Catalog card outlines, shadows, inner gradients and technical-family
badges use the corresponding family color; DNA/RNA badges retain modality colors.
Light-theme card gradients use faint tints. Dark-theme cards use charcoal surfaces
with subtle family tints, muted borders and restrained shadows. The catalog heading
and filter panel sit slightly above the page background.
Badges inside service cards have an all-around shadow and inset highlights. Both themes
retain text labels so color is not the only identifier.

Domain badge classes name the value they represent: for example `badge-snv`,
`badge-illumina`, `badge-auth-local` and `badge-role-admin`. Their tokens in
`styles/domain-badge-theme.css` use named color palettes that vary by theme.
Use `valueBadgeClass` for configured values and `GENELIST_TYPE_METADATA` for
gene-list types. Status classes such as `badge-danger` and `badge-success` are
reserved for actual status or severity indicators. A domain value must not use a
status class merely to obtain its color. Generic decorative tones use explicit
color names such as `badge-tone-blue`.

About, Contact, knowledgebase details, the catalog matrix, cohort exploration,
tiered variant search and the dashboard use the `material-page` presentation scope.
`styles/page-materials.css` gives raised content cards very light accent gradients
and shared elevation tokens across routes, including outside that presentation scope.
Grouping panels and table frames retain their standard shared treatment.
Cards inherit their knowledgebase, panel
or static-section accent; semantic badge fills and tier colors remain intact.

Use the same treatment for the same component role across routes:

- Page headings and section panels group content; their elevation is separate from
  the raised cards inside them.
- Raised content and metric cards share `--content-card-border`,
  `--content-card-radius`, `--inner-card-background` and `--material-card-shadow`.
  Keep the border visible; do not combine transparent borders with a separate
  page-specific background that hides the border's underlying gradient.
- Assign accent variables for a meaningful resource type or section. Do not color
  a card because it happens to be the first child or appears in a particular route.
- `Badge` and `TableBadge` own their default elevation through
  `--material-badge-shadow`. Explicit compact clinical markers can opt out; do not
  restore their shadow with a page-level selector.
- Keep equivalent metric cards' padding and label/value typography aligned. Content
  length may differ; the card treatment should not.
The page heading retains the standard backdrop. Forced-colors mode removes the
decorative gradients and shadows.

Horizontal progress and prevalence bars share `progress-pipe` for the recessed
track and `progress-pipe-fill` for a rounded fill. Stacked bars use
`progress-pipe-segment` on each segment. Set each fill's existing color through a
background-color class or `backgroundColor`, so the shared cylindrical highlight
does not replace semantic colors or change the represented proportions.

Capability-ring tracks, their progress arcs and Recharts donut sectors share
`--chart-ring-depth` in `styles/charts.css`. Theme-specific highlight and shadow
tokens add elevation without changing the data colors, angles or values. Keep
the effect on the ring geometry; labels and legend markers remain unfiltered.
Forced-colors mode removes the decorative filter. Chart export inlines the
resolved `filter` alongside stroke and fill so standalone SVG and PNG exports
retain the chart's presentation.

The shared layout uses native scrolling at browser speed. `app-scroll-viewport`
marks the main and sidebar scroll surfaces; it does not intercept wheel or touch
input or add easing. Back-to-top jumps directly. Page-height controls update from
resize observation rather than measuring layout on each scroll event. The static
canvas decoration is paint-contained independently of scrolling content.

Views distinguish loading, empty, forbidden, disabled and failed states. Icon-only
controls have accessible names. Keyboard focus, disabled behavior and reduced-motion
support belong to shared component contracts. Clinical meaning must remain readable
without relying on color alone.

## Code and contract documentation

Python interfaces use type annotations and Google-style docstrings. Docstrings
describe behavior, parameter semantics, returned values and expected failures;
transaction boundaries or external side effects belong in `Notes:` when relevant.
FastAPI descriptions present client behavior and permissions before internal
dependency details.

TypeScript API and component types describe the values used by the UI. Persisted
document models, transport contracts and display models have separate ownership.
Generated references are produced from their source contracts:

```bash
PYTHONPATH=. .venv/bin/python scripts/docs/export_collection_contracts_doc.py
PYTHONPATH=. .venv/bin/python scripts/docs/export_permissions_reference.py
```

## Verification

Backend tests cover domain rules, application services, HTTP contracts and repository
behavior. Vitest covers frontend components and state; Playwright covers browser
workflows. Transaction tests require explicitly configured disposable MongoDB
replica sets. Skipped infrastructure tests do not establish transaction correctness.

Run commands from the repository root with the development dependencies installed:

```bash
# Backend tests and coverage
PYTHONPATH=. .venv/bin/python -m pytest -q tests/unit tests/api tests/integration \
  --cov=api --cov=coyote3 --cov-config=.coveragerc --cov-report=term-missing

# Python lint, formatting and configured type-check scope
PYTHONPATH=. .venv/bin/python -m ruff check src api tests scripts
PYTHONPATH=. .venv/bin/python -m ruff format --check src api tests scripts
PYTHONPATH=. .venv/bin/python -m mypy

# Frontend verification
npm --prefix frontend run lint
npm --prefix frontend run test:coverage
npm --prefix frontend run build
npm --prefix frontend run test:e2e

# Documentation verification
npm run docs:lint
.venv/bin/python scripts/docs/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict

# Combined repository checks
PYTHON_BIN=.venv/bin/python bash scripts/quality/run_quality_suite.sh
```

Mypy checks the modules configured in `pyproject.toml`, not the entire Python tree.
Coverage thresholds, clinical family gates and deployment checks are specified in
[Testing and quality](../testing/test-strategy-and-quality-gates.md). Optional
[Locust workloads](../testing/load-and-capacity-testing.md) run against an explicitly approved
synthetic deployment and do not replace browser or clinical acceptance testing.

## Reference index

| Subject | Reference |
| --- | --- |
| Application architecture | [Application context](../architecture/application-architecture.md) |
| Environment settings | [Configuration reference](../deployment/configuration-reference.md) |
| Collection fields | [Collection contracts](../reference/mongodb-collections.md) |
| Permissions | [Permission naming](../administration/permissions-and-access.md) and [Permission catalog](../administration/permission-catalog.md) |
| API compatibility | [API versioning and compatibility](../api/versioning-and-compatibility.md) |
| Deployment | [Center deployment](../deployment/bootstrap-data-flow.md) |
| Operational procedures | [Maintenance and quality](../operations/maintenance-and-verification.md) |
