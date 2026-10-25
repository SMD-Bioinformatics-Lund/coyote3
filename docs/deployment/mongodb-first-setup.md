# First-time MongoDB provisioning

Use this procedure only for a new MongoDB service or an explicitly planned conversion.
An existing healthy replica set needs connectivity and grant verification, not fresh
initialization. Upgrade and recovery procedures are in
[MongoDB deployment and recovery](mongodb-setup-and-recovery.md).

Complete [installation steps 1–6](first-installation.md) first, retaining the selected
`COYOTE_ENV_FILE`, `COYOTE_PROJECT` and sourced application settings in the same Bash
shell. The external application network must already exist. This page owns the
Docker and host provisioning branches; after either branch and the bootstrap grants,
return to [application storage preparation](first-installation.md#7-prepare-storage-and-validate-compose).

## Choose a database location

Complete **one** path below before proceeding to [installation step 7](first-installation.md#7-prepare-storage-and-validate-compose). The examples create a
single-member replica set, which supports transactions but has no failover.
For a center-managed multi-member or sharded deployment, retain its existing
configuration and obtain the connection/grant details from its database operator.

| Database location | Follow | Application connection |
| --- | --- | --- |
| Dedicated Docker MongoDB | Option A | `mongo-app:27017` on the application network. |
| MongoDB installed on the Linux/WSL host | Option B | A stable hostname reachable from both the host and API/worker containers. |
| Already managed and writable replica set | Verify primary and grants, then [installation step 7](first-installation.md#7-prepare-storage-and-validate-compose) | Operator-provided URI and replica-set name; do not run initialization commands. |

A local service on `27017` and SSH tunnels on `28802`/`28803` are different
endpoints. Keep their URIs separate. Never initialize a tunnel destination as
part of local setup, and do not use a local MongoDB data directory for a container.

## Option A: Dedicated Docker MongoDB

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
BAM databases, but read-only knowledgebase access. For initial reference installation,
prepare a maintenance identity as described below. Open an administrative shell
(password prompted):

```bash
mongo_compose exec mongo sh -c 'exec gosu "$MONGO_UID:$MONGO_GID" mongosh "mongodb://127.0.0.1:27017/admin?directConnection=true" --username "$MONGO_INITDB_ROOT_USERNAME" --authenticationDatabase admin --password'
```

Run the privilege commands under **Credentials for bootstrap** below,
then exit `mongosh`. Reload the application file and complete
[bootstrap credentials](#credentials-for-bootstrap) before returning to installation.

## Option B: Host-installed MongoDB, including WSL

**B1. Inspect the intended local service.** Install the server/shell using the
links in [installation prerequisites](first-installation.md#1-check-prerequisites)
if absent. For the official Ubuntu package, inspect its service:

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
conversion. For a healthy configured replica set with authentication enabled, skip
B2–B4 and retain its name, member address and authentication. A healthy replica set
without authentication still needs the authentication steps in B3–B4; preserve its
existing replica-set name, member address and data directory, and do not initialize
it again. Create administrative and restricted runtime accounts before enabling
authorization on an existing server. Changing application URIs alone does not enable
server-side authorization. Host configuration changes and service restarts require
operating-system administrator access. `NotYetInitialized` means initiation is needed;
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

The result must identify this MongoDB host. **Step 8** checks the same endpoint from
the application container; both perspectives must work.

For a native Docker Engine inside WSL, `host.docker.internal` is already mapped
through `host-gateway` in Coyote3's API/worker services. If choosing that name,
ensure it also resolves on WSL itself to the verified Docker host address; configure
an appropriate host entry if needed. Do not assume every WSL/Docker Desktop setup
uses `172.17.0.1`. Keep the hostname/listener stable across restarts. An existing
working local replica set should be retained, not renamed by this example.

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

**B5. Create the runtime account for a new installation.** Open the authenticated
shell from the repository root so it can read the generated role policy. Substitute
the **exact four names from the application environment** below. Install protected
audit indexes with the administrator account before granting runtime access.
These are examples; changing the names later does not transfer grants:

```javascript
const applicationDb = "coyote3_prod";
const identityDb = "coyote3_identity_prod";
const knowledgebaseDb = "coyote3_knowledgebase";
const bamDb = "bam_prod";
const policy = JSON.parse(require("fs").readFileSync(
  "deploy/compose/mongo-init/identity-role-policy.json", "utf8"
));
const identity = db.getSiblingDB(identityDb);
for (const index of policy.indexes) {
  const { collection, fields, ...options } = index;
  identity.getCollection(collection).createIndex(Object.fromEntries(fields), options);
}
identity.createRole({
  ...policy.identity_role,
  privileges: policy.identity_role.privileges.map(privilege => ({
    ...privilege,
    resource: { ...privilege.resource, db: identityDb }
  }))
});
db.getSiblingDB("admin").createUser({
  user: "coyote3_app",
  pwd: passwordPrompt(),
  roles: [
    { role: "readWrite", db: applicationDb },
    { role: policy.identity_role.role, db: identityDb },
    { role: "readWrite", db: bamDb },
    { role: "read", db: knowledgebaseDb }
  ]
});
```

For an existing account, have its administrator verify grants instead of repeating
`createUser` or `createRole`. Existing broad identity grants must be replaced with
the restricted policy using the procedure in
[audit protection](../operations/audit-and-logging.md). Prepare the maintenance
account below, then set all four application
URIs to the local server using the runtime account:

```text
mongodb://APP_USER:URI_ENCODED_PASSWORD@mongo-host.example.internal:27017/?authSource=admin&replicaSet=coyote3-rs
```

Use the existing set name if different. Do not point these local URIs at an SSH
tunnel. Do not use `directConnection=true` as a substitute for configuring a
reachable advertised member; normal application connections use replica discovery.

## Credentials for bootstrap

Bundled reference installation is included by default in fresh bootstrap and requires
knowledgebase write privileges. A separate maintenance URI can supply those privileges
to the initial bootstrap container while routine API connections remain read-only.

Later authenticated knowledgebase maintenance uses the running API's connection.
If that connection is read-only, grant the additional role while maintaining reference
data, substituting the actual
username, authentication database and knowledgebase name:

```javascript
db.getSiblingDB("admin").grantRolesToUser("coyote3_app", [
  { role: "readWrite", db: "coyote3_knowledgebase" }
]);
```

After reference installation, revoke this additional role if routine API access
should remain read-only; retain the existing `read` grant:

```javascript
db.getSiblingDB("admin").revokeRolesFromUser("coyote3_app", [
  { role: "readWrite", db: "coyote3_knowledgebase" }
]);
```

Knowledgebase indexing can use a separate approved maintenance account.
Replace the database name with the selected `KNOWLEDGEBASE_DB`:

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

This account is for index/reference maintenance, not routine API connections.
Keep its URI in a restricted secret file and supply that file through
`--knowledgebase-maintenance-uri-file` in [installation step 8](first-installation.md#8-build-images-and-install-the-database-baseline) for fresh knowledgebase installation
or selected knowledgebase indexes. This override leaves the API connection
unchanged. Application and identity bootstrap use their
configured read/write accounts.

After editing application endpoints, reload the trusted file in the original shell:

```bash
set -a
. "$COYOTE_ENV_FILE"
set +a
```

Continue at [installation step 7](first-installation.md#7-prepare-storage-and-validate-compose). **Step 8** verifies connectivity from the API container before
installing any baseline data.
