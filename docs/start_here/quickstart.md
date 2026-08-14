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

Coyote3 uses MongoDB 8.2. The application always connects through `MONGO_URI`.
That URI may point to a host-installed service, a managed service, or an
independently deployed Docker service.

---

## Step 2: Clone the repository

Clone the repository and create a local environment file.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3

# Create your local environment file
cp deploy/env/example.env .coyote3_dev_env
```

!!! note "Review the environment file"

    The example values are suitable as a starting point for the development
    Compose profile. Before starting the stack, review `MONGO_URI`, mounted data
    paths, and every secret value. Production deployments must provide their own
    generated secrets.

---

## Step 3: Initialize the database

Start or select a MongoDB instance first. Set `MONGO_URI` to an endpoint that
will be reachable from the API and worker containers. On Linux, the supplied
Compose files resolve `host.docker.internal` to the Docker host, so a
host-installed MongoDB can use that hostname. The supplied MongoDB Compose
definition is also an independent infrastructure deployment.

Run the database bootstrap from the repository checkout. It connects directly
to MongoDB; it does not start Coyote3 services, call the API, or ingest a
sample.

```bash
.venv/bin/python scripts/bootstrap_database.py \
  --mongo-uri "$MONGO_URI" \
  --db "${COYOTE3_DB:?COYOTE3_DB must be set}" \
  --username "<first-superuser-username>" \
  --email "<first-superuser-email>" \
  --password "<generate-a-unique-password>"
```

This creates the first local superuser and initializes empty `permissions`,
`roles`, `hgnc_genes`, and `vep_metadata` collections. It stops rather than
mixing data into a partially initialized governance database. To install the
synthetic ASP, ASPC, and ISGL demonstration catalog for a nonclinical local
environment, add `--with-demo-center`.

For a clinical deployment, import reviewed center-owned ASP, ASPC, and ISGL
definitions after startup through the managed admin interfaces or approved
collection-import procedure.

---

## Step 4: Start the stack

The application stack brings up:

- web
- API
- Redis

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

## Cleaning Up

When the development session is complete, stop the environment:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml -f deploy/compose/docker-compose.dev.yml down
```

### Next Steps

- Developers: [Local Development](local_development.md)
- Operations: [Deployment Guide](../operations/deployment_guide.md)
