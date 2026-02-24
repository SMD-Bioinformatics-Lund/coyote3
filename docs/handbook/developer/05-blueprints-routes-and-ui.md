# Blueprints, Routes, and UI Ownership

This chapter documents module ownership boundaries so new work is added in the correct layer.

## Ownership model

Each blueprint owns:

- route handlers (`views.py`)
- form definitions (where applicable)
- helper logic (`util.py`, `filters.py`, query builders)
- feature templates under blueprint template paths

## Home blueprint

Module:

- `coyote/blueprints/home`

Primary responsibilities:

- samples landing/worklist
- sample settings workspace
- report view/download routes
- effective gene helper routes used by settings UI

Key routes:

- `/samples...`
- `/samples/<sample_id>/edit`
- `/samples/<sample_id>/reports/<report_id>`
- `/samples/<sample_id>/effective-genes/all`

## DNA blueprint

Module:

- `coyote/blueprints/dna`

Primary responsibilities:

- DNA case list and filter workflow
- SNV/CNV/translocation detail actions
- variant classification and flags
- DNA report preview and save

Key routes:

- `/dna/sample/<sample_id>`
- `/dna/<sample_id>/var/<var_id>`
- `/dna/<sample_id>/multi_class`
- `/dna/sample/<sample_id>/preview_report`
- `/dna/sample/<sample_id>/report/save`

## RNA blueprint

Module:

- `coyote/blueprints/rna`

Primary responsibilities:

- RNA fusion list/detail workflows
- fusion flagging/classification actions
- RNA report preview and PDF render

Key routes:

- `/rna/sample/<id>K=`
- `/rna/fusion/<id>`
- `/rna/sample/preview_report/<id>`
- `/rna/sample/report/pdf/<id>`

## Common blueprint

Module:

- `coyote/blueprints/common`

Primary responsibilities:

- sample comment actions shared by DNA/RNA
- gene information pages
- tiered interpretation search views
- reported-variant history views

Key routes:

- `/sample/<sample_id>/sample_comment`
- `/search/tiered_variants`
- `/reported_variants/variant/<variant_id>/<tier>`

## Dashboard blueprint

Module:

- `coyote/blueprints/dashboard`

Primary responsibilities:

- aggregate operational statistics and dashboard rendering

## Admin blueprint

Module:

- `coyote/blueprints/admin`

Primary responsibilities:

- schema-driven governance CRUD
- users, roles, permissions
- ASP, ASPC, ISGL
- sample management and audit pages

## Template ownership

Global shared templates:

- `coyote/templates/layout.html`
- `coyote/templates/report_layout.html`
- `coyote/templates/error.html`

Feature templates should remain under the owning blueprint. Cross-blueprint template dependencies should be minimized.

## Access enforcement contract

Route handlers enforce access with decorators. Template-level hiding is not sufficient.

Required pattern for state-changing routes:

1. authentication requirement
2. permission requirement
3. sample-access requirement when sample-scoped

## Extension rules

1. Add route in the owning blueprint only.
2. Keep business logic in handlers/utilities, not templates.
3. Keep templates presentation-focused.
4. Reuse existing helper services before adding new cross-module utilities.
5. Update handbook chapter references when route ownership changes.
