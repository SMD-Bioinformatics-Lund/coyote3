# Installation bootstrap and data flow

This page explains the data installed during bootstrap and the order in which
services and clinical configuration become available. Follow
[first installation](first-installation.md) for setup commands and the
[deployment acceptance checklist](acceptance-checklist.md) for the deployment handoff.

For the purpose, format and ownership of each installed catalog, see
[installed catalogs](../reference/operational-files.md#installed-catalogs).

## Deployment Flow

The image build packages `core/src/coyote/config/factory_defaults.toml`
and `adapters/mongo/src/coyote_mongo/config/collections.toml` with
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
3. On fresh targets, bootstrap creates initial accounts and RBAC, then installs
   application catalogs and bundled HGNC/VEP references
   by default, with system creation provenance. Module skip flags disable selected parts.
4. The installer checks and applies compatible application indexes, starts services
   and verifies health. Existing deployments skip all initial data installation.
5. Verify browser and administrative access and complete initial password changes.
6. Configure and validate clinical workflows before ingesting clinical data.

The installer stops on unrecognized initialization states or index conflicts.
It does not reset databases, replace populated seed collections or run data migrations.

## Authoritative Procedure

Use [first installation](first-installation.md) for the commands and execution
order. It covers deployment files, storage, networking, bootstrap, startup and
clinical configuration. The [deployment acceptance checklist](acceptance-checklist.md)
records acceptance and handoff; it is not a second installation procedure.

## Required Baseline Collections

Before first sample ingest, ensure identity/RBAC, the assay and its applicable
configuration are available. Reference requirements depend on the input workflow:

1. `permissions`
2. `roles`
3. `hgnc_genes` for gene-reference lookup and validation workflows
4. `vep_metadata` for the releases used by VEP-annotated input
5. `assay_specific_panels`
6. `asp_configs`
7. `insilico_genelists` when the center uses in-silico gene-list filtering

Published `clinical_rule_sets` are optional for ingest and assay activation. They
are needed for automatic report narrative; without a compatible publication, the
report is available without that summary and the UI warns. Indexes and revision
collections are managed independently of whether rules have been authored.

The explicit database bootstrap installs the application-owned RBAC catalog,
creates a named system administrator and an emergency superuser. It
runs only against empty governance collections.
Bundled HGNC/VEP references are installed by default;
use `--skip-knowledgebase` to disable them. Later additions and
repairs use `scripts/deployment/manage_data.py --api-url API_URL --modules
application knowledgebase`. Add `--force` to repair explicitly selected modules.
API login, administrator roles and required password changes apply to maintenance.
Knowledgebase indexing is a separate opt-in operation.
See [installation operations](installation-operations.md).

## Seed Source Policy

- `core/src/coyote/config/catalogs/rbac` is the core-owned permission and role catalog,
  read by the server's explicit installer.
- Bundled permission documents are installed with `system_managed: true`; their
  definitions are immutable at runtime but remain assignable through roles.
- `services/demo/src/coyote_demo/data/demo_center` contains synthetic ASP, ASPC, and ISGL documents for isolated installation checks.
- `services/atlas/src/coyote_atlas/data/reference` contains the release-bundled HGNC and VEP
  snapshots loaded by the reference installer when their collections are
  empty.
- Normal application startup does not seed or synchronize governance documents.

## Database bootstrap method

- Run `scripts/bootstrap/bootstrap_database.py` before application services are started.
- The initial logins are fixed to `coyote4.superuser` and `coyote4.sysadmin`.
  Optionally set their contacts using `--email` and `--sys-admin-email`.
- Omit `--password` and `--sys-admin-password` to generate independent temporary
  passwords, displayed once after account creation.
  Both accounts must replace their temporary password at first sign-in.
- Bootstrap assigns `superuser` and `sys_admin` respectively. The clinical
  administrator role is `admin` and is assigned separately.
- A complete existing installation is left unchanged, even when a data module is missing.
  Only the invocation that creates accounts can seed without API login. Partial governance data
  without a superuser is rejected for manual review.
- Additional superusers must be created by an existing authenticated superuser.

Standard command shape:

```bash
.venv/bin/python scripts/bootstrap/bootstrap_database.py \
  --mongo-uri "$COYOTE4_MONGO_URI" \
  --identity-mongo-uri "$IDENTITY_MONGO_URI" \
  --db "$COYOTE4_DB" \
  --identity-db "$IDENTITY_DB" \
  --sys-admin-email "operator@example.org" \
  --email "admin@your-center.org"
```

Configure `COYOTE4_MONGO_URI` for the independently operated database before this
command. If the supplied MongoDB Compose definition is used, its persistent
host resources are `COYOTE4_MONGO_DATA_HOST_ROOT` and `COYOTE4_MONGO_KEYFILE_HOST_PATH`.
`COYOTE4_MONGO_BACKUP_HOST_ROOT` is optional and mounts a directory only with
`docker-compose.mongo-backup.yml`. Omit both when backups are managed externally.
Set `COYOTE4_LOGS_HOST_ROOT` for every deployment; it is mounted at `/app/logs`
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

The core configuration package lives at `core/src/coyote/config`; host settings
live at `api/src/coyote_api/config`. Deployment installs their wheels and resolves
packaged resources through Python; it does not depend on source checkout paths.
The core supplies typed software policy and the first-deployment RBAC catalog.
Current Dockerfiles do not copy or mount a separate `/app/config` directory. If
that directory appears in a running container, the container was built from an
older image or an external deployment mount; rebuild and recreate the container
from the current Compose definition.

The optional `coyote-demo` package owns connected DNA/RNA configuration and
synthetic starter samples. It is installed and enabled only for an
[isolated demonstration deployment](demo-installation.md), using dedicated
databases and restricted credentials. Normal bootstrap and general data maintenance
do not install demonstration records.

Start Coyote4 after database bootstrap:

```bash
./scripts/deployment/compose-with-version.sh \
  --env-file .coyote4_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

For environment-specific values and full verification gates, use:

- [Deployment Acceptance Checklist](acceptance-checklist.md)
- [Maintenance And Quality](../operations/maintenance-and-verification.md)

Operational defaults:

- Per-service container resource limits are enabled by default (`*_CONTAINER_MEM_LIMIT`, `*_CONTAINER_CPU_LIMIT`).
- API and web request throttling are enabled by default and configured from env templates.
- Internal Prometheus-style metrics are exposed at `GET /api/v1/internal/metrics` (requires `X-Coyote-Internal-Token`).

Sample manifest reference:

- Use [Sample YAML Guide](../reference/sample-manifest.md) for the required DNA/RNA YAML shape.
- Use [Sample Input Files](../reference/ingest-files/README.md#file-contracts) for the raw VCF and JSON payload formats consumed by the ingest parsers.
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
  default, assay group, assay and diagnosis. Bootstrap installs the bundled group
  rules and typed installation-file criteria as attributed version-one publications.
- DNA CNV thresholds use `filters.somatic.cnv`; RNA fusion thresholds use
  `filters.somatic.fusion`.

## Related References

- [Ingestion API](../api/sample-ingestion.md)
- [Deployment Guide](containers-and-reverse-proxy.md)
- [Minimum Production Baseline](production-requirements.md)
