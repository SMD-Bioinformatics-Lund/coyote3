# First installation

Follow these steps in order from the repository root, in the same Bash shell.
This procedure builds the production images, prepares storage and networking,
installs the database baseline, starts the application, and completes the first
sign-in. The bootstrap command runs inside the API image; a host Python virtual
environment is not required for this procedure.

For an installation that is already running, do not repeat bootstrap to troubleshoot
the UI. Start at step 9 to check service status and the browser URL.

## 1. Check prerequisites

Have the following available before proceeding:

- A checkout of the reviewed application release.
- Docker Engine and Docker Compose v2, accessible to the deploying account.
- Host Python 3.12 or later for the deployment wrapper, plus Bash and `curl`.
- An existing MongoDB deployment, or permission to provision one using step 6.
  Application and identity writes require a writable replica-set primary.
- Distinct application, identity, knowledgebase and BAM database names and the
  required database credentials. Preserve an existing knowledgebase when installing
  a new application database.
- Permission to create the configured host storage paths, or a host administrator
  who can prepare them with the configured container UID/GID.

Install missing prerequisites before continuing. Use the instructions for the
host's operating system; installing software is separate from configuring Coyote3.

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

MongoDB has an independent lifecycle. Step 6 provides Docker and host-installed
paths before the database bootstrap in step 8. An existing healthy replica set
needs verification, not reinitialization. Never substitute `localhost` in a
container URI for a database on the host: it identifies the container itself.

## 2. Select the deployment files

Choose the environment file and Compose project name once. Subsequent commands
reuse these shell variables.

For the prepared SMD deployment:

The [environment file](../configuration/environment-file.md) is the private
`NAME=value` configuration selected by `--env-file`. Its
[key reference](configuration-reference.md#environment-variable-reference) lists
required values and exact defaults. `COYOTE_ENV_FILE` and `COYOTE_PROJECT` below
are shell helper variables selecting the file and existing deployment name.

```bash
COYOTE_ENV_FILE="$PWD/.smd_configs/production.env"
COYOTE_PROJECT="coyote3-smd-prod"
```

For another center, select a private persistent location instead:

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

Edit this file before continuing. The SMD file already contains generated secrets
and local deployment values; retain those rather than copying over it.

## 3. Review environment and URL settings

Set or confirm these values in the selected environment file:

| Settings | Required decision |
| --- | --- |
| `ENV_NAME` | Use `production` for the production image and runtime profile. |
| Four MongoDB URI settings | Set `COYOTE3_MONGO_URI`, `IDENTITY_MONGO_URI`, `KNOWLEDGEBASE_MONGO_URI`, and `BAM_MONGO_URI` to endpoints reachable from containers. |
| Four database names | Set distinct `COYOTE3_DB`, `IDENTITY_DB`, `KNOWLEDGEBASE_DB`, and `BAM_DB`. |
| Secrets | Replace template values for `SECRET_KEY`, `INTERNAL_API_TOKEN`, `PASSWORD_TOKEN_SALT`, and `REDIS_PASSWORD` with separate random values. |
| `COYOTE3_APP_NETWORK` | Choose the external Docker network name; step 6 creates it if absent. |
| `COYOTE3_DATA_HOST_ROOT`, `COYOTE3_LOGS_HOST_ROOT` | Absolute persistent host paths; step 7 prepares them. |
| `COYOTE3_UID`, `COYOTE3_GID` | Numeric container identity with access to those paths; defaults are `10001:10001`. |
| `COYOTE3_CENTER_CONFIG_HOST_DIR` | Absolute directory containing the four center files described in step 4. |
| `ORGANIZATION_NAME`, `LOCAL_TIME_ZONE` | Center identity and timezone. |
| Authentication and email | Select the intended authentication providers and configure SMTP before relying on email delivery. |

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

The prepared SMD files are under `.smd_configs/center/`; do not overwrite them.
For a new center, create the directory selected by
`COYOTE3_CENTER_CONFIG_HOST_DIR` and copy only missing example files. Substitute
the reviewed absolute directory in this command:

```bash
COYOTE_CENTER_DIR="/srv/coyote3/config/center"
mkdir -p "$COYOTE_CENTER_DIR"
for name in contact.toml clinical_vocabulary.toml clinical_query_policy.toml filter_flag_metadata.yaml; do
  if [ ! -f "$COYOTE_CENTER_DIR/$name" ]; then
    cp "api/config/center/$name" "$COYOTE_CENTER_DIR/$name"
  fi
done
```

Review each file before building or initializing the database:

| File | Review |
| --- | --- |
| [`contact.toml`](../configuration/contact-file.md) | Center name, department, support contacts and hours. |
| [`clinical_vocabulary.toml`](../administration/clinical-vocabulary.md) | Supported clinical vocabulary and file bindings. DNA caller metadata registries may remain empty. |
| [`clinical_query_policy.toml`](../configuration/clinical-query-policy-file.md) | Evidence models and scoped exceptions approved for the center. Example exceptions are not evidence of local clinical approval. |
| [`filter_flag_metadata.yaml`](../configuration/filter-flag-metadata-file.md) | Labels and explanations for actual pipeline flags. Caller-specific overrides may remain empty. |

Do not copy or edit `collections.toml`; it belongs to the application.
The container UID/GID must be able to read all four files. Configuration is mounted
read-only. ASP, ASPC, gene lists and reporting rules are database resources added
through the application after startup, in step 12.

## 5. Load the environment and define the Compose command

Source only the trusted private environment file that was reviewed above:

```bash
set -a
. "$COYOTE_ENV_FILE"
set +a

coyote_compose() {
  bash scripts/deployment/compose-with-version.sh \
    -p "$COYOTE_PROJECT" --env-file "$COYOTE_ENV_FILE" \
    -f deploy/compose/docker-compose.yml "$@"
}
```

Use `coyote_compose` for every command below. This keeps the project name,
environment file, image version and base production Compose file consistent.
This command controls application services only; step 6 uses a separate command
if Docker MongoDB is selected. No development overlay is used. The
[Compose file reference](../configuration/compose-files.md) explains the base file,
overrides, mounts, networks and what changes require a rebuild.
If you edit environment settings later, source the file again before continuing;
exported shell values take precedence over Compose's environment-file values.

## 6. Create the application network

The application uses an external Docker network. Create it before bootstrap or
startup; Compose does not create an external network automatically:

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

Complete **one** path below before proceeding to step 7. The examples create a
single-member replica set, which supports transactions but has no failover.
For a center-managed multi-member or sharded deployment, retain its existing
configuration and obtain the connection/grant details from its database operator.

| Database location | Follow | Application connection |
| --- | --- | --- |
| Dedicated Docker MongoDB | Option A | `mongo-app:27017` on the application network. |
| MongoDB installed on the Linux/WSL host | Option B | A stable hostname reachable from both the host and API/worker containers. |
| Already managed and writable replica set | Verify primary and grants, then step 7 | Operator-provided URI and replica-set name; do not run initialization commands. |

A local service on `27017` and SSH tunnels on `28802`/`28803` are different
endpoints. Keep their URIs separate. Never initialize a tunnel destination as
part of local setup, and do not use a local MongoDB data directory for a container.

### Option A: Dedicated Docker MongoDB

**A1. Prepare its private server environment.** This is separate from the
application file; see [server settings](configuration-reference.md#environment-variable-reference).
Choose a private filename and a distinct infrastructure project:

```bash
COYOTE_MONGO_ENV_FILE="$(dirname "$COYOTE_ENV_FILE")/mongo-server.env"
COYOTE_MONGO_PROJECT="${COYOTE_PROJECT}-mongo"
if [ ! -f "$COYOTE_MONGO_ENV_FILE" ]; then
  (umask 077; cp deploy/env/example.mongo-server.env "$COYOTE_MONGO_ENV_FILE")
fi
chmod 600 "$COYOTE_MONGO_ENV_FILE"
```

Edit that file before running the following commands:

| Setting | Required value or decision |
| --- | --- |
| `COYOTE3_APP_NETWORK` and the four `*_DB` names | Match the application file exactly for this instance's initial grants. |
| `MONGO_ROOT_USERNAME`, `MONGO_ROOT_PASSWORD` | Separate administrative credentials; replace placeholders. |
| `MONGO_APP_USER`, `MONGO_APP_PASSWORD` | Runtime account credentials; replace placeholders. |
| `MONGO_UID`, `MONGO_GID` | Numeric IDs owning database storage; select an approved host account, for example the output of `id -u` / `id -g`. |
| `COYOTE3_MONGO_DATA_HOST_ROOT` | Dedicated persistent data directory, never a running local mongod's dbPath. |
| `COYOTE3_MONGO_KEYFILE_HOST_PATH` | Private file for member authentication; preserve an existing keyfile. |
| `MONGO_REPLICA_SET_NAME` | `coyote3-rs` for this example. |
| `MONGO_REPLICA_MEMBER_HOST` | `mongo-app:27017` for application clients on this Docker network. |
| `COYOTE3_MONGO_BIND_ADDRESS`, `COYOTE3_MONGO_PORT` | `127.0.0.1` and an unused host port. Use `27018`, for example, when local MongoDB already occupies `27017`. Internal clients still use `mongo-app:27017`. |

The single-instance path keeps four distinct logical databases on this server.
Do not enable `mongo-kb` unless a separately operated knowledgebase instance is
intended; its additional settings and commands are in the
[split-instance reference](../architecture/mongodb-topology.md#optional-docker-mongodb).

**A2. Prepare new storage and a keyfile.** Run this for a new deployment's paths.
If storage already contains data, preserve its owner/keyfile and use the existing
server's recovery or upgrade procedure instead of repeating first-time setup.
The subshell keeps server settings out of the application environment:

```bash
(
  set -a
  . "$COYOTE_MONGO_ENV_FILE"
  set +a
  sudo install -d -o "$MONGO_UID" -g "$MONGO_GID" -m 0700 "$COYOTE3_MONGO_DATA_HOST_ROOT"
  sudo install -d -m 0700 "$(dirname "$COYOTE3_MONGO_KEYFILE_HOST_PATH")"
  if ! sudo test -e "$COYOTE3_MONGO_KEYFILE_HOST_PATH"; then
    sudo sh -c 'set -C; umask 077; openssl rand -base64 756 > "$1"' sh "$COYOTE3_MONGO_KEYFILE_HOST_PATH"
    sudo chown "$MONGO_UID:$MONGO_GID" "$COYOTE3_MONGO_KEYFILE_HOST_PATH"
    sudo chmod 0400 "$COYOTE3_MONGO_KEYFILE_HOST_PATH"
  fi
)
```

**A3. Start only MongoDB and initialize its replica set.** The helper loads the
server environment inside a subshell so exported application values cannot
silently override server-file settings:

```bash
mongo_compose() (
  set -a
  . "$COYOTE_MONGO_ENV_FILE"
  set +a
  docker compose -p "$COYOTE_MONGO_PROJECT" --env-file "$COYOTE_MONGO_ENV_FILE" \
    -f deploy/compose/docker-compose.mongo.yml --profile mongo "$@"
)
mongo_compose config --quiet
mongo_compose up -d --wait --wait-timeout 180 mongo
mongo_compose run --rm --no-deps mongo_init
mongo_compose ps
```

Continue only when the initializer reports `[ok] replica set is writable`.
The container health check confirms responsiveness; the initializer confirms
primary election. On failure inspect `mongo_compose logs --tail=100 mongo`;
do not delete storage to retry. The initializer preserves an existing replica
configuration rather than force-reconfiguring it.

**A4. Set the application URIs and prepare reference-data credentials.** For this
single instance, all four application URI settings point to:

```text
mongodb://APP_USER:URI_ENCODED_PASSWORD@mongo-app:27017/?authSource=admin&replicaSet=coyote3-rs
```

Replace the placeholders with the runtime account from the server file. Percent-encode
reserved characters in URI credentials. Database names remain the four separate
`*_DB` settings. Do not put the root account in the application environment.

The supplied runtime account has read/write access to application, identity and
BAM databases, but read-only knowledgebase access. Bootstrap needs a separate
knowledgebase maintenance account. Open an administrative shell (password prompted):

```bash
mongo_compose exec mongo sh -c 'exec gosu "$MONGO_UID:$MONGO_GID" mongosh "mongodb://127.0.0.1:27017/admin?directConnection=true" --username "$MONGO_INITDB_ROOT_USERNAME" --authenticationDatabase admin --password'
```

Run the maintenance-account block under **Credentials for bootstrap** below,
then exit `mongosh`. Continue at step 7 after reloading the application file.

### Option B: Host-installed MongoDB, including WSL

**B1. Inspect the intended local service.** Install the server/shell using the
links in step 1 if absent. For the official Ubuntu package, inspect its service:

```bash
sudo systemctl status mongod --no-pager
mongosh 'mongodb://127.0.0.1:27017/admin?directConnection=true'
```

If authentication is already enabled, add `--username YOUR_ADMIN --authenticationDatabase admin --password`.
In `mongosh`, run:

```javascript
printjson(db.adminCommand({ hello: 1 }));
printjson(db.adminCommand({ replSetGetConfig: 1 }));
```

A healthy existing primary reports `isWritablePrimary: true` **and** a replica-set
`setName`. A standalone can report writable without a `setName`; it still needs
conversion. For a healthy configured replica set, skip B2–B4 and retain its name,
member address and authentication. `NotYetInitialized` means initiation is needed;
`InvalidReplicaSetConfig` or a node that cannot recognize itself needs recovery,
not another `rs.initiate()` or deletion of the `local` database.
Back up existing standalone data and stop its writers before conversion.

**B2. Select a stable member hostname.** The example below uses
`mongo-host.example.internal`. Replace it with a name resolving to this server
from the server itself and from application containers. Use a private listener
reachable by those clients; `127.0.0.1` alone is insufficient for container access.

Check the host's resolution before adding the name to MongoDB configuration:

```bash
getent hosts mongo-host.example.internal
```

The result must identify this MongoDB host. Step 8 checks the same endpoint from
the application container; both perspectives must work.

For a native Docker Engine inside WSL, `host.docker.internal` is already mapped
through `host-gateway` in Coyote3's API/worker services. If choosing that name,
ensure it also resolves on WSL itself to the verified Docker host address; configure
an appropriate host entry if needed. Do not assume every WSL/Docker Desktop setup
uses `172.17.0.1`. Keep the hostname/listener stable across restarts. An existing
working SMD local replica set should be retained, not renamed by this example.

**B3. Prepare authentication and edit the existing mongod configuration.** For a
new Ubuntu package installation, the service account is normally `mongodb`.
Confirm it before setting ownership. Create a keyfile only if none exists:

```bash
sudo install -d -o mongodb -g mongodb -m 0700 /etc/mongodb
if ! sudo test -e /etc/mongodb/keyfile; then
  sudo sh -c 'set -C; umask 077; openssl rand -base64 756 > /etc/mongodb/keyfile'
  sudo chown mongodb:mongodb /etc/mongodb/keyfile
  sudo chmod 0400 /etc/mongodb/keyfile
fi
sudoedit /etc/mongod.conf
```

Merge these keys into the existing YAML sections; do not duplicate section names
or replace `storage.dbPath`, logging settings, TLS settings or existing credentials:

```yaml
net:
  port: 27017
  bindIp: 127.0.0.1,mongo-host.example.internal
replication:
  replSetName: coyote3-rs
security:
  authorization: enabled
  keyFile: /etc/mongodb/keyfile
```

| Setting | Meaning |
| --- | --- |
| `net.bindIp` | Local interfaces to listen on; the example hostname must resolve to this host. |
| `replication.replSetName` | Replica-set identity, matched by `rs.initiate` and application URI options. |
| `security.authorization` | Requires authenticated client permissions. |
| `security.keyFile` | Private member-authentication secret, readable only by the MongoDB service owner. |

These steps describe single-node preparation using keyfile authentication. Apply
the center's TLS/member-authentication policy for clinical infrastructure. See
MongoDB's [standalone conversion](https://www.mongodb.com/docs/v8.0/tutorial/convert-standalone-to-replica-set/)
and [authenticated replica-set setup](https://www.mongodb.com/docs/manual/tutorial/deploy-replica-set-with-keyfile-access-control/).

```bash
sudo systemctl restart mongod
sudo systemctl status mongod --no-pager
```

If startup fails, inspect `sudo journalctl -u mongod -n 80 --no-pager` and correct
the reported setting/access problem before proceeding. For WSL without systemd,
configure its supported service manager first; do not start a second mongod on
the same data directory.

**B4. Initialize only an unconfigured replica set.** Connect locally as in B1.
Use an existing administrator if users already exist. With no users, MongoDB's
localhost exception permits initial replica-set and administrator creation.
Run once, substituting the hostname chosen in B2:

```javascript
rs.initiate({
  _id: "coyote3-rs",
  members: [{ _id: 0, host: "mongo-host.example.internal:27017" }]
});
```

Repeat `db.hello()` until `isWritablePrimary` is `true` and `setName` is
`coyote3-rs`. Do not repeat initiation while waiting for election. If there are
no users yet, create the first administrator on this primary with a hidden prompt:

```javascript
db.getSiblingDB("admin").createUser({
  user: "coyote3_root",
  pwd: passwordPrompt(),
  roles: [{ role: "root", db: "admin" }]
});
```

Store that administrative credential privately. Exit and reconnect with
`--username coyote3_root --authenticationDatabase admin --password` before creating
other users. Existing deployments retain their administrator; do not recreate it.

**B5. Create the runtime account for a new installation.** In the authenticated
shell, substitute the **exact four names from the application environment** below.
These are examples; changing the names later does not transfer grants:

```javascript
const applicationDb = "coyote3_prod";
const identityDb = "coyote3_identity_prod";
const knowledgebaseDb = "coyote3_knowledgebase";
const bamDb = "bam_prod";
db.getSiblingDB("admin").createUser({
  user: "coyote3_app",
  pwd: passwordPrompt(),
  roles: [
    { role: "readWrite", db: applicationDb },
    { role: "readWrite", db: identityDb },
    { role: "readWrite", db: bamDb },
    { role: "read", db: knowledgebaseDb }
  ]
});
```

For an existing account, have its administrator verify grants instead of repeating
`createUser`. Prepare the maintenance account below, then set all four application
URIs to the local server using the runtime account:

```text
mongodb://APP_USER:URI_ENCODED_PASSWORD@mongo-host.example.internal:27017/?authSource=admin&replicaSet=coyote3-rs
```

Use the existing set name if different. Do not point these local URIs at an SSH
tunnel. Do not use `directConnection=true` as a substitute for configuring a
reachable advertised member; normal application connections use replica discovery.

### Credentials for bootstrap

On each knowledgebase endpoint receiving bundled reference data, use an existing
approved maintenance identity or create a dedicated account while authenticated
as its administrator. Replace the database name with the selected `KNOWLEDGEBASE_DB`:

```javascript
db.getSiblingDB("admin").createUser({
  user: "coyote3_kb_maintenance",
  pwd: passwordPrompt(),
  roles: [
    { role: "readWrite", db: "coyote3_knowledgebase" },
    { role: "dbAdmin", db: "coyote3_knowledgebase" }
  ]
});
```

This account is for bootstrap/reference maintenance, not routine API connections.
Keep its URI in the center's secret store and enter it only for the bootstrap
command in step 8. Application and identity bootstrap use their configured
read/write accounts; knowledgebase runtime access remains read-only.

After editing application endpoints, reload the trusted file in the original shell:

```bash
set -a
. "$COYOTE_ENV_FILE"
set +a
```

Continue at step 7. Step 8 verifies connectivity from the API container before
installing any baseline data.

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
when the API image is used in step 8.

| Directory | Required state before application startup |
| --- | --- |
| `COYOTE3_DATA_HOST_ROOT` | Created by storage preparation if missing; writable by the container UID/GID. |
| `<data root>/coyote3_prod/reports` | Created automatically. |
| `<data root>/coyote3_prod/ingest_staging` | Created automatically. |
| `<data root>/coyote3_prod/copied_sample_files/yaml` | Created automatically, including parents. |
| `COYOTE3_LOGS_HOST_ROOT` | Created automatically; service log and spool subdirectories are created at runtime. |
| `COYOTE3_CENTER_CONFIG_HOST_DIR` | Already contains the four reviewed files from step 4. |
| Additional pipeline input directories | Already contain real pipeline files if mounted through a center override. |
| Database and backup storage | Provisioned separately; application preparation does not manage it. |

Existing files, ownership and permissions are retained. If a protected parent
prevents creation, an authorized host administrator can create the two roots:

```bash
sudo install -d -o "$COYOTE3_UID" -g "$COYOTE3_GID" -m 0750 "$COYOTE3_DATA_HOST_ROOT"
sudo install -d -o "$COYOTE3_UID" -g "$COYOTE3_GID" -m 0750 "$COYOTE3_LOGS_HOST_ROOT"
```

Then rerun storage preparation with an account able to create subdirectories for
the container identity. The wrapper does not invoke sudo automatically.
For deployments with a prepared host virtual environment, the additional
`center_preflight.sh` checks can be run now; they are not required to follow the
container-based bootstrap below.

## 8. Build images and install the database baseline

Build the application, frontend and documentation images:

```bash
coyote_compose build
```

Stop here if the build fails. The frontend embeds the URL prefix and other public
settings at build time; build only after selecting the values in step 3.

Validate the mounted center files using the built API image before any bootstrap
writes. This command checks configuration without connecting to MongoDB:

```bash
coyote_compose run --rm --no-deps -T api python3 -c '
from api.config.clinical_query_policy import load_clinical_query_policy
from api.config.loaders.filter_flags import load_filter_flag_metadata
from api.config.loaders.contact import load_contact_config
from api.config.paths import CONTACT_CONFIG_PATH
load_clinical_query_policy()
load_filter_flag_metadata()
load_contact_config(CONTACT_CONFIG_PATH, organization_name="Validation", public_base_url="", script_name="")
print("Center configuration valid")
'
```

Before bootstrap, verify all four endpoints from the API container, which uses
the same DNS, host mapping and credentials as the application. This command only
reads server state and reports endpoint labels, not credential-bearing URIs:

```bash
coyote_compose run --rm --no-deps -T api python3 -c '
import os
from pymongo import MongoClient
for key in ("COYOTE3_MONGO_URI", "IDENTITY_MONGO_URI", "KNOWLEDGEBASE_MONGO_URI", "BAM_MONGO_URI"):
    uri = os.environ.get(key) or os.environ["COYOTE3_MONGO_URI"]
    try:
        with MongoClient(uri, serverSelectionTimeoutMS=7000) as client:
            client.admin.command("ping")
            info = client.admin.command("hello")
            if not info.get("isWritablePrimary") or not (info.get("setName") or info.get("msg") == "isdbgrid"):
                raise RuntimeError("primary_required")
    except Exception as error:
        raise SystemExit(f"{key}: check connection, authentication and primary state ({type(error).__name__})") from None
    print(f"{key}: ready")
'
```

Resolve any failed check before continuing. A connection test does not prove write
grants; verify the account roles prepared in step 6. Enter the knowledgebase
maintenance URI at a hidden prompt. It uses the same endpoint and database as the
runtime knowledgebase connection, with the separate maintenance credentials:

```bash
read -rsp "Knowledgebase maintenance URI for bootstrap: " COYOTE_KB_BOOTSTRAP_URI
printf '\n'
test -n "$COYOTE_KB_BOOTSTRAP_URI"
```

Enter the real initial account details at the prompts:

```bash
read -r -p "Named administrator username: " COYOTE_ADMIN_USERNAME
read -r -p "Named administrator email: " COYOTE_ADMIN_EMAIL
read -r -p "Emergency superuser username: " COYOTE_SUPERUSER_USERNAME
read -r -p "Emergency superuser email: " COYOTE_SUPERUSER_EMAIL

coyote_compose run --rm --no-deps -it \
  -e KNOWLEDGEBASE_MONGO_URI="$COYOTE_KB_BOOTSTRAP_URI" api \
  python3 scripts/bootstrap/bootstrap_database.py \
  --db "$COYOTE3_DB" --identity-db "$IDENTITY_DB" \
  --sys-admin-username "$COYOTE_ADMIN_USERNAME" \
  --sys-admin-email "$COYOTE_ADMIN_EMAIL" \
  --username "$COYOTE_SUPERUSER_USERNAME" \
  --email "$COYOTE_SUPERUSER_EMAIL"
```

The API container receives the reviewed MongoDB endpoints, knowledgebase database
and mounted center files from Compose. This command initializes the selected
databases; it does not start the API server or its dependencies. Enter and confirm
two distinct temporary passwords at the hidden prompts, each at least 12 characters.
Use distinct usernames and email addresses. Do not place passwords in command history.

After successful bootstrap, run `unset COYOTE_KB_BOOTSTRAP_URI` to clear the
temporary shell value. The ordinary service environment retains the runtime reader URI.

Continue only after `[ok] database bootstrap completed`. If bootstrap fails,
resolve its reported configuration, transaction or connection error before startup.
Do not drop databases or reset an existing knowledgebase to retry.

Permissions, roles, and both accounts are committed together in one identity-database
transaction. MongoDB must support transactions, including a single-member replica set
for local development. Existing governance with a superuser is left unchanged;
partially initialized governance without a superuser is rejected. Reference and
optional demonstration collections are loaded separately, only when empty.

Installed documents are attributed to the normalized `--sys-admin-username` account
in their audit fields. Catalogs supporting `system_managed` are marked as system
records. Document versions start at `1`, including clinical rule content versions
and revisions and generated subpanel versions. Demonstration rule review and
publication metadata use the same administrator and installation time; these are
synthetic baselines, not evidence of clinical approval. External reference release
identifiers, such as VEP releases, retain their original values. Rerunning bootstrap
does not reset versions or attribution in populated collections.

| Data installed | Collection | Ownership and behavior |
| --- | --- | --- |
| System permissions | `permissions` | Shipped with Coyote3. Assign through roles; do not rename or delete. |
| System roles | `roles` | Shipped role baselines. Protected from ordinary editing, deactivation, and deletion. |
| Initial local accounts | `users` | One `sys_admin` and one `superuser`, with operator-supplied credentials. Both must change their password at first sign-in. Profiles, activation, and deletion are protected; password workflows and UI preferences remain available. |
| HGNC gene reference | `hgnc_genes` in `KNOWLEDGEBASE_DB` | Bundled reference snapshot loaded only when the collection is empty. |
| VEP metadata and diagrams | `vep_metadata`, `vep_diagrams` in `KNOWLEDGEBASE_DB` | Bundled metadata and diagram assets loaded only when the respective collection is empty. |

For a disposable demonstration environment, append `--with-demo-center`. This additionally installs synthetic ASP, ASPC, and ISGL records. These records are useful for interface and ingest validation; they are not approved clinical configuration.

## 9. Start services and verify the browser URL

```bash
coyote_compose up -d --wait --wait-timeout 180
coyote_compose ps
```

The command must complete successfully. API and Redis must be healthy; other
services must be running. If startup fails or a container restarts, inspect:

```bash
coyote_compose logs --tail=100 api redis proxy worker beat monitor
```

After successful startup, check the public routes:

```bash
COYOTE_BROWSER_URL="${PUBLIC_BASE_URL%/}${SCRIPT_NAME%/}"
curl --fail --show-error "$COYOTE_BROWSER_URL/api/v1/health"
curl --fail --show-error --output /dev/null "$COYOTE_BROWSER_URL/"
printf 'Open %s/ in the browser\n' "$COYOTE_BROWSER_URL"
```

For the local values in step 3, open **http://localhost:6802/coyote3/**.
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

With Redis available, inspect the application and security index contracts:

```bash
coyote_compose run --rm --no-deps -T api python3 scripts/database/manage_mongo_indexes.py plan
```

Review conflicts before proceeding. Create compatible missing indexes:

```bash
read -rsp "Knowledgebase maintenance URI for index creation: " COYOTE_KB_INDEX_URI
printf '\n'
test -n "$COYOTE_KB_INDEX_URI"
coyote_compose run --rm --no-deps -T \
  -e KNOWLEDGEBASE_MONGO_URI="$COYOTE_KB_INDEX_URI" api \
  python3 scripts/database/manage_mongo_indexes.py apply
unset COYOTE_KB_INDEX_URI
```

Use the maintenance identity prepared in step 6: index application includes
knowledgebase repositories, whose runtime reader cannot create indexes.
Do not continue with an empty URI. The command does not drop indexes. Resolve reported conflicts before admitting
clinical samples; do not retire an existing index without reviewing its purpose.

## 11. Complete first sign-in

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
| 4 | Select **Scopes** and target environments. | Base is included automatically. Register/reuse any active named subpanel definitions, refresh them and select the needed scopes. Their assay associations are created at activation. |
| 5 | Prepare **Gene lists** if filters will select them. | Each selected ISGL has the correct type, genes and assay/group/scope bindings. Leave this step empty if no list is required. |
| 6 | Use **Open rule builder** for the saved draft assay; test, review and publish its rules. | A compatible published assay/scope/analyte/language release exists and declares the intended report analyses. Return to setup and refresh rules. |
| 7 | Save **Configurations** for every selected scope/environment pair. | Each ASPC has supported analyses, filter defaults, eligible selected lists and compatible report settings. Base plus one named scope in two environments requires four ASPCs. |
| 8 | Resolve **Review** readiness errors and submit. Have the independent reviewer approve and activate. | Operational ASP, associations, staged ISGLs and ASPCs are committed together. Merely saving/submitting a draft does not enable ingest. |
| 9 | Verify user access and ingest an approved validation sample. | The intended ASPC resolves; evidence, tabs, gene filters, report preview, saved report and audit records behave as approved. Review any Base-fallback warning. |
| 10 | Publish public assay catalog content if needed. | The separate catalog approval workflow exposes the offering. It is not required to activate the assay or review its samples. |

**Order is conditional.** Shared subpanel definitions may be prepared before an
assay. ISGLs and reporting rules can be prepared in either order after their assay
and scope dependencies exist; both must be suitable before dependent ASPCs are
approved. Base needs no subpanel record. Unselected gene lists and public catalog
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
