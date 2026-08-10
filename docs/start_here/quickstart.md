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

## Step 3: Start the stack

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

## Step 4: Load seed data

Once the stack is running, create the first superuser, load the baseline collections, and ingest the demo DNA sample.

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_dev_env \
  --compose-file deploy/compose/docker-compose.dev.yml \
  --api-base-url "http://localhost:6801" \
  --admin-username "<first-superuser-username>" \
  --admin-email "<first-superuser-email>" \
  --admin-password "<generate-a-unique-password>" \
  --seed-file api/config/bootstrap/demo_center \
  --seed-data-pack api/config/bootstrap/rbac \
  --yaml-file demo_data/ingest/generic_case_control.yaml \
  --with-optional
```

This command:

1. checks the environment and seed inputs
2. starts the compose stack
3. bootstraps the first superuser
4. seeds the baseline collections
5. ingests the demo sample

Ingest references:

- Use [API / Sample YAML Guide](../api/sample_yaml.md) for the sample manifest contract.
- Use [API / Sample Input Files](../api/sample_input_files.md) for the raw VCF and JSON file formats behind the demo ingest bundle.

### Parameter Reference

| Parameter | Required | Description |
| --- | --- | --- |
| `--env-file <path>` | Yes | Path to the environment file (e.g. `.coyote3_dev_env`). |
| `--compose-file <path>` | Yes | Path to the Docker Compose file to use. |
| `--api-base-url <url>` | Yes | Base URL of the HTTP proxy or API service (e.g. `http://localhost:6801`). The scripts append `/api/v1/...`. |
| `--admin-username <name>` | Yes | Username for the first superuser account. |
| `--admin-email <email>` | Yes | Email address for the first superuser account. |
| `--admin-password <password>` | Yes | Password for the first superuser account. |
| `--with-mongo` | No | Enable the compose-managed MongoDB container (`with-mongo` profile). Use when `MONGO_URI` points to `coyote3_mongo`. |
| `--compose-profile <name>` | No | Activate an arbitrary Docker Compose profile. Can be repeated. |
| `--seed-file <path>` | No | Path to the center collection seed directory. Default: `api/config/bootstrap/demo_center`, which contains synthetic ASP, ASPC, and ISGL examples. |
| `--seed-data-pack <path>` | No | Path to the application RBAC catalog. Default: `api/config/bootstrap/rbac`. |
| `--use-default-seed-data-pack` | No | Shorthand for `--seed-data-pack api/config/bootstrap/rbac`. |
| `--yaml-file <path>` | No | YAML manifest for the demo sample ingest check. Default: `demo_data/ingest/generic_case_control.yaml`. |
| `--mongo-uri <uri>` | No | Override the `MONGO_URI` from the env file for the bootstrap step. |
| `--with-optional` | No | Include optional collections during seeding. |
| `--skip-existing` | No | Tolerate duplicate documents during seeding (enabled by default). |
| `--strict-no-retry` | No | Fail immediately on first seed error with no retry. Must be combined with `--skip-existing`. |
| `--teardown` | No | Tear down the compose stack (including volumes) after the run. Refused for production compose unless `COYOTE3_ALLOW_PROD_VOLUME_PRUNE=1` is set. |

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

You should see the demo DNA sample in the sample list.

For direct API usage, create a session with
`POST /api/v1/auth/sessions`. The API session token is returned as the
configured session cookie and may also be sent as
`Authorization: Bearer <token>` by API-only clients. See
[API Authentication](../api/authentication.md) for exact examples.

---

## Production-like local run

Use this when you want to test the production compose file locally with the Mongo container enabled.

```bash
scripts/center_first_run.sh \
  --env-file .coyote3_env \
  --compose-file deploy/compose/docker-compose.yml \
  --with-mongo \
  --api-base-url "http://localhost:5815" \
  --admin-username "<first-superuser-username>" \
  --admin-email "<first-superuser-email>" \
  --admin-password "<generate-a-unique-password>" \
  --seed-file api/config/bootstrap/demo_center \
  --seed-data-pack api/config/bootstrap/rbac \
  --yaml-file demo_data/ingest/generic_case_control.yaml \
  --with-optional
```

---

## Cleaning Up

When the development session is complete, stop the environment:

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml down
```

### Next Steps

- Developers: [Local Development](local_development.md)
- Operations: [Deployment Guide](../operations/deployment_guide.md)
