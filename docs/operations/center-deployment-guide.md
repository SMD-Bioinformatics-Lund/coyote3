# Center Deployment Guide

This page is the entry point for first-time center deployment.
Use it as a quick map; use the linked checklist for full command-by-command execution.

## Deployment Flow

1. Prepare environment and secrets.
2. Start the stack.
3. Bootstrap the first admin user.
4. Seed baseline collections in strict order.
5. Validate and ingest the demo sample.
6. Verify UI/API and admin flows.

## Authoritative Procedure

For the full, detailed procedure, use:

- [Initial Deployment Checklist](initial-deployment-checklist.md)

That checklist is the single source of truth for:

- exact commands and command order
- required collection order
- seed-source policy (`--seed-file` and `--reference-seed-data`)
- ingest verification steps
- rollback and handoff
- optional reverse-proxy profile (`with-proxy`) for one external entrypoint

## Required Baseline Collections

Before first sample ingest, ensure these are seeded:

1. `permissions`
2. `roles`
3. `refseq_canonical`
4. `hgnc_genes`
5. `vep_metadata`
6. `asp_configs`
7. `assay_specific_panels`

`users` are intentionally not bulk-seeded by `bootstrap_center_collections.sh`; create the first admin with `bootstrap_local_admin.py`.

## Seed Source Policy

- `--seed-file` is the primary source for center onboarding/demo runtime collections.
- `--reference-seed-data` provides compressed baseline packs for core reference/RBAC data.
- `asp_configs` and `assay_specific_panels` are seeded from onboarding/demo input (default `--seed-file`).
- `permissions`, `roles`, `refseq_canonical`, `hgnc_genes`, and `vep_metadata` are loaded from `--reference-seed-data` only when that argument is provided.

## First-Run Method

- Use `scripts/center_first_run.sh` for first-time bootstrap.
- Pass admin credentials via CLI args (`--admin-email`, `--admin-password`).

Standard first-load command shape:

```bash
scripts/center_first_run.sh \
  --env-file <ENV_FILE> \
  --compose-file <COMPOSE_FILE> \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:<API_PORT>" \
  --admin-email "admin@your-center.org" \
  --admin-password "<ADMIN_PASSWORD>" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

For environment-specific concrete command values and verification gates, use:

- [Initial Deployment Checklist](initial-deployment-checklist.md)
- [Maintenance And Quality](maintenance-and-quality.md)

Operational defaults applied by compose stacks:

- Per-service container resource limits are enabled by default (`*_CONTAINER_MEM_LIMIT`, `*_CONTAINER_CPU_LIMIT`).
- API and web request throttling are enabled by default and configured from env templates.
- Internal Prometheus-style metrics are exposed at `GET /api/v1/internal/metrics` (requires `X-Internal-Token`).

ASPC contract rule for first-load data:

- `asp_configs` entries include `filters` and `reporting` objects.
- DNA SNV base behavior is configured with `filters`.
- DNA SNV retrieval uses the `generic_germline` and `generic_somatic` base groups, and center-specific SNV clauses are added through `query.snv`.
- DNA assay-specific SNV operator rules are configured with `query.snv`.
- DNA CNV behavior is configured with `filters.cnv_*`.
- RNA fusion behavior is configured with `filters.fusion_*`.

## Related References

- [API / Ingestion API](../api/ingestion-api.md)
- [Operations / Deployment Guide](deployment-guide.md)
- [Operations / Minimum Production Baseline](minimum-production-baseline.md)
