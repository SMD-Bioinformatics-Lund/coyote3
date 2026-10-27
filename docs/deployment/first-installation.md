# First installation

Follow these steps in order from the repository root, in the same Bash shell.
This procedure builds the production images, prepares storage and networking,
installs the database baseline, starts the application, and completes the first
sign-in. The bootstrap command runs inside the API image; a host Python virtual
environment is not required for this procedure.

For an installation that is already running, do not repeat bootstrap to troubleshoot
the UI. Start at **step 9** to check service status and the browser URL.

## 1. Check prerequisites

MongoDB authentication is optional; installation warns and continues for
unauthenticated connections. Application login and role permissions remain required.
Database-level audit protection requires authenticated, collection-scoped runtime permissions.
Fresh bundled MongoDB instances receive the protected audit indexes and custom role
from the initializer. Existing and externally managed instances require the
[runtime role upgrade](../operations/audit-and-logging.md#runtime-database-privileges)
when database-level audit protection is enabled. Use a separate maintenance
principal for that upgrade; the installer does not elevate runtime credentials.
Add `--identity-maintenance-uri-file /protected/identity-maintenance-uri` to the
normal installer command to apply the upgrade within the same invocation.

Have the following available before proceeding:

- A checkout of the reviewed application release.
- Docker Engine and Docker Compose v2, accessible to the deploying account.
- Host Python 3.12 or later for the deployment wrapper, plus Bash and `curl`.
- An existing MongoDB deployment, or permission to provision one using **step 6**.
  Application and identity writes require a writable replica-set primary.
- Explicit application, identity, knowledgebase and BAM database names and the
  required database credentials. Names must be distinct when they use the same
  endpoint; independent endpoints can use the same logical name. Preserve an existing knowledgebase when installing
  a new application database.
- Permission to create the configured host storage paths, or a host administrator
  who can prepare them with the configured container UID/GID.

Install missing prerequisites before continuing. Use the instructions for the
host's operating system; installing software is separate from configuring Coyote3.

The normal installer builds and installs the application wheel inside Docker.
No host virtual environment, prebuilt SDK wheel or `.release/sdk` directory is
required. The installer defaults `GIT_COMMIT` to the checkout's current commit.
Host commands use `PYTHON_BIN` when supplied; otherwise they select the repository's
`.venv/bin/python` if supported, then a supported system interpreter. The selected
interpreter must be Python 3.12 or later. This also applies after `sudo` or `runuser`
changes `PATH`. `tomllib` is included with supported Python versions; do not install
a separate package to compensate for an older host interpreter.
Release CI can select the separate
[verified-artifact build](../sdk/compatibility.md#build-and-record-an-application-release)
using `deploy/compose/docker-compose.release.yml` as an additional overlay.

| Software | Needed for | Installation instructions |
| --- | --- | --- |
| Git | Obtaining and updating the reviewed checkout | [Git installation](https://git-scm.com/install/linux). |
| Docker Engine, Buildx and Compose v2 or later | Building images and running services | [Docker Engine](https://docs.docker.com/engine/install/), [Ubuntu packages](https://docs.docker.com/engine/install/ubuntu/), [Compose plugin](https://docs.docker.com/compose/install/linux/). Install the Buildx and Compose plugins with the Engine. |
| Python 3.12 or later | Host deployment wrapper and directory preparation | [Python downloads](https://www.python.org/downloads/). The API's Python version is supplied by its image. |
| Bash, curl and OpenSSL | Shell procedures, HTTP checks and keyfile generation | Install the distribution packages `bash`, `curl`, `openssl`; [curl packages](https://curl.se/download.html), [OpenSSL releases](https://openssl-library.org/source/). |
| MongoDB server | Only for the host-installed option | [MongoDB Community installation on Ubuntu](https://www.mongodb.com/docs/manual/administration/install-community-linux/?linux-distro=ubuntu&linux-method=pkg). Docker users use the image pinned in the MongoDB Compose file. |
| `mongosh` | Local MongoDB preparation and administrative checks | [MongoDB Shell installation](https://www.mongodb.com/docs/mongodb-shell/install/). The supplied MongoDB image includes it. |
| MongoDB Database Tools | Host-run backup/restore commands | [Database Tools installation](https://www.mongodb.com/docs/database-tools/installation/). The repository's container-based backup command supplies its own tools. |

For Windows development, first [install WSL 2](https://learn.microsoft.com/en-us/windows/wsl/install).
Use one Docker installation strategy: an Engine in the Linux distribution or
[Docker Desktop with WSL integration](https://docs.docker.com/desktop/features/wsl/).
Do not add a second daemon to an already working setup. The commands below run
inside Bash on the Linux host/WSL distribution. Node.js and a host API virtual
environment are not required for this container-based installation.

Check the command-line tools:

```bash
docker version
docker compose version
docker buildx version
git --version
python3 --version
bash --version
curl --version
openssl version
```

If a command is missing or Docker cannot contact its daemon, complete the linked
installation and account-access steps before proceeding. Check `mongod --version`
and `mongosh --version` as well when choosing host-installed MongoDB.

MongoDB has an independent lifecycle. **Step 6** links to its separate Docker and
host provisioning procedure before the database bootstrap in **step 8**. An existing healthy replica set
needs verification, not reinitialization. Never substitute `localhost` in a
container URI for a database on the host: it identifies the container itself.

## 2. Select the deployment files

Choose the environment file and Compose project name once. Subsequent commands
reuse these shell variables.

The [environment file](../configuration/environment-file.md) is the private
`NAME=value` configuration selected by `--env-file`. Its
[key reference](configuration-reference.md#environment-variable-reference) lists
required values and exact defaults. `COYOTE_ENV_FILE` and `COYOTE_PROJECT` below
are shell helper variables selecting the file and existing deployment name.

Select a private persistent location outside the application checkout. The following
examples use `/srv/coyote3/config` and the Compose project name `coyote3-prod`:

```bash
COYOTE_ENV_FILE="/srv/coyote3/config/production.env"
COYOTE_PROJECT="coyote3-prod"
```

If the selected environment file does not exist, copy the template once:

```bash
if [ ! -f "$COYOTE_ENV_FILE" ]; then
  mkdir -p "$(dirname "$COYOTE_ENV_FILE")"
  (umask 077; cp deploy/env/example.env "$COYOTE_ENV_FILE")
fi
chmod 600 "$COYOTE_ENV_FILE"
```

Edit this file before continuing. If a deployment file already exists, review its
settings and retain its secrets rather than overwriting it with the template.

Record the ordered application overlays in this shell. Leave the array empty only
when the base file is the complete deployment definition:

```bash
COYOTE_COMPOSE_OVERLAYS=()
```

Production Redis TLS is optional. If selected, complete the
[certificate procedure](../operations/redis-tls.md), set `COYOTE3_REDIS_TLS_DIR` in
the production environment file, and add its overlay:

```bash
COYOTE_COMPOSE_OVERLAYS+=(deploy/compose/docker-compose.redis-tls.yml)
```

Keep this overlay out of development and staging. Append any approved private
storage overrides in their intended precedence order. The command helpers below
reuse this file list for bootstrap, validation and startup; record it for upgrades
and recovery. The base configuration uses authenticated plaintext Redis internally.

## 3. Review environment and URL settings

Set or confirm these values in the selected environment file:

| Settings | Required decision |
| --- | --- |
| `ENV_NAME` | Use `production` for the production image and runtime profile. |
| Four MongoDB URI settings | Set `COYOTE3_MONGO_URI` to a container-reachable endpoint. Set `IDENTITY_MONGO_URI`, `KNOWLEDGEBASE_MONGO_URI`, and `BAM_MONGO_URI` when a service needs a different connection; empty auxiliary settings inherit `COYOTE3_MONGO_URI`. Identity authentication is required either way. |
| Four database names | Set `COYOTE3_DB`, `IDENTITY_DB`, `KNOWLEDGEBASE_DB`, and `BAM_DB`; the selected namespaces must not overlap on the same endpoint. |
| Secrets | Replace template values for `SECRET_KEY`, `INTERNAL_API_TOKEN`, `PASSWORD_TOKEN_SALT`, and `REDIS_PASSWORD` with separate random values of at least 16 characters. Redis accepts letters, digits, underscores and hyphens. |
| `COYOTE3_APP_NETWORK` | Choose the external Docker network name; **step 6** creates it if absent. |
| `COYOTE3_DATA_HOST_ROOT`, `COYOTE3_LOGS_HOST_ROOT` | Absolute persistent host paths; **step 7** prepares them. |
| `COYOTE3_UID`, `COYOTE3_GID` | Numeric container identity with access to those paths; defaults are `10001:10001`. |
| `COYOTE3_CENTER_CONFIG_HOST_DIR` | Absolute directory containing the three center files described in **step 4**. |
| `ORGANIZATION_NAME`, `LOCAL_TIME_ZONE` | Center identity and timezone. |
| Authentication and email | Select the intended authentication providers and configure SMTP before relying on email delivery. |

The application template is a **development** example. Renaming it to
`production.env` does not change its contents. For a new production target, review
the database names and cookie name explicitly, for example:

```dotenv
ENV_NAME='production'
COYOTE3_DB='coyote3_prod'
IDENTITY_DB='coyote3_identity_prod'
KNOWLEDGEBASE_DB='coyote3_knowledgebases'
BAM_DB='bam_prod'
API_SESSION_COOKIE_NAME='coyote3_prod_api_session'
```

Use the center's actual reviewed names, not these examples, when databases already
exist. MongoDB users' grants must match those names. If provisioning the supplied
MongoDB stack, copy the same names into its separate server environment file.

For direct access through the included proxy on this local machine:

```dotenv
COYOTE3_PORT='6802'
SCRIPT_NAME='/coyote3'
PUBLIC_BASE_URL='http://localhost:6802'
COYOTE3_NGINX_PUBLIC_SCHEME='http'
```

This configuration serves **http://localhost:6802/coyote3/**.
`PUBLIC_BASE_URL` is the origin; do not include `/coyote3` in it.
`SCRIPT_NAME` supplies that path prefix. Use `SCRIPT_NAME=''` to serve at `/`.

**The included proxy listens on HTTP.** Setting
`COYOTE3_NGINX_PUBLIC_SCHEME='https'` changes forwarded scheme information and
security headers; it does not install a certificate or enable a TLS listener.
Do not use `https://localhost:6802` for the direct HTTP port.

For a center-facing HTTPS deployment, first provision the center's TLS ingress
with its certificate and route it to the application's HTTP proxy. Then set
`PUBLIC_BASE_URL` to the external HTTPS origin and `COYOTE3_NGINX_PUBLIC_SCHEME`
to `https`. The browser uses that external origin and `SCRIPT_NAME`, not the
internal HTTP listener. Select the actual ingress trust settings for that topology.

## 4. Prepare the center configuration directory

Create the directory selected by
`COYOTE3_CENTER_CONFIG_HOST_DIR` and copy only missing example files. Substitute
the reviewed absolute directory in this command:

```bash
COYOTE_CENTER_DIR="/srv/coyote3/config/center"
mkdir -p "$COYOTE_CENTER_DIR"
for name in contact.toml clinical_vocabulary.toml filter_flag_metadata.yaml; do
  if [ ! -f "$COYOTE_CENTER_DIR/$name" ]; then
    cp "config/examples/center/$name" "$COYOTE_CENTER_DIR/$name"
  fi
done
```

Review each file before building or initializing the database:

| File | Review |
| --- | --- |
| [`contact.toml`](../configuration/contact-file.md) | Center name, department, support contacts and hours. |
| [`clinical_vocabulary.toml`](../administration/clinical-vocabulary.md) | Fusion evidence terms and optional DNA caller metadata. Transcript selection belongs to the application; annotation wording is configured in reporting rules. |
| [`filter_flag_metadata.yaml`](../configuration/filter-flag-metadata-file.md) | Labels and explanations for actual pipeline flags. Caller-specific overrides may remain empty. |
| Optional [`report_presentation.toml`](../configuration/report-presentation-file.md) | Copy only if customizing empty-analysis messages. The installer validates it when present; omitted keys use application defaults. |

The container UID/GID must be able to read all three files. Configuration is mounted
read-only. ASP, ASPC, gene lists and reporting rules are database resources added
through the application after startup, in **step 12**.

## 5. Load the environment and define the Compose command

Source only the trusted private environment file that was reviewed above:

```bash
set -a
. "$COYOTE_ENV_FILE"
set +a

COYOTE_COMPOSE_ARGS=(-f deploy/compose/docker-compose.yml)
COYOTE_INSTALL_ARGS=(--compose-file deploy/compose/docker-compose.yml)
for compose_overlay in "${COYOTE_COMPOSE_OVERLAYS[@]}"; do
  COYOTE_COMPOSE_ARGS+=(-f "$compose_overlay")
  COYOTE_INSTALL_ARGS+=(--compose-file "$compose_overlay")
done

coyote_compose() {
  bash scripts/deployment/compose-with-version.sh \
    -p "$COYOTE_PROJECT" --env-file "$COYOTE_ENV_FILE" \
    "${COYOTE_COMPOSE_ARGS[@]}" "$@"
}
```

Use `coyote_compose` for every command below. This keeps the project name,
environment file, image version and base production Compose file consistent.
This command controls application services only; **step 6** uses a separate command
if Docker MongoDB is selected. No development overlay is used. The
[Compose file reference](../configuration/compose-files.md) explains the base file,
overrides, mounts, networks and what changes require a rebuild.
If you edit environment settings later, source the file again before continuing;
exported shell values take precedence over Compose's environment-file values.

## 6. Create the application network

The application uses an external Docker bridge network. A host administrator
provisions it before bootstrap or startup; the installer only inspects it.
Network creation is a separate infrastructure operation and can affect host routes
and Docker firewall rules. Choose a subnet that does not overlap the host, VPN or
other application networks. Compose does not create an external network automatically:

```bash
if ! docker network inspect "$COYOTE3_APP_NETWORK" >/dev/null 2>&1; then
  docker network create --driver bridge "$COYOTE3_APP_NETWORK"
fi
docker network inspect "$COYOTE3_APP_NETWORK" --format '{{.Name}} {{.Driver}}'
```

The final command must show the configured name and `bridge`. If the center
requires a reserved subnet, use its approved subnet with `docker network create`.
Keep an existing suitable network; do not delete or recreate it while services
are attached.

### Choose and prepare MongoDB

Before application bootstrap, complete [first-time MongoDB provisioning](mongodb-first-setup.md)
if the center needs a new database service. That guide contains the Docker and
host-installed branches, replica-set preparation, runtime users and restricted
knowledgebase maintenance credentials. Return here after its connectivity checks.

For an existing managed replica set, retain its configuration. Obtain the four
URI/database pairs and required runtime/maintenance grants from its operator; verify
all advertised replica members are reachable from API and both workers. Do not
reinitialize it or reuse another process's dbPath. Continue at **step 7** once the
application and identity databases are writable and reference-installation access
is available.

## 7. Prepare storage and validate Compose

Validate secrets, resolve the complete configuration and create missing application
directories without starting any service:

```bash
bash scripts/deployment/validate_env_secrets.sh --env-file "$COYOTE_ENV_FILE"
coyote_compose --prepare-directories config --quiet
```

Do not proceed if either command fails. Resolve missing values, missing center
files, invalid Compose settings or filesystem permissions first. This render checks
Compose structure; the API configuration loaders validate center-file contents
when the API image is used in **step 8**.

| Directory | Required state before application startup |
| --- | --- |
| `COYOTE3_DATA_HOST_ROOT` | Created by storage preparation if missing; writable by the container UID/GID. |
| `<data root>/coyote3_prod/reports` | Created automatically. |
| `<data root>/coyote3_prod/ingest_staging` | Created automatically. |
| `<data root>/coyote3_prod/copied_sample_files/yaml` | Created automatically, including parents. |
| `COYOTE3_LOGS_HOST_ROOT` | Created automatically; service log and spool subdirectories are created at runtime. |
| `COYOTE3_CENTER_CONFIG_HOST_DIR` | Already contains the three reviewed files from **step 4**. |
| Additional pipeline input directories | Already contain real pipeline files if mounted through a center override. |
| Database and backup storage | Provisioned separately; application preparation does not manage it. |

Existing files, ownership and permissions are retained. If a protected parent
prevents creation, an authorized host administrator can create the two roots:

```bash
sudo install -d -o "$COYOTE3_UID" -g "$COYOTE3_GID" -m 0750 "$COYOTE3_DATA_HOST_ROOT"
sudo install -d -o "$COYOTE3_UID" -g "$COYOTE3_GID" -m 0750 "$COYOTE3_LOGS_HOST_ROOT"
```

If the deploying account cannot create or assign directories for that UID/GID,
have a host administrator prepare the complete tree using the same resolved
Compose definition. The helper needs only the supported host interpreter, not
the installed API or SDK:

```bash
source scripts/deployment/python_runtime.sh
select_deployment_python "$PWD"
coyote_compose config --format json | \
  sudo -- "$PYTHON_BIN" scripts/deployment/prepare_host_directories.py
coyote_compose --prepare-directories config --quiet
```

This streams resolved settings directly to the helper; do not print or save them
in shared logs. Existing ownership and modes are not changed. Container access is
checked inside each bind mount, not through private host parents above its source.
The Docker daemon must still be able to mount the host source. The wrapper does
not invoke sudo automatically.
Deployments with a host virtual environment can run `center_preflight.sh` for
additional checks. The installer validates configuration inside the API container
and does not require a host virtual environment.

## 8. Build images and install the database baseline

Run the application installer after completing the environment, center configuration,
MongoDB and database-user prerequisites in steps 1–7. Use the same shell session
and the `COYOTE_ENV_FILE` and `COYOTE_PROJECT` values defined in **step 2**:

```bash
bash scripts/deployment/install_center.sh \
  --setup-center \
  --env-file "$COYOTE_ENV_FILE" \
  --project "$COYOTE_PROJECT" \
  "${COYOTE_INSTALL_ARGS[@]}"
```

The installer executes the following sequence:

1. Validate secrets and render the selected Compose configuration.
2. Validate the existing external bridge network and prepare host directories.
3. Build images, start Redis, and verify authenticated cache, task-broker and result-backend
   connections from a temporary API container. Validate mounted center configuration.
4. Verify all four MongoDB endpoints and inspect application/identity installation state.
5. On a fresh target only, prompt for initial accounts and install users, application
   catalogs, bundled knowledgebases and both starter demonstrations by default.
6. Check application, identity and BAM indexes, stop on conflicts, create compatible missing indexes, and
   verify that every required index is present before starting services.
7. Apply knowledgebase indexes separately when explicitly selected.
8. Start services with health waiting, display service status, and check the local proxy's
   health and browser routes.

Do not run the individual bootstrap or index commands in addition to this sequence.
The script does not provision MongoDB, initialize replica sets, create database users,
or create or repair Docker networks. Complete those prerequisites before running it.

> [!IMPORTANT]
> Redis must be reachable between containers on the application network. Its local
> health check alone does not prove this. A failed connectivity check stops installation
> before database bootstrap or application startup. Follow
> [Redis connection troubleshooting](../operations/troubleshooting.md#api-startup-fails-while-connecting-to-redis)
> to correct the host configuration before retrying.

Index checks report counts of present, missing and conflicting indexes. Missing
indexes are expected on a first installation. A conflict identifies the repository,
collection and index name; it is not resolved by dropping data or indexes automatically.
Use the index status command in **step 10** to inspect a conflicting contract.

> [!IMPORTANT]
> `--setup-center` includes bundled HGNC and VEP references. Populated reference
> collections are preserved. It does not import external knowledgebases such as
> CIViC, COSMIC or BRCA Exchange; follow their separate
> [import procedures](../reference/knowledgebases/README.md).

Knowledgebase-wide indexing remains a separate `--with-knowledgebase-indexes`
operation because large existing collections can take considerable time. Review
[required data](required-data.md) before clinical use; a successful installation
does not certify reference completeness or clinical readiness.

For individual operations, replace `--setup-center` with `--steps` and the required
reference flags. The
[installation operations reference](installation-operations.md) lists every stage,
default, prerequisite and standalone command.

### Existing data and repeated runs

| Detected state | Installer behavior |
| --- | --- |
| Application and identity databases contain no documents | Create accounts/RBAC, install application, knowledgebase and demo modules by default, then start services. Empty collections do not count as installed data. |
| The initial governance baseline exists, including before application catalogs are installed | Skip all initial data installation. Preserve existing data and continue index checks/startup. Missing modules require authenticated maintenance. |
| Only part of application/identity initialization is recognized | Stop before bootstrap or index writes. Inspect the target selection and initialization state; do not drop databases to retry. |
| Fresh bootstrap includes knowledgebase data | Populate empty bundled HGNC/VEP collections and preserve populated reference collections. |
| Conflicting indexes or an earlier step fails | Stop. No index is automatically dropped; completed operations are not rolled back or undone. |

Bootstrap rechecks that both application and identity targets are still empty
immediately before its writes. Run only one installer against a deployment at a time.
A failed bootstrap can leave partial data across databases; inspect it before an
explicit recovery operation. Rerunning the installer never resets populated databases.

Detection of an existing installation prevents reseeding. Release compatibility
requires the applicable
[upgrade maintenance](application-upgrades.md), including RBAC or query-rule
synchronization. Complete these operations separately; the installer does not run
data migrations.

### Prompts and options

Fresh reference installation uses the configured knowledgebase connection or the
maintenance URI from **step 6**, targeting the same endpoint and logical database.
Existing deployments skip initial data operations completely.

Fresh targets create the fixed local logins `coyote3.sysadmin` (`sys_admin`) and
`coyote3.superuser` (`superuser`). Bootstrap generates separate temporary passwords
and displays them once in a terminal table after account creation. Both accounts
require a password change at first sign-in. Existing accounts are not renamed or
reset, and their passwords are never redisplayed. Contact emails default to
`sysadmin@coyote3.invalid` and `superuser@coyote3.invalid`; set real distinct contact
addresses with the email options. Protect installer output containing the passwords.

For later additions or forced repairs, run `scripts/deployment/manage_data.py` with
explicit modules and an existing administrator's API login. It completes a required
password change and signs in again before adding data. The service checks the
`admin`, `sys_admin` or `superuser` role and records the authenticated operator.

| Option | Requirement and behavior |
| --- | --- |
| `--env-file FILE` | Required private deployment environment file. |
| `--project NAME` | Required Compose project name; retain the existing name for redeployment. |
| `--compose-file FILE` | Required; repeat for overlays in precedence order. |
| `--setup-center` | Complete first-center setup, also the default stage selection. Fresh installation includes users, catalogs, bundled references and demos. Preserves existing deployments. Cannot combine with `--steps`. |
| `--sys-admin-email EMAIL` | Optional initial system-administrator contact address. Login is fixed to `coyote3.sysadmin`. |
| `--email EMAIL` | Optional initial superuser contact address. Login is fixed to `coyote3.superuser`. |
| `--knowledgebase-maintenance-uri-file FILE` | Optional private URI file for fresh knowledgebase installation or selected knowledgebase indexes. Does not affect later API data maintenance. Protect it with restricted filesystem permissions. |
| `--identity-maintenance-uri-file FILE` | Explicit restricted runtime-role upgrade before validation, using a separate maintenance connection. It does not enable MongoDB authorization or create passwords. |
| `--skip-demo` | Disable the otherwise included connected DNA/RNA starter configuration and samples. |
| `--skip-knowledgebase` | Disable bundled reference installation. |
| `--skip-application` | Disable application catalogs; requires `--skip-demo`. |
| `--skip-users` | Disable initial accounts/RBAC; requires all three data modules to be skipped. |
| `--skip-build` | Use already-built images after confirming that they match the selected release and deployment settings. |
| `--steps LIST` | Comma-separated stages; default `network,directories,build,validate,bootstrap,indexes,start,health`. Executes selected stages in dependency order. |
| `--with-knowledgebase-indexes` | Opt in to knowledgebase index planning, creation and verification. Large collections can take considerable time. |

For separately prepared HGNC and Ensembl BioMart files, use the
[standalone gene installer](../operations/hgnc-gene-installation.md), including its
input-column and parameter reference. External knowledgebase importers have their
own parameters in the [knowledgebase guides](../reference/knowledgebases/README.md);
they are not selected by `--setup-center`.

Password values are not installer command-line options. Do not enable shell tracing
when handling credentials. The temporary Compose rendering is private and removed
on exit. The script never runs database drop, restore or reset operations.

### Installed application definitions and baseline

The single installer invocation above includes both demo workflows by default.
Do not run it a second time for this subsection. Select `--skip-demo` in that
invocation when a new center should start without synthetic demonstrations.

See [Installed defaults and demonstration configuration](../administration/installed-defaults.md)
for the complete group inventory, exact query-rule conditions, optional demo assays,
diagnoses, gene lists, report rules and default role responsibilities.

The image packages `clinical_capabilities.toml` and `clinical_query_defaults.toml`
under `src/coyote3/config/`, collection mappings at `api/config/collections.toml`,
and installation criteria at `api/bootstrap/catalogs/reference/clinical_query_seed.toml`.
These are application-owned; do not copy them into the editable center directory.

Fresh bootstrap installs system permissions and roles, one named `sys_admin`, one
emergency `superuser`, assay groups, query-rule publications, bundled HGNC/VEP data
and both connected starter demonstrations unless their skip flags are selected.
Automated creations are attributed to `system`, and document versions start at
1; external reference release identifiers retain their original values. Installation
metadata is not evidence of clinical review. Optional demonstration records are
synthetic and require separate clinical configuration before real use.

See [bootstrap data flow](bootstrap-data-flow.md) for ownership and transaction
boundaries. Successful installation includes index creation and service startup.
Verify browser access in **step 9**, then proceed to **step 11** for first sign-in.
Use **step 10** only for manual index inspection or troubleshooting.

## 9. Start services and verify the browser URL

The installer starts services and checks routes through the local proxy's published
port (`COYOTE3_PORT`) before reporting success and displays it as **Local application**.
The separately labelled **Public application** address comes from `PUBLIC_BASE_URL`;
for direct localhost access, use the same port in both
settings. External HTTPS ingress and DNS require separate browser verification.
Use the following commands to inspect service state and diagnose access failures:

```bash
coyote_compose ps
```

The installer must complete successfully. API and Redis must be healthy; other
services must be running. If startup fails or a container restarts, inspect:

```bash
coyote_compose logs --tail=100 api redis proxy worker maintenance-worker beat monitor
```

For a manual check of the public routes, run:

```bash
COYOTE_BROWSER_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME%/}"
curl --fail --show-error "$COYOTE_BROWSER_URL/api/v1/health"
curl --fail --show-error --output /dev/null "$COYOTE_BROWSER_URL/"
printf 'Open %s/ in the browser\n' "$COYOTE_BROWSER_URL"
```

For the local values in **step 3**, open **http://localhost:6802/coyote3/**.
Documentation is served at **http://localhost:6802/coyote3/docs-site/**.
A running container does not imply that the published port supports HTTPS.

| Symptom | Check and next action |
| --- | --- |
| HTTPS fails but HTTP works | The direct listener is HTTP. Use the HTTP URL or provision a separate TLS ingress; changing the public scheme variable alone does not enable TLS. |
| Connection refused | Confirm `proxy` is running and `ps` shows the configured host port published to port `8088`. Read startup errors before retrying. |
| `/` returns 404 while `/coyote3` works | A nonempty `SCRIPT_NAME` requires that prefix in the browser URL. |
| Page loads but assets or API calls return 404 | Confirm `SCRIPT_NAME`, reload the environment, then rebuild and recreate services using the commands below. |
| Proxy returns 502 or API is unhealthy | Inspect API and proxy logs and resolve the reported dependency or configuration failure. |

After correcting URL settings, reload the environment and rebuild/recreate the
services. Do not rerun bootstrap:

```bash
set -a
. "$COYOTE_ENV_FILE"
set +a
coyote_compose up -d --build --force-recreate --wait --wait-timeout 180
```

## 10. Review and apply the index plan

The installer performs this step before starting the application. The commands
below are for manual inspection and troubleshooting; do not repeat index application
after a successful installation without a specific maintenance need.

Inspect the application and security index contracts:

```bash
coyote_compose run --rm --no-deps -T api python3 scripts/database/manage_mongo_indexes.py plan
```

Review conflicts before proceeding. Create compatible missing indexes:

```bash
coyote_compose run --rm --no-deps -T api \
  python3 scripts/database/manage_mongo_indexes.py apply --scope application --summary
```

Knowledgebase indexing requires an explicit `--scope knowledgebase` and appropriate
maintenance credentials; see [installation operations](installation-operations.md).
The command does not drop indexes. Resolve reported conflicts before admitting
clinical samples; do not retire an existing index without reviewing its purpose.

## 11. Complete first sign-in

Sign in separately with each initial account. Coyote3 redirects to `/change-password`
before opening the workspace. Enter the current temporary password, a new password,
and its confirmation. The new password must differ from the current one and contain
at least 10 characters, including uppercase, lowercase, a number, and a symbol.
After the change, sign in again: previous sessions are invalidated.

Until the password changes, the API permits only identity/session inspection,
password change, and sign-out, including for the superuser. The API enforces
this restriction on every request.

Use the named system administrator for Application Controls and account operations.
Assign a clinical administrator for clinical configuration. Keep emergency credentials
under controlled access and test the recovery procedure. See
[administrative responsibilities](../administration/permissions-and-access.md#administrative-responsibilities).

## 12. Add the center's clinical configuration

Use **Admin > Assay setup** for each new assay. The application is running at this
point, but infrastructure and bootstrap alone do not create a clinically usable
assay. ASP means assay definition; ASPC means its scope/environment configuration;
ISGL means an analysis-specific in-silico gene list.

![Assay definition, approval and activation order](../assets/diagrams/resource-setup-order.svg)

| Order | Action in the application | Required result before continuing |
| --- | --- | --- |
| 1 | Assign the setup author, independent reviewer and clinical-rule roles/scopes. | Distinct eligible people can author and approve the setup and rules. A user cannot approve setup content they edited. |
| 2 | Create or select an active assay group. | The assay's parent group exists and is available. Reuse an existing suitable group. |
| 3 | Create and save the **Assay** step in Assay setup. | Stable ASP ID, group, DNA/RNA category, family, covered genes and expected/required input files are defined. This is a draft, not an ingest-ready ASP. |
| 4 | Select **Scopes** and target environments. | Base is included automatically. Register/reuse any active named diagnosis definitions, refresh them and select the needed scopes. Their assay associations are created at activation. |
| 5 | Prepare **Gene lists** if filters will select them. | Each selected ISGL has the correct type, genes and assay/group/scope bindings. Leave this step empty if no list is required. |
| 6 | Use **Open rule builder** for the saved draft assay; test, review and publish its rules. | A compatible published assay/scope/analyte/language release exists and declares the intended report analyses. Return to setup and refresh rules. |
| 7 | Save **Configurations** for every selected scope/environment pair. | Each ASPC has supported analyses, filter defaults, eligible selected lists and compatible report settings. Base plus one named scope in two environments requires four ASPCs. |
| 8 | Resolve **Review** readiness errors and submit. Have the independent reviewer approve and activate. | Operational ASP, associations, staged ISGLs and ASPCs are committed together. Merely saving/submitting a draft does not enable ingest. |
| 9 | Verify user access and ingest an approved validation sample. | The intended ASPC resolves; evidence, tabs, gene filters, report preview, saved report and audit records behave as approved. Review any Base-fallback warning. |
| 10 | Publish public assay catalog content if needed. | The separate catalog approval workflow exposes the offering. It is not required to activate the assay or review its samples. |

**Order is conditional.** Shared diagnosis definitions may be prepared before an
assay. ISGLs and reporting rules can be prepared in either order after their assay
and scope dependencies exist; both must be suitable before dependent ASPCs are
approved. Base needs no diagnosis record. Unselected gene lists and public catalog
entries do not block setup. A saved setup draft can be selected in the rule builder,
so an operational ASP need not be created separately first.

**Missing resources have different effects.** A missing active group blocks new
setup/ingest; a missing selected ISGL blocks configuration validation; a missing
compatible published rule or selected ASPC combination blocks setup activation.
During sample resolution, a missing named ASPC may fall back to Base in the same
environment with a warning; without either ASPC, ingest fails. Required missing
inputs reject ingest, whereas optional expected inputs produce missing-evidence
status. Creating a catalog entry cannot resolve any of these clinical prerequisites.

The [assay setup procedure](../administration/assay-setup.md#step-by-step-add-a-new-assay)
provides the form-level steps for this same workflow when adding later assays.
If the assay needs finding-selection exceptions, prepare and independently approve
[query rules](../administration/query-rules.md) after activation and before validation
ingest. Group rules may be published earlier; assay and named-diagnosis scopes need
their active registry records. Missing scoped query rules use the installed defaults.
These rules are separate from the reporting rules in step 6. Bootstrap installs
the [group and default query policies](../administration/query-rules.md#installation-and-storage)
and four dedicated query-rule roles. Review their effective criteria for each assay.
If automatic Tier III annotations are needed, set **Tumor-type wording** in the
assay's reporting-rule draft, then review and publish it. This optional text currently
requires Swedish reporting rules; leaving it unset does not prevent ordinary classification.
The [resource reference](../administration/clinical-configuration-resources.md)
describes each item's purpose, relationships and missing-prerequisite behavior.
JSON import/export remains subject to the same validation and permissions; it is
not a way to create unresolved references or bypass approval.

## 13. Establish backup and recovery

Before admitting clinical data, select a private absolute backup directory and
create a database archive using an account with approved backup permissions:

```bash
read -r -p "Absolute MongoDB backup directory: " COYOTE_BACKUP_DIR
read -rsp "MongoDB backup URI reachable from the backup container: " MONGO_BACKUP_URI
printf '\n'
bash scripts/database/mongo_backup_archive.sh \
  --mongo-uri "$MONGO_BACKUP_URI" --out-dir "$COYOTE_BACKUP_DIR" \
  --label initial-installation --docker-network "$COYOTE3_APP_NETWORK"
unset MONGO_BACKUP_URI
```

Repeat for every independent MongoDB deployment used by application, identity,
knowledgebase and BAM services. One archive covers multiple databases only if the
backup account can read all of them on that server. The tool checks gzip integrity
and records a checksum; successful dumping does not establish restore readiness.

Copy backups off-host. Preserve the private environment, center configuration,
deployment image identifiers, reports/ingest storage and Redis state through the
center's backup policy. Restore a backup into an isolated environment and verify
the result before accepting the installation. The
[backup and recovery runbook](../operations/backup-and-recovery.md) describes that
separate recovery operation; never test restoration over the installation being prepared.

## 14. Validate before clinical use

Complete these checks before clinical use:

1. Test each configured authentication provider with a representative account.
2. Confirm that delegated roles can access only their intended pages and operations.
3. Open the UI route audit and resolve every missing route, permission, or payload dependency.
4. Ingest one representative DNA sample and one representative RNA sample when both workflows are offered.
5. Review analysis tabs, filters, comments, classification, report preview, saved report, and deletion cleanup.
6. Create a backup and restore it into a disposable MongoDB instance.
7. Test the public catalog, API documentation, cookies, and forwarded headers through the production reverse proxy.

The [target-center acceptance guide](acceptance-checklist.md) provides the complete release record for these checks.
