# Run Coyote4 locally

This procedure starts the ordinary container-based development stack. It uses the
same installer as a normal first installation, with the development overlay.
For synthetic DNA/RNA samples, use the separate
[isolated demonstration installation](../deployment/demo-installation.md), which
has its own databases, credentials and storage and supports Docker or native processes.
For host-run API development,
use the [developer environment](developer-environment.md).

## 1. Prepare tools and the checkout

Install Docker Engine/Compose v2, Python 3.12 or later, Git, Bash, curl and OpenSSL using the
[prerequisite links](../deployment/first-installation.md#1-check-prerequisites).
Check access to the existing Docker daemon before continuing.

```bash
git clone git@github.com:SMD-Bioinformatics-Lund/coyote3.git
cd coyote3
cp deploy/env/example.env .coyote4_dev_env
chmod 600 .coyote4_dev_env
```

Copy the example only for a new environment; retain existing secrets and settings
when resuming a local installation.

## 2. Configure infrastructure and storage

Edit `.coyote4_dev_env`: replace every applicable placeholder secret, select four
database names with separate namespaces and configure each URI to a writable replica set with its
intended grants when authentication is enabled. Unauthenticated connections produce
a warning and do not block the installer. The restricted identity role is needed
for database-enforced audit protection, which is separate from application login.
Compose pins MongoDB 7.0.41 when the optional database services
are used. Database infrastructure has its own lifecycle; follow
[first-time provisioning](../deployment/mongodb-first-setup.md) for a new server.

For the URLs below, set:

```dotenv
ENV_NAME=development
COYOTE4_PORT=6801
SCRIPT_NAME=/coyote4_dev
PUBLIC_BASE_URL=http://localhost:6801
COYOTE4_APP_NETWORK=coyote4-dev-app-net
```

`PUBLIC_BASE_URL` is the origin only. `SCRIPT_NAME` adds the path prefix once.
Do not append `/coyote4_dev` to both settings. Use a Compose version that supports
the development overlay's `!reset` tags; `docker compose config` must parse both
files before installation.

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
bash install.sh deploy \
  --env-file .coyote4_dev_env \
  --project coyote4-dev \
  --compose-file deploy/compose/docker-compose.yml \
  --compose-file deploy/compose/docker-compose.dev.yml
```

The installer builds images, validates mounted configuration and database/Redis
connectivity, installs a fresh baseline and starts the stack. It creates a distinct
`coyote4.superuser` and `coyote4.sysadmin` with separate generated temporary passwords
displayed once in the terminal, then
installs application catalogs and bundled references by default. Synthetic
demonstrations belong to the separate demo installation. Creations use `system` provenance.

Use `--skip-knowledgebase` when appropriate. Existing initialized
deployments preserve their data. A partial baseline stops for investigation rather
than being dropped. See [module defaults and authenticated repairs](../deployment/installation-operations.md).
A host `.venv` is not needed for this container-based bootstrap.
Host Python 3.12 or later is still required by the deployment wrappers. The docs
service uses the documentation built into its image; no host `site/` directory or
host MkDocs installation is required for this procedure.

## 4. Open and verify

For the settings above:

- [Application](http://localhost:6801/coyote4_dev/)
- [API health](http://localhost:6801/coyote4_dev/api/v1/health)
- [API reference](http://localhost:6801/coyote4_dev/api/v1/docs)
- [Documentation](http://localhost:6801/coyote4_dev/docs-site/)

Sign in with an account created during bootstrap and complete its required password
change. Synthetic starter samples are available in the separate demo deployment.
The stack includes API/frontend/docs/proxy, Redis, an ingest worker, a maintenance
worker, beat and the log/error monitor. A healthy Redis alone is not proof of API
or worker connectivity; retain the installer's checks and inspect service logs on failure.

Later data installation uses the authenticated maintenance command, rather than
repeating bootstrap. See [installation operations](../deployment/installation-operations.md).
For programmatic login, follow [API authentication](../api/authentication.md).

## Stop the local application

Retain the environment, project and both files:

```bash
./install.sh compose \
  --env-file .coyote4_dev_env -p coyote4-dev \
  -f deploy/compose/docker-compose.yml \
  -f deploy/compose/docker-compose.dev.yml down
```

The separately operated MongoDB service and persistent bind mounts retain their
own lifecycle. Follow [development setup](developer-environment.md) for source tools
or [first installation](../deployment/first-installation.md) for the full operator procedure.
