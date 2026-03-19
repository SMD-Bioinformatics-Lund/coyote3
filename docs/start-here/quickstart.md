# Quickstart

## Prerequisites

```bash
git --version
docker --version
docker compose version
python3 --version
```

## Create local virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python --version
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Clone and configure

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3

cp deploy/env/example.prod.env .coyote3_env
cp deploy/env/example.dev.env .coyote3_dev_env
cp deploy/env/example.stage.env .coyote3_stage_env
cp deploy/env/example.test.env .coyote3_test_env
```

Edit env files and set real values for:

- `SECRET_KEY`
- `INTERNAL_API_TOKEN`
- `COYOTE3_FERNET_KEY`
- Mongo credentials and URI

## Start dev stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_dev_env \
  -f deploy/compose/docker-compose.dev.yml \
  up -d --build
```

## Start prod-style stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  up -d --build
```

Optional local mongo profile for prod compose:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_env \
  -f deploy/compose/docker-compose.yml \
  --profile with-mongo \
  up -d --build
```

## Start test stack

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_test_env \
  -f deploy/compose/docker-compose.test.yml \
  --profile tests \
  up -d --build
```

Optional UI container in test stack:

```bash
./scripts/compose-with-version.sh \
  --env-file .coyote3_test_env \
  -f deploy/compose/docker-compose.test.yml \
  --profile with-ui \
  up -d --build
```

## Verify services

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml ps
curl -f "http://${COYOTE3_HOST:-localhost}:${COYOTE3_DEV_API_PORT:-6816}/api/v1/health"
```

## Stop services

```bash
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.dev.yml down
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.test.yml down
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.stage.yml down
./scripts/compose-with-version.sh -f deploy/compose/docker-compose.yml down
```
