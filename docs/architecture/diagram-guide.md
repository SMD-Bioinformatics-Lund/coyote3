# Architecture and workflow diagrams

Use these diagrams to trace resource dependencies, service boundaries, and clinical
workflows. Open an SVG to inspect it at full size. Each image has a title and text
description and renders directly in GitHub and the documentation site.

## Resource and service maps

| Diagram | Explains | Detailed reference |
| --- | --- | --- |
| [Clinical resources](../assets/diagrams/collection-relationships.svg) | ASP, ASPC, optional ISGLs, samples, findings, review state, and saved reports. | [Resource relationships](resource-relationships.md) |
| [Assay configuration](../assets/diagrams/assay-configuration-relationships.svg) | Groups, shared subpanels, assay associations, setup approval, and catalog publication. | [Assay setup](../administration/assay-setup.md) |
| [Identity and access](../assets/diagrams/identity-access-relationships.svg) | Users, roles, permissions, sessions, user scope, audit, and notifications. | [Security model](security-model.md) |
| [Database resource map](../assets/diagrams/database-resource-map.svg) | All configured collection families across primary, identity, knowledgebase, and BAM services. | [MongoDB topology](mongodb-topology.md) |
| [Runtime topology](../assets/diagrams/runtime-topology.svg) | Proxy, frontend, API, workers, Redis, storage, and integrations. | [Application architecture](application-architecture.md) |

## Workflow diagrams

### Diagnosis, change planning, and recovery

| Diagram | Question answered | Guide |
| --- | --- | --- |
| [Sample readiness](../assets/diagrams/sample-readiness-checks.svg) | Is the problem visibility, completion, analysis availability, filters, or reporting state? | [Sample readiness and missing results](../user-guide/sample-readiness-and-missing-results.md) |
| [Configuration change planning](../assets/diagrams/configuration-change-planning.svg) | What should be checked before and after a governed configuration change? | [Planning configuration changes](../administration/planning-configuration-changes.md) |
| [Ingest job recovery](../assets/diagrams/ingest-job-recovery.svg) | What do durable job states mean, and where do retries or acknowledgements fit? | [Ingest job recovery](../operations/ingest-job-recovery.md) |
| [Recovery dependencies](../assets/diagrams/recovery-data-dependencies.svg) | Which records, files, and deployment settings must be covered together? | [Backup and recovery](../operations/backup-and-recovery.md) |

### Configuration and access details

| Diagram | Question answered | Guide |
| --- | --- | --- |
| [Resource setup order](../assets/diagrams/resource-setup-order.svg) | What must be defined before configurations can be activated and samples ingested? | [Assay setup](../administration/assay-setup.md) |
| [Assay and subpanel cardinality](../assets/diagrams/assay-subpanel-cardinality.svg) | What is shared between assays, and what needs its own association or ASPC? | [Assay subpanels](../administration/assay-subpanels.md) |
| [Gene-list types and selection](../assets/diagrams/gene-list-types-and-selection.svg) | How do eligibility, list types, selected IDs, and assay coverage combine? | [Assay filtering](../reference/assay-filtering.md) |
| [Sample configuration resolution](../assets/diagrams/sample-configuration-resolution.svg) | How do ASPCs, persisted sample filters, data availability, and review fit together? | [Resource relationships](resource-relationships.md) |
| [User and assay access scope](../assets/diagrams/user-assay-access-scope.svg) | How do users, roles, permissions, groups, assays, and sample scope affect access? | [Permissions and access](../administration/permissions-and-access.md) |
| [Resource change impact](../assets/diagrams/resource-change-impact.svg) | Which operations do configuration changes affect, and which historical records remain intact? | [Resource relationships](resource-relationships.md) |

### Runtime and clinical workflows

| Focused flow | Explains |
| --- | --- |
| [End-to-end clinical flow](../assets/diagrams/end-to-end-clinical-flow.svg) | Configuration, bundle submission, atomic ingest, review, saved reports, and cohort use. |
| [Collection binding](../assets/diagrams/collection-binding-flow.svg) | Center mapping through adapters, repositories, services, and entry points. |
| [Sample evidence ownership](../assets/diagrams/sample-evidence-ownership.svg) | The sample anchor, dependent DNA/RNA records, and review/report references. |
| [Update ingest](../assets/diagrams/sample-update-ingest-flow.svg) | Existing identity, validation, filter authority, replacement evidence, and atomic commit. |
| [Filter authority](../assets/diagrams/sample-filter-authority.svg) | Missing filters, persisted filters, and explicit reset. |
| [SNV intent routing](../assets/diagrams/snv-intent-filter-routing.svg) | Independent somatic and germline filter and reporting contexts. |
| [Clinical rule lifecycle](../assets/diagrams/clinical-rule-release-lifecycle.svg) | Draft, submission, review, approval, publication, rejection, and retirement. |
| [Report artifacts](../assets/diagrams/report-artifact-rendering.svg) | Workflow context rendered to HTML and PDF. |
| [Local password lifecycle](../assets/diagrams/local-password-lifecycle.svg) | Invitation, SMTP failure, neutral recovery responses, and one-time links. |
| [Test coverage map](../assets/diagrams/test-coverage-map.svg) | Complementary unit, API, integration, browser, and quality checks. |
| [OncoKB evidence](../assets/diagrams/oncokb-local-evidence-flow.svg) | Public refresh, HGNC resolution, local evidence, and variant markers. |
| [ClinPGx evidence](../assets/diagrams/clinpgx-evidence-flow.svg) | Local gene badges and explicitly requested current public context. |

| Diagram | Explains |
| --- | --- |
| [Bootstrap data](../assets/diagrams/bootstrap-data-flow.svg) | Bundled data validation and collection occupancy checks. |
| [Ingestion](../assets/diagrams/celery-ingest-flow.svg) | Durable jobs, configuration resolution, transactional persistence, and failure handling. |
| [Clinical review](../assets/diagrams/clinical-review-flow.svg) | Filters, interpretation, preview, and saved evidence. |
| [Sample analysis](../assets/diagrams/sample-analysis-resolution.svg) | Configured analyses, gene scope, query policy, and client refresh. |
| [Transcript selection](../assets/diagrams/transcript-selection-flow.svg) | Application-owned transcript priority and within-stage consequence tie-breaking. |
| [Report generation](../assets/diagrams/report-generation-flow.svg) | Typed facts, published rules, preview, confirmation, and stable outputs. |
| [Configuration authority](../assets/diagrams/configuration-authority.svg) | Deployment settings, application catalogs, clinical resources, and sample state. |
| [Resource updates](../assets/diagrams/configuration-resource-update.svg) | Permissions, validation, version changes, and preserved report provenance. |
| [Login](../assets/diagrams/login-provider-resolution.svg) | Local/LDAP selection, account verification, and session creation. |
| [Access decision](../assets/diagrams/rbac-access-decision.svg) | Active permissions, role assignment, user scope, and allow/deny decisions. |
| [Request lifecycle](../assets/diagrams/request-lifecycle.svg) | Browser request through policy, services, persistence, and response. |
| [URL routing](../assets/diagrams/url-request-flow.svg) | Frontend route, API request, data access, and rendering. |
| [Dashboard metrics](../assets/diagrams/dashboard-metric-path.svg) | Independent metric queries, cache state, and background refresh. |
| [Feature delivery](../assets/diagrams/feature-delivery.svg) | Implementation, contract, clinical, and release validation gates. |

## Reading and maintaining the diagrams

Resource-map arrows label dependencies or data contributions; they do not declare
SQL foreign keys or imply a transaction across different MongoDB services. Dashed
arrows identify optional selection or integrations. Workflow arrows show execution
order. Read the linked guide for fallback, failure, and permission conditions.

The editable sources are the SVG files in `docs/assets/diagrams/`. Use descriptive
hyphenated names, native text labels, an SVG `viewBox`, and accessible `title` and
`desc` elements. Keep labels outside connectors and preserve a readable full-size
view. Update the relevant diagram when changing its resource contract or workflow.

Verify relationships against collection contracts, repository references, and
application services. Check both GitHub-compatible rendering and the MkDocs page;
diagrams supplement the written contracts rather than replacing them.
