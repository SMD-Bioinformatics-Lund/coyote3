# Quickstart: Run Coyote3 Locally

This guide starts a local Coyote3 stack and loads the demo data.

---

## Step 1: Check Prerequisites

Make sure the required tools are installed.

```bash
# Check required tools
git --version
docker --version
docker compose version
python3 --version
```

---

## Step 2: Clone The Repository

Clone the repository and create a local environment file.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3

# Create your local environment file
cp deploy/env/example.dev.env .coyote3_dev_env
```

> [!NOTE]
> For local development, the default values in `.coyote3_dev_env` are enough.
> For production, set all secrets explicitly.

---

## Step 3: Start The Stack

Start the development stack. This brings up:
- web
- API
- local MongoDB
- Redis

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

---

## Step 4: Load Seed Data

Once the stack is running, create the first superuser, load the baseline collections, and ingest the demo DNA sample.

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_dev_env \
  --compose-file deploy/compose/docker-compose.dev.yml \
  --api-base-url "http://localhost:6802" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@coyote3.local" \
  --admin-password "Coyote3.Admin" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

This command:
1. checks the environment and seed inputs
2. starts the compose stack
3. bootstraps the first superuser
4. seeds the baseline collections
5. ingests the demo sample

---

## Step 5: Open The Application

Open:
- UI: [http://localhost:6801](http://localhost:6801)
- API health: [http://localhost:6802/api/v1/health](http://localhost:6802/api/v1/health)

Login with:
- username: `admin.coyote3`
- email: `admin@coyote3.local`
- password: `Coyote3.Admin`

You should see the demo DNA sample in the sample list.

---

## Prod-Like Local Run

Use this when you want to test the production compose file locally with the Mongo container enabled.

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml \
  --compose-profile with-mongo \
  --api-base-url "http://localhost:5818" \
  --admin-username "admin.coyote3" \
  --admin-email "admin@coyote3.local" \
  --admin-password "Coyote3.Admin" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --seed-data-pack tests/data/seed_data \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml \
  --with-optional
```

---

## Cleaning Up

When you are done with your session, you can spin down the environment:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml down
```

### Next Steps
- Developers: [Local Development](local_development.md)
- Operations: [Deployment Guide](../operations/deployment_guide.md)
