# Admin and Governance (User Perspective)

This chapter explains what each admin area controls and how those settings affect daily users.

## Admin entry point

- `/admin/`

## What each admin section controls

## Users (`/admin/users`)

Controls:

- who can log in
- assay and environment scope
- explicit allow/deny permissions
- active/inactive state

Impact on analysts:

- visible samples are constrained by assigned assays/environments
- route access changes immediately after permission updates

## Roles (`/admin/roles`)

Controls:

- permission bundles
- role levels and labels

Impact on analysts:

- baseline access to workflow pages and actions

## Permissions (`/admin/permissions`)

Controls:

- fine-grained route/action permissions

Impact on analysts:

- determines whether actions like classify, hide comments, or create reports are available

## Schemas (`/admin/schemas`)

Controls:

- dynamic form definitions for managed entities

Impact on operations:

- incorrect schema edits can break admin create/edit forms

## ASP: assay specific panels (`/admin/asp/manage`)

Controls:

- panel metadata
- covered genes and germline genes
- assay family/category descriptors

Impact on interpretation:

- effective gene baseline for sample analysis

## ASPC: assay specific configs (`/admin/aspc`)

Controls:

- filter defaults
- analysis/report sections
- report headers/paths
- CNV thresholds and other assay behavior

Impact on interpretation:

- what appears on DNA/RNA pages
- report content and structure

## ISGL: in-silico gene lists (`/admin/genelists`)

Controls:

- curated gene lists with assay/assay-group linkage

Impact on interpretation:

- selectable gene filters on sample settings
- effective gene set used during review/reporting

## Samples management (`/admin/manage-samples`)

Controls:

- sample-level admin edit/delete flows

Impact on analysts:

- sample metadata/state corrections

## Audit (`/admin/audit`)

Purpose:

- operational trace of user/admin actions

## Governance best practices

1. Change one config domain at a time (roles, permissions, ASP, ASPC, ISGL).
2. Validate with a smoke sample after every change.
3. Prefer role-based permission design; keep per-user overrides minimal.
4. Keep config history and rollback intent documented.
