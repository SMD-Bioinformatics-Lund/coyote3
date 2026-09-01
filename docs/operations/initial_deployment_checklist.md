# Initial deployment checklist

**Last verified:** 13 August 2026

Use this procedure for a new Coyote3 installation. Database provisioning,
database bootstrap, application deployment, and clinical data ingest are
separate deliberate operations.

> **Info**
>
> The complete operator procedure, including production installation,
> acceptance, backup, subsequent deployment, and rollback, is maintained in
> [Production deployment](../start_here/production_deployment.md). This page
> is a concise operational checklist.
>

## Before you begin

- Prepare an environment file from `deploy/env/example.env`.
- Set `MONGO_URI` to the MongoDB service chosen by the center.
- Create the MongoDB application user with read/write access to the Coyote3
  database.
- Replace every placeholder secret in the environment file.
- Keep approved center ASP, ASPC, and ISGL definitions in the center's private
  deployment configuration.

The repository bootstrap catalogs contain no patient data, samples, reports, or
credentials:

| Catalog | Collections | Purpose |
| --- | --- | --- |
| `api/config/bootstrap/rbac` | `permissions`, `roles` | Application-owned system permissions and built-in roles. |
| `api/config/bootstrap/reference` | `hgnc_genes`, `vep_metadata` | Bundled reference snapshot used by the initial empty database. |
| `api/config/bootstrap/demo_center` | ASP, ASPC, ISGL | Optional synthetic configuration for a nonclinical demonstration only. |

## 1. Provision MongoDB

MongoDB is independent from the Coyote3 application Compose stack. The center
may use an existing MongoDB deployment, a managed service, or the supplied
standalone MongoDB Compose definition. Confirm that the URI is reachable from
the future API and worker containers before continuing.

```bash
mongosh "$MONGO_URI" --eval 'db.runCommand({ping: 1})'
```

See [MongoDB deployment and recovery](mongodb_deployment_and_recovery.md) for
the standalone Docker and replica-set procedure.

## 2. Initialize the empty application database

Run the direct bootstrap command from a checkout with the Python dependencies
installed. The command does not start Docker Compose, call HTTP endpoints, or
ingest any sample.

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$MONGO_URI" \
  --db "${COYOTE3_DB:?COYOTE3_DB must be set}" \
  --username "admin.coyote3" \
  --email "admin@your-center.org" \
  --password "<GENERATED_ADMIN_PASSWORD>"
```

It creates the first local `superuser` and loads the bundled `permissions`,
`roles`, `hgnc_genes`, and `vep_metadata` records into their empty
collections. A partially initialized governance database is rejected rather
than modified. A database that already has a superuser is reported and left
unchanged.

For a nonclinical local demonstration, add `--with-demo-center`. This loads
only the synthetic ASP, ASPC, and ISGL documents. It does not ingest a sample.

## 3. Start the Coyote3 services

Validate the environment and Compose definition, then start the services.

```bash
bash scripts/center_preflight.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml

./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

The application Compose stack starts the proxy, UI, API, worker, Beat, Redis,
and documentation services. It does not provision or seed MongoDB.

## 4. Verify service availability

Use the externally exposed URL, including `SCRIPT_NAME` when configured.

```bash
APP_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME}"
curl -fsS "$APP_URL/api/v1/health"
docker compose --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml ps
```

Sign in using the account created in step 2. Create additional users through
the Users administration area after login.

## 5. Import center clinical configuration

Before clinical sample ingest, import reviewed ASP, ASPC, and ISGL documents
through the managed administration interface or an approved controlled
collection-import process. The required active configuration is:

| Collection | Required purpose |
| --- | --- |
| `assay_specific_panels` | Panel metadata, assay group, platform, and covered-gene scope. |
| `asp_configs` | Active assay, subpanel, environment, analysis, filter, and reporting configuration. |
| `insilico_genelists` | Optional analysis-specific gene-list selection. |

An active ASPC must contain the appropriate `analysis_types`, `filters`, and
`reporting` configuration. These documents are center clinical configuration;
the demonstration catalog is not suitable for clinical use.

## 6. Validate and ingest controlled data

Validate every manifest before placing it in the ingest watch directory.

```bash
.venv/bin/python scripts/validate_ingest_spec.py \
  --yaml <SAMPLE_MANIFEST.yaml> \
  --check-files
```

Use [Sample YAML](../api/sample_yaml.md) and [Sample input files](../api/sample_input_files.md)
for the required formats. Ingest is a separate workflow; no deployment command
queues a sample automatically.

## 7. Record the deployment handoff

Record the MongoDB target, application release, environment file location,
health-check result, bootstrap operator, first-superuser account owner, and the
approved ASP/ASPC/ISGL release identifiers. Keep this information in the
center's controlled operational records.

## Existing installations

Do not run `bootstrap_database.py` to update populated reference or clinical
collections. Use the documented RBAC synchronization, reference-data release,
and ASP/ASPC/ISGL managed revision procedures instead. See
[Maintenance and quality](maintenance_and_quality.md).
