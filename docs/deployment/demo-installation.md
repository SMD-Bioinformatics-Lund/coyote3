# Local demonstration installation

The demonstration uses synthetic DNA and RNA samples in four dedicated databases:
`coyote4_demo`, `coyote4_demo_identity`, `coyote4_demo_knowledgebase` and
`coyote4_demo_bam`. Collection names and application workflows remain unchanged.
It uses the testing assay profile with the normal production security runtime;
authentication, permissions, CSRF protection and audit remain enabled.

The optional `coyote-demo` package supplies the datasets and installation commands.
Ordinary application images do not install it. Its API routes are available only
when the package is installed and demonstration mode is explicitly enabled.

## Isolation

The preparation command reads no deployment `.env` file and starts no services.
It creates a private state directory containing generated, distinct credentials.
Each subsequent command revalidates the settings and passes a restricted environment
to its child process. Keep this directory outside the source checkout and do not
commit or share its `settings.json` or `demo.env` files.

Demo processes reject ordinary database names, missing endpoint selections,
remote native endpoints, LDAP, SMTP and public knowledgebase lookups. Before
application storage initialization, a read-only MongoDB privilege check rejects
credentials with authority outside the four demo databases. Installation also
checks the repository clients used for the writes. Use dedicated local Redis;
Redis credentials and storage must not be shared with an ordinary deployment.

## Install the local tools

From the repository root, install the workspace, including the optional package:

```bash
uv sync --all-packages --group dev
```

Source checkouts provide the operational launcher at
`install.sh demo`. The individual `coyote-demo` wheel can also be
installed with its `api` extra alongside the selected core and server artifacts.
This guide assumes the checkout launcher and a local Docker Engine or local
MongoDB and Redis services.

## Docker installation

Prepare a new directory and inspect the Compose configuration without printing
credentials:

```bash
bash install.sh demo \
  --directory "$HOME/coyote-demo-local" prepare --mode docker --port 8089
bash install.sh demo \
  --directory "$HOME/coyote-demo-local" compose config
```

Start the prepared deployment when ready:

```bash
bash install.sh demo \
  --directory "$HOME/coyote-demo-local" compose up
```

The dedicated `deploy/demo/compose.yml` definition builds the
`demo_source` API target, a MongoDB replica set and the frontend. The separate
`demo` Docker target accepts verified release artifacts. Compose creates its own Redis,
internal database network, a frontend-only bridge and project-scoped volumes.
Only the frontend is published, at
`http://127.0.0.1:8089`; MongoDB, Redis and the API have no published ports.
There are no production overlays, external networks, runtime bind mounts or
ordinary environment files. The launcher explicitly selects the local Docker
socket and ignores the caller's Docker context and Compose variables.

The ingestion worker, maintenance worker and beat scheduler run the regular
application tasks. This includes durable ingest dispatch, audit delivery, report
artifact completion and dashboard refresh. Every background service validates
demo isolation before connecting to its queue. Directory watching and public
knowledgebase lookups remain disabled; unavailable SMTP does not send messages.

Bootstrap creates factory catalogs and initial accounts, then installs synthetic
starters. Existing accounts and passwords are preserved on subsequent starts.
The generated initial passwords are stored under `environment` in the private
`settings.json`: `COYOTE_DEMO_ADMIN_PASSWORD` for `coyote4.sysadmin`, and
`COYOTE_DEMO_SUPERUSER_PASSWORD` for `coyote4.superuser`. The application requires
the normal first-login password change.

Inspect or stop only this demo project:

```bash
bash install.sh demo \
  --directory "$HOME/coyote-demo-local" compose ps
bash install.sh demo \
  --directory "$HOME/coyote-demo-local" compose logs
bash install.sh demo \
  --directory "$HOME/coyote-demo-local" compose stop
```

Stopping preserves the demo volumes. The launcher intentionally provides no
volume-removal operation. A fresh demonstration uses a new state directory and
receives a new project identity and credentials.

## Native installation

Provide an authenticated local MongoDB replica set and a dedicated local Redis
instance. A separate loopback MongoDB instance is recommended. An existing local
instance is accepted only with a user named `coyote_demo`, authenticated against
`admin`, whose expanded privileges cover only the four demo databases. The user
needs `readWrite` and `dbAdmin` on each demo database. It must have no cluster,
all-database or ordinary application database grants. Do not supply a root or
production application credential.

Store the MongoDB URI and Redis URL in separate owner-only files (`chmod 600`).
The MongoDB URI must include `authSource=admin`, `replicaSet`,
`directConnection=true` and an explicit loopback host and port. The Redis URL must include username, password and an
explicit loopback port, with no database suffix; preparation assigns `/0`, `/1`
and `/2` to cache, queue and results. Passwords containing reserved URL characters
must be URL-encoded.

Prepare the native settings using those explicitly selected files:

```bash
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" prepare --mode native --port 8089 \
  --mongo-uri-file "$HOME/demo-mongo-uri" \
  --redis-url-file "$HOME/demo-redis-url"
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" run bootstrap
```

Run each process in its own terminal:

```bash
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" run api
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" run frontend
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" run worker
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" run maintenance-worker
bash install.sh demo \
  --directory "$HOME/coyote-demo-native" run beat
```

The frontend uses `127.0.0.1:8089` and proxies to the API at `127.0.0.1:8090`.
Install frontend dependencies with `npm --prefix frontend ci` before starting its
development server. Native reports, staging files and logs belong to the selected
state directory, including beat's scheduler and PID files; the backend refuses an ambient `.env` in its isolated runtime
directory. Stop these foreground processes with Ctrl-C. The launcher never starts,
stops, modifies or removes the operator-provided MongoDB or Redis services.

## Verification and limits

Unit and integration tests exercise target rejection, privilege rejection,
configuration isolation and package-owned synthetic workflows. Static tests also
check the dedicated Compose network, volume and endpoint declarations. A container
build and end-to-end installation are separate acceptance checks; preparation and
static tests alone do not establish that a deployment is running successfully.

The demonstration is for training and evaluation with synthetic data. It is not
a clinical validation dataset or an acceptance result for a clinical deployment.
