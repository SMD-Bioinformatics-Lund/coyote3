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
./scripts/compose-with-version.sh \
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
| `api/application/` | Clinical and administrative workflows coordinating domain rules, repositories and integrations. |
| `api/domain/` | Domain rules, identity logic, query policies and repository protocols. |
| `api/contracts/` | Request, response, collection and managed-resource contracts. |
| `api/infra/` | MongoDB persistence, cache, integrations, notifications and observability. |
| `api/security/` | Authentication, authorization and password workflows. |
| `api/config/` | Runtime settings, center configuration, software constants and bootstrap catalogs. |
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
| Contacts, clinical vocabulary and query policy | Supported files under `api/config/center/`. |
| Assay groups, subpanel definitions and assay associations | MongoDB registries. |
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

Collection models are registered in `api/contracts/schemas/registry.py`.
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
`api/application/common/assay_config.py`. When `current_aspc_id` is present,
normal resolution uses that exact revision. Active configuration lookup applies
to ingestion, unassigned samples and explicit configuration updates. Saved report
snapshots are not reconstructed from the current active configuration.

### Index administration

Repositories declare their index contracts. API startup inspects those contracts
and logs missing or conflicting indexes without creating, replacing or dropping them.
Index changes are explicit maintenance operations:

```bash
PYTHONPATH=. .venv/bin/python scripts/manage_mongo_indexes.py status
PYTHONPATH=. .venv/bin/python scripts/manage_mongo_indexes.py plan
```

With the target database configured and the plan reviewed, `apply` creates missing
compatible indexes. It does not drop conflicting indexes:

```bash
PYTHONPATH=. .venv/bin/python scripts/manage_mongo_indexes.py apply
```

## Clinical configuration

| Resource | Purpose |
| --- | --- |
| Assay group | Clinical grouping and availability of associated assays. |
| Assay (ASP) | Assay identity, sequencing attributes, physical gene coverage and input-file policy. |
| Subpanel | Shared interpretation scope associated with one or more assays. Availability can be controlled per association. |
| Assay configuration (ASPC) | Assay, subpanel and environment-specific analyses, filter profiles and reporting settings. |
| Gene list (ISGL) | Named gene selection offered to the analysis types declared by `list_type`. |

`base` is the default interpretation scope when no named subpanel is selected.
Named subpanel choices come from the selected assay's associations.

Filter profiles separate analysis intent and finding type. An SNV gene-list
selection does not implicitly restrict CNVs or fusions. Selected lists and
ad-hoc genes are resolved against the assay's coverage policy; without a selected
restriction, assay coverage applies. An empty broad-assay scope can mean no gene
predicate, whereas a selected list with no overlap must remain restrictive.

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
[Sample input files](../reference/sample-file-formats.md) and [Sample YAML](../reference/sample-manifest.md).

## Reporting

![Reporting workflow](../assets/diagrams/report-generation-flow.svg)

Clinical rule sets are stored in MongoDB and follow the authoring, review and
publication workflow. Publishing approved rule content does not require a new
application build.

`api/application/reporting/clinical_rules/resolution.py` selects an active published
release using the assay, sample subpanel, analyte and reporting language. An exact
subpanel release takes precedence; assay Base is used only when no exact release
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

Roles bundle permissions. API access checks combine the required permission with
applicable assay and environment scope. Frontend visibility is not an authorization
decision. Bootstrap permissions and roles are installed from
`api/config/bootstrap/rbac/`; MongoDB holds runtime assignments.

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
cell, action, or table layout, edit `assays/AssaysPage.tsx`. Assay subpanel
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

Pages own route parameters, queries, mutations, and top-level composition.
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
PYTHONPATH=. .venv/bin/python scripts/export_collection_contracts_doc.py
PYTHONPATH=. .venv/bin/python scripts/export_permissions_reference.py
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
  --cov=api --cov-config=.coveragerc --cov-report=term-missing

# Python lint, formatting and configured type-check scope
PYTHONPATH=. .venv/bin/python -m ruff check api tests scripts
PYTHONPATH=. .venv/bin/python -m ruff format --check api tests scripts
PYTHONPATH=. .venv/bin/python -m mypy

# Frontend verification
npm --prefix frontend run lint
npm --prefix frontend run test:coverage
npm --prefix frontend run build
npm --prefix frontend run test:e2e

# Documentation verification
npm run docs:lint
.venv/bin/python scripts/check_markdown_links.py
.venv/bin/python -m mkdocs build --strict

# Combined repository checks
PYTHON_BIN=.venv/bin/python bash scripts/run_quality_suite.sh
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
