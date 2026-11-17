# Installation and data maintenance

First installation and later data maintenance are separate operations. The deployment
installer builds and starts services. The data maintenance command uses a running API
and does not build, start or recreate services.

## Entry point and profiles

Run `bash install.sh --help` from the checkout. `deploy`, `plan`, `compose`,
`check`, `center`, `data`, `demo` and `watch` share this entry point; implementation modules
live in `deploy/installer/`. Python 3.12 or later is required. The launcher prefers
`PYTHON_BIN`, then the checkout virtual environment, then a supported system Python.
Ordinary Docker installation needs no server packages installed on the host.

| Selection | Default Compose files | Image tag |
| --- | --- | --- |
| `--environment prod` or `production` | Base | Application version |
| `--environment dev` or `development` | Base + dev | Version + `-dev` |
| `--environment stage` or `staging` | Base + stage | Version + `-stage` |
| `--environment test` or `testing` | Base + test | Version + `-test` |
| `demo` | Dedicated isolated demo stack | Demo build targets |

Both `--environment` and `ENV_NAME` accept short or full deployment names. An
explicit selection must agree with `ENV_NAME` after normalization. Without
`--environment`, the command derives it from the environment file, allowing an
explicit process-environment override. Use `--legacy` for the maintained older-host
Compose definitions. `--overlay FILE` appends an overlay; repeated
`--compose-file FILE` options replace the default file selection entirely.
Keep the same environment file, project name and ordered overlays for every operation.

Development profiles automatically reload mounted backend package sources and use
Vite hot updates for frontend/CSS edits. Native development uses
`install.sh watch --env-file FILE -- COMMAND`; it rejects other environments.
See [editable development](../sdk/uv-development.md) for commands and restart behavior.

These deployment names are independent of the sample's clinical profile.
Samples use `production`, `development`, `testing` or `validation`; the installer
does not translate `staging` into sample `validation`. See the
[environment naming map](environments-and-secrets.md#environment-naming-map).

Preview a regular deployment using local files only:

```bash
bash install.sh plan --environment stage --env-file .stage.env --project coyote4-stage
bash install.sh deploy --environment stage --env-file .stage.env --project coyote4-stage
bash install.sh compose --env-file .stage.env --project coyote4-stage ps
```

`plan` does not execute subprocesses, contact services or prepare storage. It
checks local selections and secret placeholders; it cannot establish that a
network, database or image is ready. `deploy` logs timestamped stages, streams
build output and stops at the first failure. It does not automatically roll back
completed database operations. `NO_COLOR=1` disables terminal colors.

Use [demo installation](demo-installation.md) for Docker or native demonstrations.
Demo settings cannot be substituted into an ordinary production profile.

## First installation

MongoDB endpoints and the application network must be configured
before installation. Follow [first installation](first-installation.md) for provisioning.

```bash
bash install.sh deploy \
  --env-file "$COYOTE_ENV_FILE" \
  --project "$COYOTE_PROJECT" \
  --compose-file deploy/compose/docker-compose.yml
```

All eight stages run by default: network, directories, build, validate, bootstrap,
indexes, start and health. `--skip-build` uses existing images.
`--steps` selects individual stages in their canonical order.

Fresh bootstrap creates two distinct local accounts and their RBAC catalog, then
installs application catalogs and the installed Atlas provider's HGNC/VEP
references in their configured databases. It installs no synthetic samples or
demo assay configuration; use the separate [demo deployment](demo-installation.md).
The fixed logins are `coyote4.sysadmin` and `coyote4.superuser`. Independent temporary
passwords are generated and printed once after account creation. Both accounts must
change their password on first API or browser use. Existing accounts are preserved.
The `--system-admin-*` options apply to the `sys_admin` account for account, access
and system operations. The `--superuser-*` options apply to the privileged recovery
account. The clinical administrator role, `admin`, is assigned separately through
authenticated user administration.
MongoDB connections without authentication produce a warning and do not block installation.

Production Redis TLS is optional. When selected, prepare the
[certificates](../operations/redis-tls.md) and repeat
`--compose-file deploy/compose/docker-compose.redis-tls.yml` after the base file on
every installer invocation. Include the same ordered overlays in subsequent Compose,
upgrade and recovery commands. Development and staging exclude this overlay.

| Module | Default contents | Disable flag |
| --- | --- | --- |
| Identity | Emergency superuser, named system administrator, permissions and roles | `--skip-users` |
| Application | Five biological groups, six group-scoped SNV policies and immutable baseline revisions | `--skip-application` |
| Knowledgebase | Bundled HGNC genes, VEP metadata and associated binary diagrams | `--skip-knowledgebase` |

`--skip-users` requires application and knowledgebase installation to be skipped
too: unauthenticated data installation is authorized only
by successful initial account creation in that same invocation. On a deployment with
existing accounts, use authenticated maintenance to add disabled modules later.

Automated creations use `created_by: "system"`. Existing populated reference
collections are preserved. No application data is seeded by ordinary API startup.

Existing deployments skip the entire bootstrap operation, even when a selected
module is missing. A partially recognized application/identity target is rejected.
An initial data failure after account creation does not reopen unauthenticated
seeding. Rerun deployment to finish indexes and startup while preserving existing
data, then complete missing modules with the maintenance command.

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
| `--system-admin-username USERNAME` | Initial system-administrator login, fixed to `coyote4.sysadmin`. Omit to use this default. |
| `--system-admin-email EMAIL` | Contact address for the initial system administrator (`sys_admin`). |
| `--superuser-username USERNAME` | Initial emergency superuser login, fixed to `coyote4.superuser`. Omit to use this default. |
| `--superuser-email EMAIL` | Contact address for the initial emergency superuser (`superuser`). |
| `--with-knowledgebase-indexes` | Separately plan, apply and verify knowledgebase indexes. |
| `--knowledgebase-maintenance-uri-file FILE` | Optional restricted URI file for fresh knowledgebase installation and selected knowledgebase indexes. It must target the configured endpoint/database; runtime credentials remain unchanged. |
| `--identity-maintenance-uri-file FILE` | Explicitly upgrade the restricted identity runtime role using a maintenance connection before validation. It does not enable MongoDB authorization or create runtime passwords. |

Selecting startup also checks Redis cache, broker and result-backend connections
before bootstrap or indexes. Secrets remain in the private environment file.
Do not enable shell tracing when handling credentials.

Every stage that runs application containers requires the existing external bridge,
even when `network` is omitted from `--steps`. A failed network inspection stops
before image builds or container operations. Provision missing infrastructure using
[first installation](first-installation.md#6-create-the-application-network).
The installer does not change firewall rules, forwarding settings or Docker daemon
configuration, and does not restart the Docker daemon.

For a configuration-only host preflight, use `bash install.sh check --resolved` with the same
environment file and ordered Compose files. It needs a supported host interpreter
with the application installed. It validates the resolved mounts, center files
(including optional report presentation) and directory mode bits. It does not
check network connectivity, MongoDB credentials, installation state, Redis or
indexes. Only `--prepare-directories` creates storage. The installer's `validate`
stage runs its application checks in the API image instead and needs no host SDK.

The local health-check URL uses the proxy's rendered published port and
`SCRIPT_NAME`. The separately displayed public URL uses `PUBLIC_BASE_URL`.
See [connection troubleshooting](../operations/troubleshooting.md#api-startup-fails-while-connecting-to-redis)
when containers cannot reach Redis.

### Direct initial bootstrap

The same freshness check applies when invoking Python directly through Compose:

```bash
coyote_compose run --rm --no-deps -it api sh -c '
  exec python3 scripts/bootstrap/bootstrap_database.py \
    --db "$COYOTE4_DB" --identity-db "$IDENTITY_DB"
'
```

The Python command supports the same three module skip flags. It has no `--force`
option and never uses an existing account name as unauthenticated authorization.
Configured connections need write access to the selected destination databases.
Knowledgebase installation can use the deployment installer's maintenance URI
without granting routine API connections write privileges.

## Authenticated data maintenance

Use an existing `admin`, `sys_admin` or `superuser` account with the running API.
Module selection is mandatory; `--force` never implicitly selects every module.
Authentication defaults to `--provider local`, matching initial bootstrap accounts.
Select `--provider ldap` for an LDAP account; an email-shaped login does not select
the provider automatically.
Host invocations require the application and independent Python client installed
in the selected interpreter; follow [developer environment setup](../getting-started/developer-environment.md).
Alternatively run the command in the built API image, as shown below; no host
virtual environment is needed for that path.

```bash
bash install.sh data \
  --api-url https://coyote.example.org/coyote4 \
  --modules application knowledgebase
```

Without `--force`, populated catalog collections are skipped. To repair selected
bundled modules:

```bash
bash install.sh data \
  --api-url https://coyote.example.org/coyote4 \
  --modules application knowledgebase --force
```

Inside Compose, use `coyote_compose run --rm --no-deps -it api python3
-m deploy.installer data --api-url http://api:8001 --modules knowledgebase --force`.
The API's configured connection needs write privileges on each selected database.

The command requests a username and hidden password, signs in using
`POST /api/v1/auth/sessions`, and completes a required first-login password change
using `POST /api/v1/auth/password/change`. It signs in again with the new password
because password changes invalidate previous sessions. It then calls
`POST /api/v1/admin/installation/data` and revokes its session afterward.
Passwords are never command arguments or stored in credential files.

The write request is `{"modules":["application","knowledgebase"],"force":true}`.
The application service checks the authenticated administrator role and rejects
temporary-password sessions. Client actors, seed paths and arbitrary documents are
not accepted. Newly created seed records use the system creator; updates and API
audit events record the authenticated administrator.

| Module | Forced maintenance boundary |
| --- | --- |
| `identity` | Restore missing bundled permissions/roles and union missing grants into system roles. Preserve local grants, activation state, every user, membership and password. Account creation/reset uses the normal account administration workflow. |
| `application` | Repair bundled group labels/descriptions and add missing identities. Preserve group availability, center-owned scopes and custom records. Changed bundled query content is published as a new version with retained hash-linked history; retired-only scopes stay retired. |
| `knowledgebase` | Repair system-created bundled reference IDs and content-addressed diagrams. A bundled publication or surviving system provenance identifies recoverable initial batches; active external releases are preserved. Preserve unknown/unattributed records and unrelated gene/release IDs. |

Demo installation is a separate package operation. It is available only in a
guarded demo deployment and does not appear as a maintenance module on ordinary
deployments. See [demo installation](demo-installation.md) for its CLI and
permission-protected administration page.

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
  python3 -m deploy.installer.checks indexes-ready --scope application
```

Replace `application` with `knowledgebase` for separately scheduled reference index
maintenance. `--summary` prints counts and returns a nonzero status if any required
index remains missing or conflicting. Without it, the index command prints JSON.
`indexes` is a read-only precheck that permits missing indexes; `indexes-ready`
requires all selected indexes to be present. Neither check creates indexes.
No command automatically drops a conflicting index. Use the
[index maintenance runbook](../operations/maintenance-and-verification.md) for reviewed retirement.
