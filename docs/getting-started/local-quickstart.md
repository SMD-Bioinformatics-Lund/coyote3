# Run Coyote3 locally

This procedure starts the container-based development stack with the connected
synthetic DNA and RNA starter samples. It uses the same installer as a normal
first installation, with the development overlay. For host-run API development,
use the [developer environment](developer-environment.md).

## 1. Prepare tools and the checkout

Install Docker Engine/Compose v2, Git, Bash, curl and OpenSSL using the
[prerequisite links](../deployment/first-installation.md#1-check-prerequisites).
Check access to the existing Docker daemon before continuing.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3
cp deploy/env/example.env .coyote3_dev_env
chmod 600 .coyote3_dev_env
```

Copy the example only for a new environment; retain existing secrets and settings
when resuming a local installation.

## 2. Configure infrastructure and storage

Edit `.coyote3_dev_env`: replace every applicable placeholder secret, select four
distinct database names and configure each URI to a writable replica set with its
intended grants. MongoDB authentication and the restricted identity role are
required in development as well as production. Compose pins MongoDB 7.0.41 when the optional database services
are used. Database infrastructure has its own lifecycle; follow
[first-time provisioning](../deployment/mongodb-first-setup.md) for a new server.

For the URLs below, set:

```dotenv
ENV_NAME=development
COYOTE3_PORT=6801
SCRIPT_NAME=/coyote3_dev
PUBLIC_BASE_URL=http://localhost:6801/coyote3_dev
COYOTE3_APP_NETWORK=coyote3-dev-app-net
```

Choose data/log roots writable by the container identity. Prepare the external
center directory with its three reviewed files following
[center configuration preparation](../deployment/first-installation.md#4-prepare-the-center-configuration-directory).
An existing center directory is not replaced with bundled examples.

A host administrator must provision the selected external application network
before running the installer. Follow the [network procedure](../deployment/first-installation.md#6-create-the-application-network)
and use an approved non-overlapping subnet; retain an existing healthy network.
The installer does not create networks or repair host firewall/Docker settings.
Development excludes the production Redis TLS overlay and needs no Redis certificates.

## 3. Install and start

Run from the checkout after those prerequisites are ready:

```bash
bash scripts/deployment/install_center.sh \
  --env-file .coyote3_dev_env \
  --project coyote3-dev \
  --compose-file deploy/compose/docker-compose.yml \
  --compose-file deploy/compose/docker-compose.dev.yml
```

The installer builds images, validates mounted configuration and database/Redis
connectivity, installs a fresh baseline and starts the stack. It creates a distinct
superuser and system administrator with hidden temporary-password prompts, then
installs application catalogs, bundled references and `DEMO_STARTER_DNA` /
`DEMO_STARTER_RNA` by default. Creations use `system` provenance.

Use `--skip-demo` or `--skip-knowledgebase` when appropriate. Existing initialized
deployments preserve their data. A partial baseline stops for investigation rather
than being dropped. See [module defaults and authenticated repairs](../deployment/installation-operations.md).
A host `.venv` is not needed for this container-based bootstrap.

## 4. Open and verify

For the settings above:

- [Application](http://localhost:6801/coyote3_dev/)
- [API health](http://localhost:6801/coyote3_dev/api/v1/health)
- [API reference](http://localhost:6801/coyote3_dev/api/v1/docs)
- [Documentation](http://localhost:6801/coyote3_dev/docs-site/)

Sign in with an account created during bootstrap and complete its required password
change. Open both starter samples if demonstration installation was selected.
The stack includes API/frontend/docs/proxy, Redis, an ingest worker, a maintenance
worker, beat and the log/error monitor. A healthy Redis alone is not proof of API
or worker connectivity; retain the installer's checks and inspect service logs on failure.

Later data installation uses the authenticated maintenance command, rather than
repeating bootstrap. See [installation operations](../deployment/installation-operations.md).
For programmatic login, follow [API authentication](../api/authentication.md).

## Stop the local application

Retain the environment, project and both files:

```bash
./scripts/deployment/compose-with-version.sh \
  --env-file .coyote3_dev_env -p coyote3-dev \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml down
```

The separately operated MongoDB service and persistent bind mounts retain their
own lifecycle. Follow [development setup](developer-environment.md) for source tools
or [first installation](../deployment/first-installation.md) for the full operator procedure.
