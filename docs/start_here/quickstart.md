# Quickstart: Run Coyote3 Locally

This guide starts a local Coyote3 stack and loads the demo data.

---

## Step 1: Check prerequisites

Make sure the required tools are installed.

```bash
# Check required tools
git --version
docker --version
docker compose version
python3 --version
```

Coyote3 uses MongoDB 8.2. App, identity, knowledgebase, and BAM databases have
independent URI settings. They may share one instance or use separate services.
The optional `mongo` and `mongo-kb` Docker profiles are described in
[MongoDB service topology](../architecture/mongodb_topology.md).

---

## Step 2: Clone the repository

Clone the repository and create a local environment file.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3

# Create your local environment file
cp deploy/env/example.env .coyote3_dev_env
```

> **Note: Review the environment file**
>
>
> The example values are suitable as a starting point for the development
> Compose profile. Before starting the stack, review `COYOTE3_MONGO_URI`, mounted data
> paths, and every secret value. Production deployments must provide their own
> generated secrets.
>

---

## Step 3: Initialize the database

Start or select a MongoDB instance first. Set `COYOTE3_MONGO_URI` to an endpoint that
will be reachable from the API and worker containers. On Linux, the supplied
Compose files resolve `host.docker.internal` to the Docker host, so a
host-installed MongoDB can use that hostname. The supplied MongoDB Compose
definition is also an independent infrastructure deployment.

Run the database bootstrap from the repository checkout. It connects directly
to MongoDB; it does not start Coyote3 services, call the API, or ingest a
sample.

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$COYOTE3_MONGO_URI" \
  --identity-mongo-uri "$IDENTITY_MONGO_URI" \
  --db "${COYOTE3_DB:?COYOTE3_DB must be set}" \
  --identity-db "${IDENTITY_DB:?IDENTITY_DB must be set}" \
  --sys-admin-username "center.operator" \
  --sys-admin-email "operator@example.org" \
  --username "<first-superuser-username>" \
  --email "<first-superuser-email>" \
  --password "<generate-a-unique-password>"
```

This creates one local superuser and one named system administrator, and initializes `permissions` and `roles`
in `IDENTITY_DB`, plus `hgnc_genes` and `vep_metadata` in `COYOTE3_DB`. It stops
rather than mixing data into a partially initialized identity database. To
install the synthetic ASP, ASPC, and ISGL demonstration catalog for a
nonclinical local environment, add `--with-demo-center`.

The omitted system-administrator password is requested through a hidden prompt;
omit `--password` to prompt for the emergency account too. Both accounts must
replace their temporary password on first sign-in before opening the workspace.
See [first installation](first_installation.md) for password requirements and
administrative responsibilities.

For a clinical deployment, import reviewed center-owned ASP, ASPC, and ISGL
definitions after startup through the managed admin interfaces or approved
collection-import procedure.

---

## Step 4: Start the stack

The application stack brings up:

- frontend;
- documentation;
- API;
- Celery worker;
- Celery beat scheduler;
- Redis; and
- reverse proxy.

Create the external application network named in the environment file before
starting the services:

```bash
set -a
. ./.coyote3_dev_env
set +a
docker network create \
  --driver bridge \
  --subnet 172.29.110.32/28 \
  --ip-range 172.29.110.32/28 \
  --gateway 172.29.110.33 \
  "$COYOTE3_APP_NETWORK"
```

Select another non-overlapping private subnet when this range is already routed
on the host. Compose uses the existing network and does not create or own it.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

---

## Step 5: Open the application

Open:

- UI: [http://localhost:6801/coyote3_dev/](http://localhost:6801/coyote3_dev/)
- API health: [http://localhost:6801/coyote3_dev/api/v1/health](http://localhost:6801/coyote3_dev/api/v1/health)
- Swagger UI: [http://localhost:6801/coyote3_dev/api/v1/docs](http://localhost:6801/coyote3_dev/api/v1/docs)
- Documentation site: [http://localhost:6801/coyote3_dev/docs-site/](http://localhost:6801/coyote3_dev/docs-site/)

Sign in with the username and password supplied to the bootstrap command. The
command deliberately requires these values at deployment time; no account
credentials are stored in the repository.

The application does not load a sample automatically. Use the ingest workspace
or a validated sample manifest when you are ready to load data.

For direct API usage, create a session with
`POST /api/v1/auth/sessions`. The API session token is returned as the
configured session cookie and may also be sent as
`Authorization: Bearer <token>` by API-only clients. See
[API Authentication](../api/authentication.md) for exact examples.

---

## Cleaning up

When the development session is complete, stop the environment:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.dev.yml down
```

### Next steps

- Developers: [Local Development](local_development.md)
- Operations: [Deployment Guide](../operations/deployment_guide.md)
- New installations: [First installation](first_installation.md)
