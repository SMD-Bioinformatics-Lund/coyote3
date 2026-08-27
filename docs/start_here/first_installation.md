# First installation

This procedure prepares an empty MongoDB database, installs the application-owned catalogs, creates the first administrator, and starts Coyote3. Run the steps in order. Bootstrap is an explicit operation and is never performed automatically when the API starts.

## 1. Prepare the host

Install Git, Docker Engine, and Docker Compose. Create persistent host directories for application logs, ingest data, and backups. Select or deploy a MongoDB 8.2 service that remains available independently of the Coyote3 application containers.

Create the external Docker network named by `COYOTE3_APP_NETWORK`. The [production deployment guide](production_deployment.md) contains the network and service commands.

## 2. Write the environment file

Copy `deploy/env/example.env` to a file outside version control and set the required values. At minimum, configure:

| Setting | Purpose |
| --- | --- |
| `MONGO_URI` | MongoDB connection string reachable from the API and workers. |
| `COYOTE3_DB` | Coyote3 application database name. It has no application default. |
| `BAM_DB` | BAM service database name. It has no application default. |
| `SECRET_KEY` | Signs application security material. Generate a unique random value. |
| `INTERNAL_API_TOKEN` | Authenticates internal service operations. Generate a separate random value. |
| `COYOTE3_APP_NETWORK` | Existing Docker network used by the application services. |
| Host data paths | Persistent locations for logs, watched manifests, staging data, and backups. |

Review the full [configuration reference](configuration.md) before a clinical installation.

## 3. Install the database baseline

Create a Python virtual environment and install the project dependencies, or run the command from a prepared API image. Then run:

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$MONGO_URI" \
  --db "$COYOTE3_DB" \
  --username "<first-superuser-username>" \
  --email "<first-superuser-email>" \
  --password "<generated-one-time-password>"
```

The command writes only to empty destination collections.

| Data installed | Collection | Ownership and behavior |
| --- | --- | --- |
| System permissions | `permissions` | Shipped with Coyote3. Assign through roles; do not rename or delete. |
| System roles | `roles` | Shipped role baselines. They may be edited or deactivated, but not deleted. |
| First local superuser | `users` | Credentials come from the command, not the repository. The account must change its password at first sign-in and cannot be deleted. |
| HGNC gene reference | `hgnc_genes` | Bundled reference snapshot loaded only when the collection is empty. |
| VEP metadata | `vep_metadata` | Bundled VEP metadata snapshot loaded only when the collection is empty. |

For a disposable demonstration environment, append `--with-demo-center`. This additionally installs synthetic ASP, ASPC, and ISGL records. These records are useful for interface and ingest validation; they are not approved clinical configuration.

## 4. Add center configuration

Before clinical data is ingested, create and review the center-owned configuration in this order:

1. Create the ASP definitions for each assay design and sequencing platform.
2. Create the ISGL records used by each analysis type and assay group.
3. Create active ASPC records for each ASP, subpanel, and environment combination.
4. Verify enabled analyses, filters, report sections, gene-list choices, and public-catalog visibility.
5. Confirm that the required authentication providers, users, roles, and scopes are configured.

Use JSON import/export in the administration pages when a reviewed configuration is transferred between installations. Imported values still pass the normal contract and permission checks.

## 5. Start Coyote3

Build and start the immutable application services with the production Compose files described in the [production deployment guide](production_deployment.md). Confirm that the API health check succeeds, then open the UI through the reverse proxy.

Sign in with the first-superuser account and change its password. Check the Application Controls page for API, worker, scheduler, cache, and MongoDB state.

## 6. Validate the installation

Complete these checks before clinical use:

1. Test each configured authentication provider with a representative account.
2. Confirm that delegated roles can access only their intended pages and operations.
3. Open the UI route audit and resolve every missing route, permission, or payload dependency.
4. Ingest one representative DNA sample and one representative RNA sample when both workflows are offered.
5. Review analysis tabs, filters, comments, classification, report preview, saved report, and deletion cleanup.
6. Create a backup and restore it into a disposable MongoDB instance.
7. Test the public catalog, API documentation, cookies, and forwarded headers through the production reverse proxy.

The [target-center acceptance guide](../operations/target_center_acceptance.md) provides the complete release record for these checks.
