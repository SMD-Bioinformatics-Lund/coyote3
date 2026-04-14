# Center Deployment Guide

This page is the entry point for deployment.
Use the checklist for the full procedure.

## Deployment Flow

1. Prepare environment and secrets.
2. Start the stack.
3. Bootstrap the first superuser.
4. Seed baseline collections in strict order.
5. Validate and ingest the demo sample.
6. Verify UI/API and admin flows.

## Authoritative Procedure

Use this page as a map.
Use the checklist as the source of truth for the exact commands and execution order.

- [Initial Deployment Checklist](initial_deployment_checklist.md)

The checklist defines:
- exact commands and command order
- required collection order
- seed-source policy
- ingest verification
- rollback and handoff
- compose profile usage

## Required Baseline Collections

Before first sample ingest, ensure these are seeded:

1. `permissions`
2. `roles`
3. `refseq_canonical`
4. `hgnc_genes`
5. `vep_metadata`
6. `asp_configs`
7. `assay_specific_panels`

`users` are intentionally not bulk-seeded by `bootstrap_center_collections.sh`; create the first superuser with `bootstrap_local_admin.py`.

## Seed Source Policy

- `--seed-file` is the primary source for demo/bootstrap runtime collections.
- `--reference-seed-data` provides compressed baseline packs for core reference/RBAC data.
- `asp_configs` and `assay_specific_panels` are seeded from bootstrap/demo input (default `--seed-file`).
- `permissions`, `roles`, `refseq_canonical`, `hgnc_genes`, and `vep_metadata` are loaded from `--reference-seed-data` only when that argument is provided.

## First-Run Method

- Use `scripts/center_first_run.sh` for first-time bootstrap.
- Pass admin identity explicitly:
  - `--admin-username`
  - `--admin-email`
  - `--admin-password`
- `center_first_run.sh` bootstraps a `superuser`, not an `admin`.
- The bootstrap script may create only the first superuser. Additional superusers must be created by an existing authenticated superuser.

Standard command shape:

```bash
scripts/center_first_run.sh \
  --env-file <ENV_FILE> \
  --compose-file <COMPOSE_FILE> \
  [--compose-profile <PROFILE>] \
  --api-base-url "http://${COYOTE3_HOST:-localhost}:<API_PORT>" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@your-center.org" \
  --admin-password "<ADMIN_PASSWORD>" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

If `MONGO_URI` points to `coyote3_mongo`, include:

```bash
--compose-profile with-mongo
```

Prod-like local Docker command:

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml \
  --compose-profile with-mongo \
  --api-base-url "http://localhost:5818" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@coyote3.local" \
  --admin-password "Coyote3.Admin" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

For environment-specific values and full verification gates, use:

- [Initial Deployment Checklist](initial_deployment_checklist.md)
- [Maintenance And Quality](maintenance_and_quality.md)

Operational defaults:

- Per-service container resource limits are enabled by default (`*_CONTAINER_MEM_LIMIT`, `*_CONTAINER_CPU_LIMIT`).
- API and web request throttling are enabled by default and configured from env templates.
- Internal Prometheus-style metrics are exposed at `GET /api/v1/internal/metrics` (requires `X-Internal-Token`).

Sample manifest reference:

- Use [API / Sample YAML Guide](../api/sample_yaml.md) for the required DNA/RNA YAML shape.
- Ensure the YAML `vep_version` matches a seeded `vep_metadata.vep_id` value before first sample ingest.

ASPC contract rule for first-load data:

- `asp_configs` entries include `filters` and `reporting` objects.
- DNA SNV base behavior is configured with `filters`.
- DNA SNV retrieval uses the `generic_germline` and `generic_somatic` base groups, and center-specific SNV clauses are added through `query.snv`.
- DNA assay-specific SNV operator rules are configured with `query.snv`.
- DNA CNV behavior is configured with `filters.cnv_*`.
- RNA fusion behavior is configured with `filters.fusion_*`.

## Related References

- [API / Ingestion API](../api/ingestion_api.md)
- [Operations / Deployment Guide](deployment_guide.md)
- [Operations / Minimum Production Baseline](minimum_production_baseline.md)
