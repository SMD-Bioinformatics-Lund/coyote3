# Quickstart: Launching Coyote3 in 5 Minutes

This guide will take you from a clean terminal to a running instance of Coyote3 with demo data. Follow these steps to experience the platform's clinical interpretation environment immediately.

---

## Step 1: Environment Readiness

Ensure your machine has the necessary tools. Coyote3 is distributed as a series of containerized services.

```bash
# Check your toolbelt
git --version
docker --version
docker compose version
python3 --version
```

---

## Step 2: Clone and Preparation

Clone the repository and prepare your environment configuration files. Coyote3 uses `.env` files to manage secrets and connection strings across different stages.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3

# Create your local environment profile
cp deploy/env/example.dev.env .coyote3_dev_env
```

> [!NOTE]
> For this quickstart, the default values in the `.dev.env` file are sufficient for a local run. In a production environment, you would strictly manage the `SECRET_KEY` and `INTERNAL_API_TOKEN` here.

---

## Step 3: Ignition

We will stand up the **Development Stack**. This includes the API engine, the UI presentation layer, a MongoDB instance, and a Redis cache.

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

---

## Step 4: First-Run Bootstrap

Now that the infrastructure is breathing, we need to "seed" it with clinical logic (Assays, Gene Lists) and a demo sample case.

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

**What just happened?**
1.  **Identity Creation**: An admin account was created (`admin@coyote3.local`).
2.  **Logic Seeding**: Standard clinical categories and gene list definitions were imported.
3.  **Data Ingestion**: A demo DNA case was parsed, validated against contracts, and stored.

---

## Step 5: Mission Accomplished

Open your browser and navigate to:
**[http://localhost:6801](http://localhost:6801)**

*   **Login**: Use the credentials provided in Step 4.
*   **Explore**: You should see the "Demo DNA Case" on your dashboard.
*   **Verify**: Check the API health directly at [http://localhost:6802/api/v1/health](http://localhost:6802/api/v1/health).

---

## Cleaning Up

When you are done with your session, you can spin down the environment:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml down
```

### Next Steps
*   **Developers**: Learn how to [set up for local coding](local_development.md) without Docker.
*   **Operations**: Review the [Enterprise Deployment Guide](../operations/deployment_guide.md).
