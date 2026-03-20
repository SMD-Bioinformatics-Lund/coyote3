# UI Map And User Flows

Detailed capability inventory:

- See `Product -> UI Functionality Matrix` for page-by-page actions users can perform.

## UI surface overview

Flask blueprints define the UI domains under `coyote/blueprints/`:

- `home`: landing, sample list, report retrieval
- `dna`: small variants, CNVs, translocations, DNA reports
- `rna`: fusion views and RNA reports
- `coverage`: coverage pages
- `admin`: users, roles, permissions, schemas, assay configs, audit
- `public`: public/catalog views
- `userprofile`: current-user profile pages

Help surface:

- Primary user Help: `HELP_CENTER_URL` (standalone docs container)
- UI links do not serve docs internally; they open the standalone docs endpoint

## Typical user journey (DNA case)

1. Login
2. Open sample from home list
3. Review small variants
4. Apply actions/classification/comments
5. Review structural findings (CNV/translocation)
6. Generate or open report

Main backend API route families involved:

- `/api/v1/samples`
- `/api/v1/variants`
- `/api/v1/cnvs`
- `/api/v1/translocations`
- `/api/v1/reports`

## Typical user journey (RNA case)

1. Open RNA sample
2. Review fusions
3. Adjust fusion filters
4. Generate or open RNA report

Main API families:

- `/api/v1/fusions`
- `/api/v1/samples`
- `/api/v1/reports`

## Admin journey

1. Open admin home
2. Manage users / roles / permissions
3. Update schemas and assay configs
4. Audit operational logs

Main API families:

- `/api/v1/users`
- `/api/v1/roles`
- `/api/v1/permissions`
- `/api/v1/internal`

## UI behavior notes

- UI is server-rendered with Jinja templates.
- Most data operations are API-backed and permission-gated.
- User-visible failures should map to API error payloads with actionable summaries.
