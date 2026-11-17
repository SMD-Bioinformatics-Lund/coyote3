# Python package installations

Packages are built locally; public-index publication is not required.

| Installation | Contents |
| --- | --- |
| `coyote_contracts` wheel | Structural manifests, resource metadata and bounded retrieval models; Pydantic and PyYAML only |
| `coyote_core` wheel | Clinical core, extending shared Contracts with center policy and workflows |
| `coyote_server` wheel | API, maintenance workers and MongoDB adapter; requires the selected core |
| `coyote_relay` wheel | Submission tools with Contracts and HTTPX; clinical validation adds core, optional API routes and workers use server composition |
| `coyote_atlas` wheel | HGNC/VEP reference bundles and validation; optional API integration uses server composition |
| `coyote_demo` wheel | Synthetic datasets; optional server and worker integrations enforce isolated demo targets |

## Local development

Use [the uv workspace](uv-development.md) for editable installation. The equivalent
pip setup, from the repository root in a prepared development environment, is:

```bash
python -m pip install -r requirements-dev.txt
./install.sh dependencies
python -m pip install --no-deps .release/contracts/coyote_contracts-*.whl \
  .release/relay/coyote_relay-*.whl
python -m pip install --no-deps -e core -e . \
  -e 'services/atlas[api]'
```

Python edits require process reload, not wheel builds. Metadata and dependency
changes require reinstalling or running `uv sync`.
The default uv `application` dependency group includes Relay. Both external
packages resolve to full Git commits selected in root `pyproject.toml` and `uv.lock`.
For isolated demonstration development, also install `services/demo[api,worker]`
and follow the [demo deployment guide](../deployment/demo-installation.md).

## Core boundary

Shared Contracts supplies portable input/response models and imports no clinical
host. Core extends these with clinical operations and validation. It imports neither the API
nor MongoDB implementation. The adapter owns persistence. Frontend assets and
documentation remain separate deployment services. Report templates, styles and
fonts come from the pinned `smd-reports` dependency.

## Server entry point

Configure endpoints, logical database names, secrets, storage roots and the center
profile before starting the server. Pip installation does not provision MongoDB,
Redis, users or clinical configuration.

```bash
coyote4-api --host 127.0.0.1 --port 8001 --workers 1
# Equivalent:
uvicorn coyote_api.app.main:app --host 127.0.0.1 --port 8001 --workers 1
```

The ingestion worker entry point is `coyote_relay.celery_app:celery_app`.
Installing `coyote-relay[api]` alongside the server registers ingestion routes
on API startup. They appear in `/api/v1/docs` and `/api/v1/redoc`; a server
without Relay omits them. Installation does not start a worker automatically.
Server maintenance uses `coyote_api.celery_app`. See
[deployment configuration](../deployment/configuration-reference.md) and
[center configuration](../deployment/center-configuration.md).

## Packaged resources

The core wheel contains canonical permission/role catalogs and the VEP grouping
policy. Contracts packages shared manifest field definitions. The server wheel contains documentation templates, logos, baseline
installation catalogs and example center configuration, together with the Mongo
adapter's collection mappings and connection defaults. Atlas owns HGNC/VEP reference
snapshots and provenance. Demo owns synthetic workflows and demonstration catalogs.
Each distribution carries its own resources; API and adapter retain separate
folders and imports within the server distribution.

Credentials, deployment environment files, runtime outputs and patient data are
excluded. Operators supply a reviewed external center profile.

## Deployment

Before a Docker build, `./install.sh dependencies` prepares the pinned Contracts
and Relay wheels with their source/checksum records. The installer also performs
this preparation for its Compose build commands. The image builds core, server,
Atlas and Demo locally, then installs Contracts, core, server, Relay and Atlas into
the normal runtime image. Demo is added
only by the dedicated demo image target. API source directories do not override
the installed wheels. API and worker services use the same image.

The independent Python client is not installed. Server administration and Relay
submission own their HTTP transport.

The retained-artifact release path verifies all six release wheels against their
versions, SHA-256 digests and source provenance before installation.
See [release compatibility](compatibility.md#build-and-record-an-application-release).
