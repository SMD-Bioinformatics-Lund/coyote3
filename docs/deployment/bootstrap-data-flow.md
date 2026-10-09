# Installation bootstrap and data flow

This page explains the data installed during bootstrap and the order in which
services and clinical configuration become available. Follow
[first installation](first-installation.md) for setup commands and the
[installation checklist](installation-checklist.md) for the deployment handoff.

For the purpose, format and ownership of each installed catalog, see
[installed catalogs](../reference/operational-files.md#installed-catalogs).

## Deployment Flow

The image build packages `api/config/clinical_capabilities.toml`,
`api/config/clinical_query_defaults.toml` and `api/config/collections.toml` with
the API code. These files are application contracts, not database seed documents.
They supply supported clinical identifiers, base query settings and collection
bindings on the first installation and subsequent releases. The
[first-installation validation](first-installation.md#8-build-images-and-install-the-database-baseline)
loads them together with the three editable center files before bootstrap writes.

![URL and reverse-proxy request flow](../assets/diagrams/url-request-flow.svg)

![First-deployment bootstrap data flow](../assets/diagrams/bootstrap-data-flow.svg)

1. Prepare deployment configuration, storage, MongoDB endpoints and database users.
2. Run `scripts/deployment/install_center.sh --setup-center` to build images and validate configuration
   and database readiness.
3. The installer bootstraps empty application/identity targets, preserves existing
   installations, checks and applies compatible application indexes, installs bundled
   HGNC/VEP references into empty knowledgebase collections, then starts services.
4. Verify browser and administrative access and complete initial password changes.
5. Configure and validate clinical workflows before ingesting clinical data.

The installer stops on unrecognized initialization states or index conflicts.
It does not reset databases, replace populated seed collections or run data migrations.

## Authoritative Procedure

Use [first installation](first-installation.md) for the commands and execution
order. It covers deployment files, storage, networking, bootstrap, startup and
clinical configuration. The [installation checklist](installation-checklist.md)
records acceptance and handoff; it is not a second installation procedure.

## Required Baseline Collections

Before first sample ingest, ensure these are seeded:

1. `permissions`
2. `roles`
3. `hgnc_genes`
4. `vep_metadata`
5. `assay_specific_panels`
6. `clinical_rule_sets`
7. `asp_configs`
8. `insilico_genelists` when the center uses in-silico gene-list filtering

The explicit database bootstrap installs the application-owned RBAC catalog,
creates a named system administrator and an emergency superuser. It
runs only against empty governance collections.
Bundled HGNC and VEP references are included in `--setup-center`. They can also be
installed separately with `scripts/bootstrap/install_reference_data.py --actor ADMIN_USERNAME`, or the
installer's `--with-knowledgebase-seeds` option. Knowledgebase indexing is a separate
opt-in operation. See [installation operations](installation-operations.md).

## Seed Source Policy

- `api/config/bootstrap/rbac` is the application-owned permission and role catalog.
- Bundled permission documents are installed with `system_managed: true`; their
  definitions are immutable at runtime but remain assignable through roles.
- `api/config/bootstrap/demo_center` contains synthetic ASP, ASPC, and ISGL documents for installation checks.
- `api/config/bootstrap/reference` contains the release-bundled HGNC and VEP
  snapshots loaded by the reference installer when their collections are
  empty.
- Normal application startup does not seed or synchronize governance documents.

## Database bootstrap method

- Run `scripts/bootstrap/bootstrap_database.py` before application services are started.
- Pass the emergency account using `--username` and `--email`, and the named system
  administrator using `--sys-admin-username` and `--sys-admin-email`.
- Omit `--password` and `--sys-admin-password` for hidden, confirmed password prompts.
  Both accounts must replace their temporary password at first sign-in.
- Bootstrap assigns `superuser` and `sys_admin` respectively. The clinical
  administrator role is `admin` and is assigned separately.
- A complete existing installation is left unchanged. Partial governance data
  without a superuser is rejected for manual review.
- Additional superusers must be created by an existing authenticated superuser.

Standard command shape:

```bash
.venv/bin/python scripts/bootstrap/bootstrap_database.py \
  --mongo-uri "$COYOTE3_MONGO_URI" \
  --identity-mongo-uri "$IDENTITY_MONGO_URI" \
  --db "$COYOTE3_DB" \
  --identity-db "$IDENTITY_DB" \
  --sys-admin-username "center.operator" \
  --sys-admin-email "operator@example.org" \
  --username "admin.coyote3" \
  --email "admin@your-center.org" \
  --password "<ADMIN_PASSWORD>"
```

Configure `COYOTE3_MONGO_URI` for the independently operated database before this
command. If the supplied MongoDB Compose definition is used, its persistent
host resources are `COYOTE3_MONGO_DATA_HOST_ROOT` and `COYOTE3_MONGO_KEYFILE_HOST_PATH`.
`COYOTE3_MONGO_BACKUP_HOST_ROOT` is optional and mounts a directory only with
`docker-compose.mongo-backup.yml`. Omit both when backups are managed externally.
Set `COYOTE3_LOGS_HOST_ROOT` for every deployment; it is mounted at `/app/logs`
in the API, worker, and Beat containers.

> **Warning: Existing named-volume installations**
>
>
> A bind-mounted Mongo data directory does not automatically receive data
> from a Docker named volume used by an older deployment. Back up and restore
> that database, or copy it using an approved MongoDB maintenance procedure,
> before removing the old named volume. Start the new Mongo container only
> after the selected host data directory contains the intended database.
>

## Packaged configuration location

The API configuration package is `api/config` in the repository and
`/app/api/config` in the API image. It must be present because it contains typed
software settings, center configuration, and the first-deployment RBAC catalog.
Current Dockerfiles do not copy or mount a separate `/app/config` directory. If
that directory appears in a running container, the container was built from an
older image or an external deployment mount; rebuild and recreate the container
from the current Compose definition.

For a nonclinical local demonstration, add `--with-demo-center`. The flag
loads only the bundled synthetic ASP, ASPC, and ISGL documents; it does not
create samples or run ingest.

Start Coyote3 after database bootstrap:

```bash
./scripts/deployment/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

For environment-specific values and full verification gates, use:

- [Initial Deployment Checklist](installation-checklist.md)
- [Maintenance And Quality](../operations/maintenance-and-verification.md)

Operational defaults:

- Per-service container resource limits are enabled by default (`*_CONTAINER_MEM_LIMIT`, `*_CONTAINER_CPU_LIMIT`).
- API and web request throttling are enabled by default and configured from env templates.
- Internal Prometheus-style metrics are exposed at `GET /api/v1/internal/metrics` (requires `X-Internal-Token`).

Sample manifest reference:

- Use [Sample YAML Guide](../reference/sample-manifest.md) for the required DNA/RNA YAML shape.
- Use [Sample Input Files](../reference/sample-file-formats.md) for the raw VCF and JSON payload formats consumed by the ingest parsers.
- Ensure the DNA pipeline writes the VEP version into each VCF `##VEP=` header
  and seed the matching `vep_metadata.vep_id` value before DNA interpretation
  or reporting. A YAML `database_versions.vep` override is supported only for
  an explicit correction or a pipeline that cannot emit the header value.

ASPC contract rule for first-load data:

- `asp_configs` entries include `filters` and `reporting` objects.
- Every enabled reporting scope resolves to a published exact or assay Base release for its analyte and `reporting.language`.
- DNA SNV base behavior is configured with `filters`.
- Evidence modes and typed finding exceptions resolve through
  [query rules](../administration/query-rules.md): application baseline, database
  default, assay group, assay and subpanel. Bootstrap installs the bundled group
  rules and typed installation-file criteria as attributed version-one publications.
- DNA CNV thresholds use `filters.somatic.cnv`; RNA fusion thresholds use
  `filters.somatic.fusion`.

## Related References

- [Ingestion API](../api/sample-ingestion.md)
- [Deployment Guide](containers-and-reverse-proxy.md)
- [Minimum Production Baseline](production-requirements.md)
