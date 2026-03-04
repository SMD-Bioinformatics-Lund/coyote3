# Coyote3 API Endpoint Catalog

This catalog is an implementation-oriented inventory of API route families for maintainers. It complements `API_REFERENCE.md` by mapping endpoint domains to concrete route modules.

## 1. System and Health
- Module: `api/routes/system.py`
- Scope: health, version, and system-level diagnostics endpoints.
- Access: varies by endpoint; internal/security-sensitive paths should require explicit policy.

## 2. Home and Dashboard Domains
- Modules: `api/routes/home.py`, `api/routes/dashboard.py`
- Scope: dashboard summaries, home screen context, shared page bootstrap payloads.
- Access: authenticated users with minimum access constraints.

## 3. Sample Domain
- Module: `api/routes/samples.py`
- Scope: sample listing, detail context, and sample-centric retrieval endpoints.
- Access: route-level policy + sample assay ownership checks.

## 4. DNA Domain
- Module: `api/routes/dna.py`
- Example paths:
  - `GET /api/v1/dna/samples/{sample_id}/variants`
  - `GET /api/v1/dna/samples/{sample_id}/variants/{var_id}`
  - `GET /api/v1/dna/samples/{sample_id}/biomarkers`
  - `GET /api/v1/dna/samples/{sample_id}/plot_context`
- Scope: DNA variant context, detail views, mutation operations, and annotation enrichment flows.

## 5. RNA Domain
- Module: `api/routes/rna.py`
- Example paths:
  - `GET /api/v1/rna/samples/{sample_id}/fusions`
  - `GET /api/v1/rna/samples/{sample_id}/fusions/{fusion_id}`
  - bulk mutation routes for FP/irrelevant flags
- Scope: RNA fusion listing, fusion detail, workflow mutations.

## 6. Reporting Domain
- Module: `api/routes/reports.py`
- Example paths:
  - `GET /api/v1/dna/samples/{sample_id}/report/preview`
  - `GET /api/v1/rna/samples/{sample_id}/report/preview`
  - save endpoints receiving rendered HTML and snapshot payload
- Scope: report preview context and report persistence orchestration.

## 7. Coverage Domain
- Module: `api/routes/coverage.py`
- Scope: coverage and related quality metrics endpoints.

## 8. Admin Domain
- Module: `api/routes/admin.py`
- Scope: administrative configuration, policy objects, schema and role/permission management endpoints.
- Access: strict role/permission controls.

## 9. Public Domain
- Module: `api/routes/public.py`
- Scope: public catalog and non-sensitive data endpoints.
- Access: endpoint-specific, often reduced constraints compared to administrative domains.

## 10. Internal Domain
- Module: `api/routes/internal.py`
- Scope: internal-only endpoints for trusted system interactions.
- Access: internal token/header validation and restricted network posture.

## 11. Route Ownership Rules
1. Each endpoint must be declared in exactly one route module aligned with domain ownership.
2. Shared business behavior belongs in `api/core/*` modules, not duplicated across route modules.
3. Route modules should remain thin and deterministic: parse input, authorize, call core workflow, return contract-defined payload.
4. Every route decorator must declare an explicit `response_model` from `api/contracts/*` (or `response_model=None` only for non-body compatibility redirects).

## 12. Maintenance Checklist for Endpoint Changes
- Update route tests in `tests/api/routes/`.
- Update `API_REFERENCE.md` for contract changes.
- Update permission tests when route access requirements change.
- Update this catalog when endpoint families or ownership modules change.
