# Major Endpoints (by Blueprint)

> This is a high‑level reference; see `coyote/blueprints/*/views.py` for full details.

## Admin (`/admin`)
- Users: create, edit, view, list — templates in `admin/templates/users/`
- Roles: create, edit, view, list — `admin/templates/roles/`
- Permissions: create, edit, list, view — `admin/templates/permissions/`
- Schemas: create/edit/manage — `admin/templates/schemas/`
- ASP (panels): manage/create/edit/print — `admin/templates/asp/`
- ASPC (assay configs): manage/create/edit/print — `admin/templates/aspc/`
- ISGL: manage/create/edit/view — `admin/templates/isgl/`
- Audit logs: `admin/templates/audit/audit.html`

## DNA (`/dna`)
- Variant lists, details, filters, report printing
- CNVs, translocations, biomarkers

## RNA (`/rna`)
- Fusions list & details, filtering

## Common
- Sample redirector based on assay (to DNA/RNA)
- Error pages (`coyote/templates/error.html`)

