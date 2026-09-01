# API Organization

Coyote3 keeps endpoint paths stable under `/api/v1`, but the public API
documentation is grouped by clinical and operational responsibility. This keeps
Swagger usable for reviewers, developers, and automation authors without
coupling the documentation to Python file names.

## Public Route Prefix

All browser-facing API URLs are mounted below the configured `SCRIPT_NAME`.
For example, with `SCRIPT_NAME=/coyote3_dev`, Swagger is available at:

```text
https://localhost/coyote3_dev/api/v1/docs
```

Inside the API service, route handlers still use `/api/v1/...`. Reverse proxies
and FastAPI `root_path` expose those routes under the public prefix.

## API Groups

| Group | Responsibility |
| --- | --- |
| Authentication | Session creation, logout, current-user context, and password workflows. |
| Dashboard | Operational, workload, assay, and review summary metrics. |
| Clinical Samples | Sample lists, sample context, comments, file/QC metadata, BAM-service file lookup, and sample-level settings. |
| DNA Small Variants | SNV and small indel review, filtering, exports, actions, comments, and knowledgebase lookups. |
| DNA Copy Number | CNV lists, detail contexts, and CNV-specific clinical actions. |
| RNA Fusions | RNA fusion findings, selected-call state, comments, and exports. |
| Structural Variants | DNA translocations and structural breakpoint review. |
| Coverage | Coverage plots, gene/exon/probe views, and coverage blacklist management. |
| Biomarkers | Sample biomarker summaries and molecular context payloads. |
| Reporting | Report preview, snapshot, save, HTML/PDF artifact, and report context endpoints. |
| Knowledgebases & Annotations | Gene information, tiered variant search, annotations, external knowledgebase adapters, and variant evidence. |
| Public Catalog | Unauthenticated public catalog, matrix, gene, assay reference, and center contact endpoints. |
| Admin: Operations | Audit events, schema diagnostics, runtime controls, retention maintenance, and explicit public-reference refresh operations. |
| Admin: Assays & Gene Lists | ASP, ASPC, ISGL, and admin sample resource configuration. |
| Admin: Users | User-account management, invites, provider state, and profile metadata. |
| Admin: Roles & Permissions | Role and permission policy management. |

> **Info: Stable URLs, clearer documentation**
>
>
> The grouping changes how endpoints are presented in Swagger. It does not
> change endpoint URLs, request bodies, response contracts, or permission
> checks.
>

## OpenAPI Visibility Policy

OpenAPI describes the supported client contract. It is not the security
boundary for the service. Supported authentication, clinical, reporting,
knowledgebase, public-catalog, dashboard, notification, and administrative
routes remain visible in Swagger, ReDoc, and generated clients. Protected
operations declare cookie and bearer authentication and document `401` and
`403` responses.

Runtime plumbing is intentionally excluded from the generated schema:

```text
/api/v1/health
/api/v1/internal/*
```

These routes remain registered and callable. Health probes continue to serve
Docker, reverse proxies, and monitoring systems. Internal metadata, ingest,
task-status, and metrics routes retain their existing user-permission or
internal-token checks. Hiding them from OpenAPI neither grants access nor
replaces authentication, authorization, proxy policy, or auditing.

Router visibility is declared once in `api/interfaces/http/registry.py`.
Adding a new service-integration router requires an explicit schema-visibility
decision there, which prevents internal endpoints from becoming supported
client contracts accidentally.

## Router Ownership

The HTTP layer lives in domain-oriented packages under `api/interfaces/http`:

```text
api/interfaces/http/
  admin/          # governance, managed resources, users, roles, permissions
  clinical/
    samples.py    # sample lists, sample context, sample comments, settings
    common/       # shared clinical route helpers
    dna/          # DNA findings, coverage, biomarkers, classifications
    rna/          # RNA findings
    reporting/    # report preview, save, and artifacts
  knowledgebase/  # shared gene/search/annotation endpoints
  operations/     # health, dashboard, controls, internal ingest/maintenance
  public/         # unauthenticated catalog and reference endpoints
```

Route modules should stay thin:

1. Declare the URL, method, response model, and required permission.
2. Resolve the authenticated user with `require_access`.
3. Delegate workflow behavior to `api/application`.
4. Return contract-shaped Pydantic-compatible payloads.

Clinical rules, filtering logic, report construction, and knowledgebase
normalization should not live in route handlers. They belong in the domain or
application layer where they can be tested without HTTP machinery.

### Clinical Route Subcategories

Clinical routes are grouped by the biological workflow that owns the data.

| Package | Owns | Examples |
| --- | --- | --- |
| `clinical.samples` | Sample list, sample detail context, file/QC metadata, BAM-service file lookup, sample comments, and sample-level filter settings. | `/api/v1/samples`, `/api/v1/samples/{sample_id}`, `/api/v1/samples/{sample_name}/bam-files` |
| `clinical.dna.small_variants` | SNVs and small indels. | `/api/v1/samples/{sample_id}/small-variants`, `/api/v1/samples/{sample_id}/small-variants/exports/snvs/context` |
| `clinical.dna.cnvs` | Copy-number variants. | `/api/v1/samples/{sample_id}/cnvs`, `/api/v1/samples/{sample_id}/cnvs/exports/context` |
| `clinical.dna.translocations` | DNA translocations and breakpoints. | `/api/v1/samples/{sample_id}/translocations`, `/api/v1/samples/{sample_id}/translocations/exports/context` |
| `clinical.dna.coverage` | Coverage summaries, gene views, exon/probe tracks, and coverage blacklist operations. | `/api/v1/samples/{sample_id}/coverage` |
| `clinical.dna.biomarkers` | Sample biomarker context. | `/api/v1/samples/{sample_id}/biomarkers` |
| `clinical.dna.classifications` | Tiering and classification state shared by DNA findings. | `/api/v1/samples/{sample_id}/classifications` |
| `clinical.rna.fusions` | RNA fusion finding review. | `/api/v1/samples/{sample_id}/fusions` |
| `clinical.reporting.reports` | Access-scoped saved-report library plus sample-owned preview, save, HTML, and PDF artifacts. | `/api/v1/reports`, `/api/v1/samples/{sample_id}/reports` |

> **Info: Export route ownership**
>
>
> Export endpoints live under the finding type they export. CNV export
> context belongs under `/cnvs`, translocation export context belongs under
> `/translocations`, and SNV/small-indel export context belongs under
> `/small-variants`. This keeps permissions, Swagger groups, and UI actions
> aligned with the clinical workflow.
>

> **Info: Stable path contract**
>
>
> Python module paths can change as code ownership improves. Browser URLs,
> API client paths, response contracts, and permission names are the stable
> contract.
>

## UI Route Contracts

The React application has a route registry in
`frontend/src/lib/routes/ui-route-registry.ts`. Each route declares:

- its browser path and page name
- the functional area it belongs to
- API dependencies used by the page
- the data expected by the UI
- empty and error-state expectations

Backend tests validate that concrete API dependencies named in this registry
exist in FastAPI. This makes route review explicit: when a page starts using a
new endpoint, the registry and route test must move together.

## Knowledgebase Endpoints

The `Knowledgebases & Annotations` OpenAPI group contains endpoints for
cross-cutting reference data that is reused by clinical pages rather than owned
by one finding type.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/v1/common/gene/{gene_id}/info` | HGNC-normalized gene information with the compact knowledgebase signal needed by existing UI components. |
| `GET /api/v1/common/reported_variants/variant/{variant_id}/{tier}` | Reported-variant context for one tiered finding. |
| `GET /api/v1/common/search/tiered_variants` | Cross-sample search over tiered annotations and reported variants. |
| `GET /api/v1/knowledgebases/gene/{gene_id}` | Aggregated gene context across configured external/local knowledgebases. |
| `GET /api/v1/knowledgebases/oncokb/gene/{gene_id}` | OncoKB gene context from public cache and historical local actionability data. |
| `GET /api/v1/knowledgebases/clinpgx/gene/{gene_id}` | ClinPGx public gene marker context from the local cache. |
| `GET /api/v1/knowledgebases/civic/gene/{gene_id}` | CIViC gene-level context from the local knowledgebase collection. |
| `GET /api/v1/knowledgebases/brca-exchange/gene/{gene_id}` | BRCA Exchange applicability for a gene. |
| `GET /api/v1/knowledgebases/iarc-tp53/gene/{gene_id}` | IARC TP53 applicability for a gene. |
| `GET /api/v1/knowledgebases/variant/evidence` | Variant-level local evidence from CIViC, historical OncoKB, BRCA Exchange, and IARC TP53. |
| `GET /api/v1/knowledgebases/civic/variant/evidence` | CIViC variant evidence for one genomic variant identity. |
| `GET /api/v1/knowledgebases/brca-exchange/variant/evidence` | BRCA Exchange evidence for one genomic variant identity. |
| `GET /api/v1/knowledgebases/iarc-tp53/variant/evidence` | IARC TP53 evidence for one genomic variant identity. |

## Sample-Scoped BAM-Service Lookup

`GET /api/v1/samples/{sample_name}/bam-files` returns BAM paths registered for
the resolved sample's case and control IDs. The path uses the sample name because
this is a sample workflow, not a standalone knowledgebase query.

> **Info: Gene and variant sources**
>
>
> Gene-level endpoints use HGNC normalization first, including previous
> symbols and aliases where the HGNC repository supports them. Variant-level
> evidence requires explicit genomic coordinates and selected transcript
> notation because BRCA Exchange, IARC TP53, CIViC, and historical OncoKB
> records are variant-specific.
>

> **Warning: BAM-service endpoint**
>
>
> `GET /api/v1/samples/{sample_name}/bam-files` returns paths registered by
> the connected BAM-service database. It does not read BAM content and does
> not verify that every returned path is currently mounted on the API host.
>

## Adding A New Endpoint

When adding a route:

1. Select one tag from `api/interfaces/http/tags.py`.
2. Add or reuse a Pydantic response contract in `api/contracts`.
3. Declare the permission with `require_access(permission="resource:action")`
   unless the endpoint is explicitly public.
4. Add route tests for authorization, empty state, and representative payloads.
5. Run the OpenAPI tag guardrail test.

> **Warning: Avoid ad-hoc groups**
>
>
> Do not use file-level tags such as `resource-aspc`, `admin-users`, or
> `internal` in new routers. The OpenAPI schema is a user-facing API map, not
> a mirror of the Python module tree.
