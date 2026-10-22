# Installation and data maintenance

First installation and later data maintenance are separate operations. The deployment
installer builds and starts services. The Python maintenance command uses a running API
and does not build, start or recreate services.

## First installation

MongoDB endpoints, database users and the application network must be configured
before installation. Follow [first installation](first-installation.md) for provisioning.

```bash
bash scripts/deployment/install_center.sh \
  --env-file "$COYOTE_ENV_FILE" \
  --project "$COYOTE_PROJECT" \
  --compose-file deploy/compose/docker-compose.yml
```

All eight stages run by default: network, directories, build, validate, bootstrap,
indexes, start and health. `--setup-center` explicitly selects the same complete
sequence; it cannot be combined with `--steps`. `--skip-build` uses existing images.
`--steps` selects individual stages in their canonical order.

Fresh bootstrap creates two distinct local accounts and their RBAC catalog, then
installs application catalogs, bundled HGNC/VEP references, connected DNA/RNA demo
configuration and both synthetic starter samples in their configured databases.
Account identities are prompted when omitted; temporary passwords are hidden and
confirmed. Both accounts must change their password on first API or browser use.

Production Redis TLS is optional. When selected, prepare the
[certificates](../operations/redis-tls.md) and repeat
`--compose-file deploy/compose/docker-compose.redis-tls.yml` after the base file on
every installer invocation. Include the same ordered overlays in subsequent Compose,
upgrade and recovery commands. Development and staging exclude this overlay.

| Module | Default contents | Disable flag |
| --- | --- | --- |
| Identity | Emergency superuser, named system administrator, permissions and roles | `--skip-users` |
| Application | Eleven assay groups, twelve group-scoped SNV policies and immutable baseline revisions | `--skip-application` |
| Knowledgebase | Bundled HGNC genes, VEP metadata and associated binary diagrams | `--skip-knowledgebase` |
| Demo | Connected DNA/RNA assays, configurations, gene lists, subpanels, rules, catalog and two synthetic samples | `--skip-demo` |

`--skip-application` requires `--skip-demo`. `--skip-users` requires all three
data modules to be skipped too: unauthenticated data installation is authorized only
by successful initial account creation in that same invocation. On a deployment with
existing accounts, use authenticated maintenance to add disabled modules later.

Automated creations use `created_by: "system"`; starter sample provenance uses
`ingested_by: "system"`. Existing populated reference collections are preserved.
The demo catalog is published only when no public catalog exists; otherwise its
version remains a draft. No application data is seeded by ordinary API startup.

Existing deployments skip the entire bootstrap operation, even when a selected
module is missing. A partially recognized application/identity target is rejected.
An initial data failure after account creation does not reopen unauthenticated
seeding. Rerun deployment to finish indexes and startup while preserving existing
data, then complete missing modules with the maintenance command.

Update deployment automation to remove the former `--with-demo-center` and
`--with-knowledgebase-seeds` opt-in flags; these options are rejected. Use skip
flags for fresh installation and the separate maintenance command for later work.

### Stages and operational flags

| Stage or option | Behavior |
| --- | --- |
| `network` | Inspect the pre-provisioned external application network and require the bridge driver. Never create or repair networking. |
| `directories` | Prepare configured host directories and permissions. |
| `build` | Build the selected deployment images unless `--skip-build` is set. |
| `validate` | Validate mounted center configuration, endpoint access and target state. |
| `bootstrap` | Install the default modules only on a fresh target; preserve existing deployments. |
| `indexes` | Plan, apply and verify application, identity and BAM indexes. Conflicts stop execution. |
| `start` | Verify initial accounts and required indexes, start services and wait for health. |
| `health` | Check API/browser routes through the rendered local proxy address. |
| `--sys-admin-username NAME --sys-admin-email EMAIL` | Optional initial administrator identity hints. |
| `--username NAME --email EMAIL` | Optional initial emergency-superuser identity hints. |
| `--with-knowledgebase-indexes` | Separately plan, apply and verify knowledgebase indexes. |
| `--knowledgebase-maintenance-uri-file FILE` | Optional restricted URI file for fresh knowledgebase installation and selected knowledgebase indexes. It must target the configured endpoint/database; runtime credentials remain unchanged. |

Selecting startup also checks Redis cache, broker and result-backend connections
before bootstrap or indexes. Secrets remain in the private environment file.
Do not enable shell tracing when handling credentials.

Every stage that runs application containers requires the existing external bridge,
even when `network` is omitted from `--steps`. A failed network inspection stops
before image builds or container operations. Provision missing infrastructure using
[first installation](first-installation.md#6-create-the-application-network).
The installer does not change firewall rules, forwarding settings or Docker daemon
configuration, and does not restart the Docker daemon.

The local health-check URL uses the proxy's rendered published port and
`SCRIPT_NAME`. The separately displayed public URL uses `PUBLIC_BASE_URL`.
See [connection troubleshooting](../operations/troubleshooting.md#api-startup-fails-while-connecting-to-redis)
when containers cannot reach Redis.

### Direct initial bootstrap

The same freshness check applies when invoking Python directly through Compose:

```bash
coyote_compose run --rm --no-deps -it api sh -c '
  exec python3 scripts/bootstrap/bootstrap_database.py \
    --db "$COYOTE3_DB" --identity-db "$IDENTITY_DB"
'
```

The Python command supports the same four module skip flags. It has no `--force`
option and never uses an existing account name as unauthenticated authorization.
Configured connections need write access to the selected destination databases.
Knowledgebase installation can use the deployment installer's maintenance URI
without granting routine API connections write privileges.

## Authenticated data maintenance

Use an existing `admin`, `sys_admin` or `superuser` account with the running API.
Module selection is mandatory; `--force` never implicitly selects every module.

```bash
.venv/bin/python scripts/deployment/manage_data.py \
  --api-url https://coyote.example.org/coyote3 \
  --modules application knowledgebase
```

Without `--force`, populated catalog collections and existing demo samples are
skipped. To repair selected bundled modules:

```bash
.venv/bin/python scripts/deployment/manage_data.py \
  --api-url https://coyote.example.org/coyote3 \
  --modules application demo --force
```

Inside Compose, use `coyote_compose run --rm --no-deps -it api python3
scripts/deployment/manage_data.py --api-url http://api:8001 --modules knowledgebase --force`.
The API's configured connection needs write privileges on each selected database.

The command requests a username and hidden password, signs in using
`POST /api/v1/auth/sessions`, and completes a required first-login password change
using `POST /api/v1/auth/password/change`. It signs in again with the new password
because password changes invalidate previous sessions. It then calls
`POST /api/v1/admin/installation/data` and revokes its session afterward.
Passwords are never command arguments or stored in credential files.

The write request is `{"modules":["application","demo"],"force":true}`.
The application service checks the authenticated administrator role and rejects
temporary-password sessions. Client actors, seed paths and arbitrary documents are
not accepted. Newly created seed records use the system creator; updates and API
audit events record the authenticated administrator.

| Module | Forced maintenance boundary |
| --- | --- |
| `identity` | Restore missing bundled permissions/roles and union missing grants into system roles. Preserve local grants, activation state, every user, membership and password. Account creation/reset uses the normal account administration workflow. |
| `application` | Repair bundled group labels/descriptions and add missing identities. Preserve group availability, center-owned scopes and custom records. Changed bundled query content is published as a new version with retained hash-linked history; retired-only scopes stay retired. |
| `knowledgebase` | Repair system-created bundled reference IDs and content-addressed diagrams. A bundled publication or surviving system provenance identifies recoverable initial batches; active external releases are preserved. Preserve unknown/unattributed records and unrelated gene/release IDs. |
| `demo` | Restore missing packaged configuration without overwriting existing configuration or rule history. Reingest only system-owned starter samples with their exact testing assay/subpanel, preserving sample IDs. Samples with reports, comments, RNA classifications or human ingest provenance are preserved. |

## Knowledgebase operations

Fresh bootstrap includes bundled references unless `--skip-knowledgebase` is selected.
Later additions and repairs require API maintenance with `--modules knowledgebase`;
the API's configured database connection needs write access during that operation.
Knowledgebase index maintenance remains a separately selected operation.

External releases use their source-specific
[knowledgebase import procedures](../reference/knowledgebases/README.md).
The maintenance command does not drop databases or bulk-reset collections.
For separately prepared HGNC/BioMart files, use the
[gene installation reference](../operations/hgnc-gene-installation.md).

## Standalone index maintenance

`manage_mongo_indexes.py` supports `status`, `plan`, `apply` and explicit `retire`.
Each accepts `--scope application|knowledgebase|all`; the default is `application`.
`application` includes the application, identity and BAM repositories and security
indexes. `knowledgebase` selects reference repositories only. Use `all` only when
maintenance of both groups is intended.

```bash
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py plan --scope application
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py apply --scope application --summary
coyote_compose run --rm --no-deps -T api \
  python3 -m scripts.deployment.installation_checks indexes-ready --scope application
```

Replace `application` with `knowledgebase` for separately scheduled reference index
maintenance. `--summary` prints counts and returns a nonzero status if any required
index remains missing or conflicting. Without it, the index command prints JSON.
`indexes` is a read-only precheck that permits missing indexes; `indexes-ready`
requires all selected indexes to be present. Neither check creates indexes.
No command automatically drops a conflicting index. Use the
[index maintenance runbook](../operations/maintenance-and-verification.md) for reviewed retirement.
