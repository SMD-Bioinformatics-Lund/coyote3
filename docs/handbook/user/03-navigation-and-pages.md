# Navigation and Pages

This chapter defines the primary navigation model of Coyote3 and explains what each major page is responsible for.

## Navigation model

Coyote3 is organized around a single operational spine:

1. Start in Samples.
2. Open a case into DNA or RNA workflow.
3. Review, classify, and comment.
4. Preview and save report artifacts.
5. Re-open from reported history when needed.

## Main entry points

- Samples worklist: `/samples`
- Dashboard: `/dashboard/`
- Administration: `/admin/`
- Public information pages: `/public/...`
- In-app handbook index: `/handbook/`

## Samples worklist

Supported routes:

- `/samples`
- `/samples/live`
- `/samples/done`
- `/samples/<panel_type>/<panel_tech>/<assay_group>`
- `/samples/<panel_type>/<panel_tech>/<assay_group>/<status>`

Primary user actions:

- Search by sample name.
- Switch between live and done scopes.
- Open sample settings.
- Open DNA or RNA case workspace.
- Open report links for previously reported cases.

## Live and done semantics

The worklist state is driven by `samples.report_num`.

- Live: `report_num` missing or `0`.
- Done/reported: `report_num > 0`.

Operational effect:

- A case remains live until report save is successful.
- After successful save, report metadata is written and the case appears in done/reported scope.

## Opening a case

From `/samples`:

- DNA case route: `/dna/sample/<sample_id>`
- RNA case route: `/rna/sample/<sample_id>K=`

`sample_id` accepts the sample name used by the worklist.

## Sample settings workspace

Route:

- `/samples/<sample_id>/edit`

Purpose:

- Manage ISGL selection for the case.
- Manage ad-hoc case genes.
- Verify effective genes.
- Compare raw versus filtered variant statistics.

Supporting route handlers used by the page:

- `GET /samples/<sample_id>/isgls`
- `POST /samples/<sample_id>/genes/apply-isgl`
- `POST /samples/<sample_id>/adhoc_genes`
- `POST /samples/<sample_id>/adhoc_genes/clear`
- `GET /samples/<sample_id>/effective-genes/all`

## DNA workspace

Primary route:

- `/dna/sample/<sample_id>`

Navigation from DNA list:

- SNV detail: `/dna/<sample_id>/var/<var_id>`
- CNV detail: `/dna/<sample_id>/cnv/<cnv_id>`
- Translocation detail: `/dna/<sample_id>/transloc/<transloc_id>`
- Report preview: `/dna/sample/<sample_id>/preview_report`
- Report save: `/dna/sample/<sample_id>/report/save`

## RNA workspace

Primary route:

- `/rna/sample/<sample_id>K=`

Navigation from RNA list:

- Fusion detail: `/rna/fusion/<fusion_id>`
- Fusion false-positive flag/unflag routes
- Report preview: `/rna/sample/preview_report/<sample_id>`
- PDF generation: `/rna/sample/report/pdf/<sample_id>`

## Report retrieval

Saved reports are opened through sample-scoped routes:

- View: `/samples/<sample_id>/reports/<report_id>`
- Download: `/samples/<sample_id>/reports/<report_id>/download`

If `filepath` is absent in report metadata, the app reconstructs path from configured report base and assay report folder.

## Search and historical review

Interpretation history routes:

- Tiered search: `/search/tiered_variants`
- Reported occurrence view: `/reported_variants/variant/<variant_id>/<tier>`

These routes are designed for cross-sample context and report-time traceability.

## Administration navigation

Administration root:

- `/admin/`

Managed domains:

- sample management
- users
- roles
- permissions
- schemas
- ASP (assay panel definitions)
- ASPC (assay runtime/report configs)
- ISGL (in-silico gene lists)
- audit log views

Administration pages govern system behavior; they are not part of day-to-day interpretation workflow.
