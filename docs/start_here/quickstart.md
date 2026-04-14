# Quickstart: Run Coyote3 Locally

This guide takes you from a clean terminal to a working local Coyote3 instance with demo data.

---

## Step 1: Check Prerequisites

Make sure the required tools are installed. Coyote3 runs as a set of containerized services.

```bash
# Check required tools
git --version
docker --version
docker compose version
python3 --version
```

---

## Step 2: Clone The Repository

Clone the repository and create a local environment file. Coyote3 uses `.env` files for secrets and connection settings.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3

# Create your local environment file
cp deploy/env/example.dev.env .coyote3_dev_env
```

> [!NOTE]
> For a local run, the default values in `.coyote3_dev_env` are enough. In production, you should set `SECRET_KEY`, `INTERNAL_API_TOKEN`, and related secrets explicitly.

---

## Step 3: Start The Stack

Start the development stack. This brings up the API, web UI, MongoDB, and Redis.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

---

## Step 4: Load Seed Data

Once the stack is running, load the initial data and the demo sample.

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_dev_env \
  --compose-file deploy/compose/docker-compose.dev.yml \
  --api-base-url "http://localhost:6802" \
  --admin-email "admin@coyote3.local" \
  --admin-password "coyote3_demo_pass" \
  --seed-file tests/fixtures/db_dummy/all_collections_dummy \
  --yaml-file tests/data/ingest_demo/generic_case_control.yaml
```

This command does three things:
1. Creates the first local superuser.
2. Loads the demo configuration data.
3. Ingests the demo DNA sample.

---

## Step 5: Open The Application

Open your browser and navigate to:
**[http://localhost:6801](http://localhost:6801)**

*   **Login**: Use the credentials from Step 4.
*   **Check the dashboard**: You should see the demo DNA case.
*   **Check the API**: [http://localhost:6802/api/v1/health](http://localhost:6802/api/v1/health)

---

## Cleaning Up

When you are done with your session, you can spin down the environment:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml down
```

### Next Steps
*   **Developers**: Learn how to [set up for local coding](local_development.md) without Docker.
*   **Operations**: Review the [Enterprise Deployment Guide](../operations/deployment_guide.md).
