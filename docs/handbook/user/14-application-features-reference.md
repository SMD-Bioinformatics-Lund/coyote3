# Application Features Reference

This chapter is a structured reference of major Coyote3 features and where they live in the app.

Use it as a “what can I do?” map.

Related:

- [Navigation and Page Map](./03-navigation-and-pages.md)
- [Complete Click Paths](./11-complete-click-paths.md)
- [Navbar Tools: Matrix, Catalog, and Variant Search](./13-navbar-matrix-catalog-and-variant-search.md)

## 1. Worklist and Case Access

Main routes:

- `/samples`
- `/samples/live`
- `/samples/done`

Capabilities:

- find samples by search
- switch live/done views
- open DNA and RNA workspaces
- jump to sample settings
- open saved reports

## 2. Sample Settings and Gene Scope Control

Main route:

- `/samples/<sample_id>/edit`

Capabilities:

- apply/remove ISGL lists
- add/clear ad hoc genes
- inspect effective genes
- inspect raw vs filtered variant stats

## 3. DNA Analysis Features

Main route:

- `/dna/sample/<sample_id>`

Capabilities:

- section-based variant review (SNV/CNV/translocation/biomarker depending on assay config)
- variant detail pages
- manual classification and comment actions
- report preview and save
- history links to reported occurrence context

## 4. RNA Analysis Features

Main route:

- `/rna/sample/<sample_id>K=`

Capabilities:

- fusion candidate review
- false-positive handling
- sample comments
- report preview and PDF export

## 5. Reporting and Historical Retrieval

Main routes:

- `/samples/<sample_id>/reports/<report_id>`
- `/samples/<sample_id>/reports/<report_id>/download`
- `/reported_variants/variant/<variant_id>/<tier>`

Capabilities:

- open/download saved report artifacts
- review report-linked historical variant snapshots

## 6. Navbar Discovery Features

Main routes:

- `MATRIX`: `/assay-catalog-matrix`
- `CATALOG`: `/assay-catalog`
- `VARIANT SEARCH`: `/search/tiered_variants`

Capabilities:

- matrix-based gene coverage discovery
- modality/category/list drill-down and CSV export
- cross-sample annotation/report search with mode/filter controls

Full guide:

- [Navbar Tools: Matrix, Catalog, and Variant Search](./13-navbar-matrix-catalog-and-variant-search.md)

## 7. Admin Governance Features (for authorized users)

Main routes:

- `/admin/users`
- `/admin/roles`
- `/admin/permissions`
- `/admin/schemas`
- `/admin/asp/manage`
- `/admin/aspc`
- `/admin/genelists`
- `/admin/audit`

Capabilities:

- user/role/access governance
- schema-driven config management
- assay panel and assay runtime configuration
- In Silico Gene List (ISGL) management
- audit review

Full guide:

- [Admin Creation Playbooks](./12-admin-creation-playbooks.md)
- [Administration and Governance](./07-admin-and-governance.md)

## 8. Docs and In-App Knowledge Features

Main routes:

- docs home: `/handbook/`
- user handbook: `/handbook/user`

Capabilities:

- keyword search across handbook pages
- grouped handbook links by track
- cross-linked chapter navigation
