# First installation

This procedure prepares an empty MongoDB database, installs the application-owned catalogs, creates a named system administrator and an emergency superuser, and starts Coyote3. Run the steps in order. Bootstrap is an explicit operation and is never performed automatically when the API starts.

## 1. Prepare the host

Install Git, Docker Engine, and Docker Compose. Create persistent host directories for application logs, ingest data, and backups. Select or deploy a MongoDB 8.2 service that remains available independently of the Coyote3 application containers.

Create the external Docker network named by `COYOTE3_APP_NETWORK`. The [production deployment guide](production_deployment.md) contains the network and service commands.

## 2. Write the environment file

Copy `deploy/env/example.env` to a file outside version control and set the required values. At minimum, configure:

| Setting | Purpose |
| --- | --- |
| `COYOTE3_MONGO_URI` | MongoDB connection string reachable from the API and workers. |
| `COYOTE3_DB` | Coyote3 application database name. It has no application default. |
| `IDENTITY_DB` | Dedicated identity and security database name. It must differ from every other configured database. |
| `KNOWLEDGEBASE_DB` | Dedicated external knowledgebase database name. It must differ from `COYOTE3_DB` and `BAM_DB`. |
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
  --mongo-uri "$COYOTE3_MONGO_URI" \
  --identity-mongo-uri "$IDENTITY_MONGO_URI" \
  --db "$COYOTE3_DB" \
  --identity-db "$IDENTITY_DB" \
  --sys-admin-username "center.operator" \
  --sys-admin-email "operator@example.org" \
  --username "<first-superuser-username>" \
  --email "<first-superuser-email>"
```

Enter and confirm each temporary password at the hidden prompts. Use different
usernames, email addresses, and passwords for the two accounts. Temporary passwords
must contain at least 12 characters. For automation, `--password` and
`--sys-admin-password` accept credentials supplied by the deployment secret store;
do not record them in shell history, logs, or version control. When running the
interactive command through Compose, use `run --rm --no-deps -it api`.

Permissions, roles, and both accounts are committed together in one identity-database
transaction. MongoDB must support transactions, including a single-member replica set
for local development. Existing governance with a superuser is left unchanged;
partially initialized governance without a superuser is rejected. Reference and
optional demonstration collections are loaded separately, only when empty.

| Data installed | Collection | Ownership and behavior |
| --- | --- | --- |
| System permissions | `permissions` | Shipped with Coyote3. Assign through roles; do not rename or delete. |
| System roles | `roles` | Shipped role baselines. Protected from ordinary editing, deactivation, and deletion. |
| Initial local accounts | `users` | One `sys_admin` and one `superuser`, with operator-supplied credentials. Both must change their password at first sign-in. Profiles, activation, and deletion are protected; password workflows and UI preferences remain available. |
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

Sign in separately with each initial account. Coyote3 redirects to `/change-password`
before opening the workspace. Enter the current temporary password, a new password,
and its confirmation. The new password must differ from the current one and contain
at least 10 characters, including uppercase, lowercase, a number, and a symbol.
After the change, sign in again: previous sessions are invalidated.

Until the password changes, the API permits only identity/session inspection,
password change, and sign-out, including for the superuser. This restriction is
enforced by the API, not just the redirect.

Use the named system administrator for Application Controls and account operations.
Assign a clinical administrator for clinical configuration. Keep emergency credentials
under controlled access and test the recovery procedure. See
[administrative responsibilities](../developer/permissions_naming.md#administrative-responsibilities).

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
