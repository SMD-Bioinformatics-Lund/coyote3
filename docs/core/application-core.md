# Coyote Core

Core operations provide the application workflows used by the API and workers.
A trusted host supplies authentication, current permissions, repositories and
integration capabilities. Operations enforce access and delegate to domain services.
External applications should use HTTP or [pyClient](README.md#coyote-pyclient).

## Installation and development

For a standalone host, follow [core installation](../../core/docs/getting-started.md)
and select [center configuration](../../core/docs/configuration.md#host-supplied-settings)
before importing profile-dependent contracts. Imports do not load deployment secrets
or connect to databases.

For application development, use the [editable uv workspace](uv-development.md).
Use [package installation](server-installation.md) for equivalent pip and wheel
instructions. The API host composes the runtime through
`coyote_api.app.application_factory`; package ownership is described in
[package boundaries](package-boundaries.md).

## Supported Python interface

Import application resources and result models from `coyote.application.operations`.
Import authored-content models from `coyote.application.operations.inputs`. Other modules
under `core/src/coyote/application/` and `core/src/coyote/domain/` implement use cases and clinical rules;
their methods and repository attributes are internal implementation details.

The installed distribution version identifies the Coyote Core release. Changes to
supported imports, arguments, results and errors follow the
[Coyote Core compatibility policy](compatibility.md). Application releases and HTTP
API majors have separate ownership; there is no extra interface-generation counter.

| Resource | Operations |
| --- | --- |
| `application.samples` | Sample search, navigation counts, references and reads. |
| Sample reference | Metadata, permitted fields, applied configuration, gene selection, comments, filters, tiering, classifications, annotations, report context, registered artifacts, coverage and biomarkers. |
| `sample.variants` | Review tables, individual findings, detail context, flags, comment visibility, CSV export, tiered selection, transcript selection, public evidence and blacklist curation. |
| `sample.cnvs`, `sample.translocations`, `sample.fusions` | Review tables, findings, detail context, flags, comment visibility and CSV export; structural transcript or RNA call selection where supported. |
| `application.coverage` | Coverage blacklist inspection, addition and removal. |
| `application.reports` | Library, preview, PDF preview, temporary `preview_bundle` rendering and save for DNA/RNA. Only save allocates a report number and persists snapshots. |
| `application.ingest` | Manifest authorization, upload preparation, synchronous sample/collection writes, durable asynchronous acceptance and submitter-scoped job status. |
| `application.query_rules` | Policy authoring, revision history, testing, scoped sample search, comparison previews and review/publication transitions. |
| `application.clinical_rules` | Rule-set authoring, facts, versions, revisions, testing, scoped sample previews and assigned review/publication transitions. |
| `application.configuration_profiles` | `list`, `create`, `publish` |
| `application.configuration_promotions` | `list`, `propose`, `approve` |
| `application.users`, `application.roles`, `application.permissions` | Account/access administration, form context, identity checks and lifecycle changes. Account assignment changes require their dedicated grants. |
| `application.assays`, `application.assay_groups`, `application.diagnoses` | Assay definitions, biological groups, shared diagnoses and assay associations. |
| `application.assay_configurations`, `application.gene_lists` | Configuration and gene-list authoring, inspection and lifecycle changes. |
| `application.editing` | Acquire, renew and release [document editing sessions](../administration/document-editing.md) before changing existing records. |
| `application.catalog_authoring` | Catalog workspace, revisions, previews, drafts, assignment, review and publication. |
| `application.sample_administration` | Privileged sample catalog, edit context, updates and deletion. |
| `application.reference_data` | Typed field and metadata reads for managed reference resources. |
| `application.knowledgebase` | Local evidence, source-specific context, aggregate statistics and scoped clinical cohorts. |
| `application.notifications` | Recipient inbox/read/dismiss operations and privileged broadcasts. |
| `application.dashboard`, `application.controls` | Scoped metrics, refresh requests, administrative insights, runtime overrides and maintenance submission. |
| `application.traceability`, `application.credentials` | Audit/schema inspection and audited fixed-audience ingestion credential issuance. |
| `application.account` | Current-user profile, interface preferences and local password replacement. |
| `application.internal_references` | Restricted role-level and gene-list identity metadata for ingestion tooling. |
| `application.public` | Anonymous published catalogs, public reference metadata, gene lookup, module availability and catalog exports. |
| `application.password_recovery` | Account-neutral reset requests and atomic one-time token consumption. |

Resource methods are explicit Python operations with typed arguments and docstrings.
There is no arbitrary service-method passthrough. Existing implementation services
remain internal; callers do not obtain their repositories or database collections.

## Deployment use

The trusted host initializes its configured runtime and obtains a session through
the existing authentication flow. The deployment composition entry point is
`coyote_api.app.application_factory.open_application`; credentials are not discovered by importing Coyote Core.

```python
from coyote_api.app.application_factory import open_application
from coyote.application.operations import AnalysisQuery, FlagChange

# session_token comes from the existing authenticated session, never a username or role list.
application = open_application(session_token, correlation_id="validation-run")
sample = application.samples.ref("SYNTHETIC_001")
metadata = sample.read()
selected = sample.variants.tiered_variants(
    AnalysisQuery(parameters={"intent": "somatic"})
)
sample.variants.set_flags(
    FlagChange(resource_ids=["synthetic-finding-id"], flag="interesting", value=True)
)
```

`ref()` stores an identifier and performs no database read. Every operation on
the reference reloads the session, current user, role grants and sample scope.
Reading a snapshot does not grant access to subsequent operations. Expired or
revoked sessions, inactive accounts, credential changes, required password changes
and changed permissions are checked again. A required password change permits
only the current-account password replacement operation. Supplied operation arguments cannot
set the authenticated actor, roles or assay scope.

The host's session repository, permission policy and repositories enforce those
checks. Coyote Core does not sandbox arbitrary Python with database credentials.
External notebooks and integrations use the remote client so credentials and
centralized access control remain on the server.

## Values and failures

`AnalysisQuery` carries explicit filters, search, sorting and pagination values.
Clinical services interpret them using the existing assay configuration and
query rules. `tiered_variants()` requests the complete existing selection;
pagination parameters do not truncate it. `FindingPage` contains findings and
pagination values without HTTP-specific form schemas or page context.

`SampleRecord` contains detached sample attributes. `FlagChange` and `TierChange`
validate supported states and tier values. Finding ownership is checked against
the authoritative sample before mutation; all selected targets are checked before
the first write. Production tier changes additionally require
`annotation:publish`. Publication and review operations retain their existing
revision, content-hash, assignment and distinct-reviewer requirements.

Annotations are immutable. `TierChange(apply=False)` is rejected; corrections
create new annotation records. Saved report references retain their original versions.

`SampleSearch` validates sample catalog selections. Existing authoring contexts
and administrative mutation results retain their structured dictionary contracts.
`CsvExport`, `Download` and `FileArtifact` describe exports and registered artifacts
without returning a FastAPI response. The HTTP adapter applies response headers,
streams registered files and shapes its existing response envelopes.

Report preview returns `ReportPreview`, including a fingerprint. Saving reloads
current inputs and rejects a stale fingerprint before allocating a number or
preparing artifact output. The existing reporting workflow persists artifacts,
finding snapshots and the configuration-resolution receipt. `SavedReport` carries
the resulting identity and artifact locations.

Operations raise the existing `AppError` with status, category and safe details;
HTTP exception handling translates the same error. Authored-content validation
retains existing Pydantic errors. Repository and integration failures propagate;
Coyote Core does not retry mutations or introduce an outer transaction. Multiple flag
writes retain their individual service transaction boundaries.

## Host composition and workers

`CoyoteApplication(ApplicationRuntime(...), ApplicationServices(...))` accepts
trusted host capabilities. This supports synthetic repositories and deterministic
validation without FastAPI or MongoDB. Importing the public interface, including
input models, does not load server wiring, database drivers or task runtimes.
Services remain lazy until the corresponding operation is authorized.

`ApplicationRuntime` binds the verified actor and correlation identity to the
existing execution context and restores any surrounding context on success or
failure. Its access-audit callback runs before service work. The deployment's
session composition requires accepted audit persistence before proceeding.
Business mutation audit and transactional outboxes remain owned by the existing
services and repositories; an access event is not a mutation-completion receipt.

Clinical, authoring, administrative, knowledgebase, notification and operational
HTTP workflows call Coyote Core. Permission and sample-scope checks use the
framework-independent functions in `core/src/coyote/application/common/access.py`. Routes
declare HTTP access requirements as an additional transport check; Coyote Core operations
enforce their requirements for every caller. No business workflow depends on a
router first setting the actor or checking a permission.

Authentication-provider negotiation, session cookies, CSRF, multipart decoding,
upload staging/cleanup, HTTP streaming and health/metrics responses belong to
transport and infrastructure. Password policy and account/recovery workflows
belong to domain/application operations. Operational task submission uses injected
ports; Coyote Core modules do not import Celery tasks.

Anonymous reads use `PublicApplication`, composed by
`coyote_api.app.application_factory.open_public_application`. This capability cannot access clinical
records or mutate resources. One-time recovery has a separate restricted
`PasswordRecovery` capability. Pipeline credentials are reverified for each call
and restricted to synchronous sample ingestion. Static internal metadata access
has its own two-operation audience. Neither credential constructs an unrestricted
authenticated application.

Maintenance workers use `MaintenanceExecution` for retention, committed artifact
recovery, audit/activity delivery, leased email delivery, reference refresh and
metric refresh. The task adapter retains scheduling gates and cross-process locks;
Coyote Core loads current active account scopes and deduplicates equivalent refreshes.
The fixed maintenance identity cannot invoke interactive clinical or account operations.
Its operational access log does not make audit recovery depend on a healthy audit queue.

The ingestion worker uses `IngestJobExecution`, composed by
`coyote_api.app.application_factory.ingest_job_executor`. It authenticates as `celery-ingest` with only
`internal.ingest:manage`; that capability cannot read clinical samples or administer
accounts. The durable job's original submitter remains ingestion attribution.
The completion callback remains inside the existing ingest transaction, preserving
lease fencing and duplicate-delivery behavior. Operational worker access events
use the worker's existing audit delivery policy; committed mutation traceability
continues through its existing transaction/outbox path.

Coyote Core requires host-supplied storage, identity and integration
capabilities. Installing the library does not provide database credentials or an
authenticated application instance. Its release version is independent of the
application release. The remote client has its own distribution and version.
