# Python package installations

Packages are built locally; public-index publication is not required.

| Installation | Contents |
| --- | --- |
| `coyote_core` wheel | Reusable models, validation, clinical rules and workflows; optional reporting and alignment dependencies |
| `coyote_server` wheel | API, maintenance workers and MongoDB adapter; requires the selected core |
| `coyote_relay` wheel | Submission tools with core and HTTPX; optional API routes and workers use server composition |
| `coyote_atlas` wheel | HGNC/VEP reference bundles and validation; optional API integration uses server composition |
| `coyote_demo` wheel | Synthetic datasets; optional server and worker integrations enforce isolated demo targets |

## Local development

Use [the uv workspace](uv-development.md) for editable installation. The equivalent
pip setup, from the repository root in a prepared development environment, is:

```bash
python -m pip install -r requirements-dev.txt
./install.sh dependencies
python -m pip install --no-deps .release/atlas/coyote_atlas-*.whl
python -m pip install --no-deps -e core -e . \
  -e 'services/relay[api,worker]'
```

Python edits require process reload, not wheel builds. Metadata and dependency
changes require reinstalling or running `uv sync`.
The default uv `application` dependency group includes local Relay and Atlas pinned to a full
Git commit in root `pyproject.toml` and `uv.lock`. The server requires
`coyote-core[reporting,alignment]`; the application dependency export supplies
those feature dependencies for the pip setup above.
For isolated demonstration development, also install `services/demo[api,worker]`
and follow the [demo deployment guide](../deployment/demo-installation.md).

## Core boundary

Core owns reusable models, validation and clinical operations. Base installation
uses Pydantic, PyYAML and Bleach. The `reporting` extra supplies report rendering;
`alignment` supplies pysam for alignment and VCF processing. Core imports neither
the API nor MongoDB implementation. The adapter owns persistence. Frontend assets and
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
policy, shared models and manifest field definitions. The server wheel contains
documentation templates, logos, baseline
installation catalogs and example center configuration, together with the Mongo
adapter's collection mappings and connection defaults. Atlas owns HGNC/VEP reference
snapshots and provenance. Demo owns synthetic workflows and demonstration catalogs.
Each distribution carries its own resources; API and adapter retain separate
folders and imports within the server distribution.

Credentials, deployment environment files, runtime outputs and patient data are
excluded. Operators supply a reviewed external center profile.

## Deployment

Before a Docker build, `./install.sh dependencies` prepares the pinned Atlas
wheel with its source/checksum record. The installer also performs
this preparation for its Compose build commands. The image builds core, server,
Relay and Demo locally, then installs core, server, Relay and Atlas into
the normal runtime image. Demo is added
only by the dedicated demo image target. API source directories do not override
the installed wheels. API and worker services use the same image.

The independent Python client is not installed. Server administration and Relay
submission own their HTTP transport.

The retained-artifact release path verifies all five release wheels against their
versions, SHA-256 digests and source provenance before installation.
See [release compatibility](compatibility.md#build-and-record-an-application-release).
